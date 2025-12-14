<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Story</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;0,900;1,300;1,400;1,700;1,900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,700;0,900;1,300;1,400;1,700;1,900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="styles.css">
</head>

<body>
<h1>News Story</h1>
<?php
$servername = "localhost";
$username = "[USERNAME]";
$password = "[PASSWORD]";
$dbname = "newswires";

// Create connection
$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Set the right character set
mysqli_set_charset($conn, 'utf8mb4');

$article_id = intval($_GET['article_id']);

// Fetch the story details
$sql = "SELECT pubDate, title, plaintext, source, description FROM rss_feed WHERE article_id = $article_id";
$result = $conn->query($sql);

if ($result->num_rows > 0) {
    $row = $result->fetch_assoc();
    $pubDate = date("H:i:s \o\\n jS F Y", strtotime($row["pubDate"]));
    $title = htmlspecialchars($row["title"]);
    $source = htmlspecialchars($row["source"]);
    $description = htmlspecialchars($row["description"]);
    $plaintext = nl2br(htmlspecialchars($row["plaintext"]));

    echo "<div class='headline'><b>$title</b></div>\n";
    echo "<div class='source'><b>$source</b></div>\n";
    echo "<div class='description'><b>$description</b></div>\n";
    echo "<div class='pubDate'>Received: $pubDate</div><br>\n";

    // Add a blank line between paragraphs
    $paragraphs = explode("\n", $plaintext);
    foreach ($paragraphs as $paragraph) {
        echo "<div class='plaintext'>$paragraph</div>\n";

    }
} else {
    echo "Story not found.";
}

$conn->close();
?>
</body>
</html>
