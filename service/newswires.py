import os
import time
import csv
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urlunparse
import mysql.connector
from mysql.connector import errorcode
from datetime import datetime
from bs4 import BeautifulSoup
import re
import sys
import logging
from systemd.journal import JournalHandler
from google import genai

# Global variables for database connection details
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = '[USERNAME]'
DB_PASSWORD = '[PASSWORD]'
DB_NAME = 'newswires'
TABLE_NAME = 'rss_feed'
LOCK_FILE = '/tmp/newswires.lock'
POLLING_INTERVAL = 60  # 5 minutes

# Define the characters that the Mariadb SQL command will accept
ALLOWED_CHARACTERS = re.compile(r'[ -~]|[\u00A0-\u00FF]|[\u2600-\u26FF]|[\u2700-\u27BF]|[\u2018-\u201F]|[\u2028-\u2029]|\n|\r')

# URL of the RSS feed
url = "https://www.dailymail.co.uk/wires/index.rss"

# System prompt for headline classifier
SYSTEM_PROMPT = "You are a helpful AI chatbot who is using their knowledge of how news and sport stories are written to classify headlines as either 'Sport' or 'Other'. In response to receiving a headline, you can reply with only one word chosen from two, which describes what the headline is about. The two words you can choose from are 'Sport' or 'Other'. Make sure stories about baseball, tennis, football, soccer, motor racing and other sports are all described as 'Sport'. Now, here is the headline you need to classify: "

# Google Gemini API key
CLIENT = genai.Client(api_key="[KEY]")

# Set up logging to the systemd journal
logger = logging.getLogger('newswires')
logger.propagate = False
logger.setLevel(logging.INFO)
handler = JournalHandler()
formatter = logging.Formatter('%(name)s: %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Function to create the table if it doesn't exist
def create_table_if_not_exists(cursor):
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pubDate DATETIME,
        title TEXT,
        description TEXT,
        classification VARCHAR(16) NOT NULL,   -- short, indexable
        source VARCHAR(255),                   -- nullable
        link TEXT,
        plaintext LONGTEXT,
        article_id BIGINT,
        -- Base indexes
        INDEX idx_pubDate (pubDate),
        INDEX idx_title_255 (title(255)),
        INDEX idx_article_id (article_id),
        -- Composite indexes to speed common queries
        INDEX idx_class_source_pubdate (classification, source, pubDate),
        INDEX idx_class_pubdate (classification, pubDate),
        INDEX idx_source_pubdate (source, pubDate)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """
    cursor.execute(create_table_query)

# Function to convert RSS datetime to MySQL datetime format
def convert_rss_datetime(rss_datetime):
    return datetime.strptime(rss_datetime, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d %H:%M:%S')

# Function to extract plaintext from the article link
def extract_plaintext(link):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p', class_='mol-para-with-font')
        plaintext = '\n'.join([para.get_text() for para in paragraphs if 'imageCaption' not in para.get('class', [])])
        return plaintext
    except requests.RequestException as e:
        logger.error(f"Error retrieving story from {link}: {e}")
        return "Story unavailable"

# Function to extract article ID from the URL
def extract_article_id(link):
    match = re.search(r'article-(\d+)', link)
    return int(match.group(1)) if match else None

# Function to extract the full title from the article link
def extract_full_title(link):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('div', class_='heading-tag-switch').find('h1')
        return title_tag.get_text() if title_tag else "Title unavailable"
    except requests.RequestException as e:
        logger.error(f"Error retrieving title from {link}: {e}")
        return "Title unavailable"

# Function to filter out unwanted characters that trigger Mariadb errors
def filter_text(text):
    return ''.join(char for char in text if ALLOWED_CHARACTERS.match(char))

# Function to give classification ('Sport' or 'Other') of headline
def classify(title):
    try:
        response = CLIENT.models.generate_content(
                model = 'gemini-2.5-flash-lite',
                contents = SYSTEM_PROMPT + title)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Classification Error: {e}")
        return 'Other'

# Function to acquire the lock
def acquire_lock():
    if os.path.exists(LOCK_FILE):
        # Check if the lock file is older than the timeout threshold
        if time.time() - os.path.getmtime(LOCK_FILE) > POLLING_INTERVAL * 2:
            os.remove(LOCK_FILE)
        else:
            return False
    with open(LOCK_FILE, 'w') as lock_file:
        lock_file.write(str(os.getpid()))
    return True

# Function to release the lock
def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# Main function to check the RSS feed and update the database
def check_rss_feed():
    # Send a GET request to fetch the RSS feed
    response = requests.get(url)
    rss_content = response.content

    # Parse the RSS feed
    root = ET.fromstring(rss_content)

    # Connect to the MariaDB database
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Check if the table exists and create it if it doesn't
        create_table_if_not_exists(cursor)

        new_story_flag = False

        # Iterate over each item in the RSS feed and insert data into the database
        for item in root.findall('./channel/item'):
            media_credit = item.find('media:credit', {'media': 'https://search.yahoo.com/mrss/'}).text.strip()
            if media_credit is not None and media_credit in ['PA Media', 'Reuters', 'Associated Press Photo', 'AFP']:
                pubDate = item.find('pubDate').text
                description = item.find('description').text
                link = item.find('link').text

                # Parse the URL and remove query parameters
                parsed_url = urlparse(link)
                stripped_url = urlunparse(parsed_url._replace(query=''))

                # Convert the pubDate to MySQL datetime format
                pubDate = convert_rss_datetime(pubDate)

                # Extract article ID from the URL
                article_id = extract_article_id(stripped_url)

                # Check if the article_id already exists in the database
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE article_id = %s", (article_id,))
                if cursor.fetchone()[0] > 0:
#                    logger.info(f"Story already exists: ID={article_id}, skipping...")
                    continue

                # Extract plaintext from the article link
                plaintext = filter_text(extract_plaintext(stripped_url))
#                logger.info(f"PLAINTEXT: {plaintext}")

                # Extract the full title from the article link
                title = extract_full_title(stripped_url)
                logger.info(f"STORY FOUND: {title}")

                classification = classify(title)
                logger.info(f"CLASSIFICATION: {classification}")

                # Insert data into the database
                insert_query = f"""
                INSERT INTO {TABLE_NAME} (pubDate, title, description, classification, source, link, plaintext, article_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (pubDate, title, description, classification, media_credit, stripped_url, plaintext, article_id))

                # Log the headline of each story
                logger.info(f"Story retrieved: ID={article_id}, title={title}")
                new_story_flag = True

                # Commit the transaction after every story. Inefficient but updates faster
                conn.commit()


    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exist")
        else:
            logger.error(err)
    finally:
        cursor.close()
        conn.close()

    if new_story_flag:
        logger.info("Newswires RSS feed has been successfully added to the database.")
    else:
        logger.info("No new stories found this time..")

# Main loop to continuously check the RSS feed
while True:
    if acquire_lock():
        try:
            check_rss_feed()
        finally:
            release_lock()
    else:
        logger.warning("Another instance is already running. Skipping this interval.")
    time.sleep(POLLING_INTERVAL)
