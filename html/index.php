<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Index</title>
    <link rel="stylesheet" href="styles.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;0,900;1,300;1,400;1,700;1,900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,700;0,900;1,300;1,400;1,700;1,900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="styles.css">
</head>

<body>
<h1>Newswires: <a href="https://news.johnwarburton.net/?source=PA%20Media">PA</a>, Reuters, AP, AFP</h1>
<?php
$servername = "localhost";
$username = "[USERNAME]";
$password = "[PASSWORD]";
$dbname = "newswires";

// Read an optional source from the URL
$requestedSource = isset($_GET['source']) ? trim($_GET['source']) : '';
$requestedSource = urldecode($requestedSource);


// Create connection
$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Set the right character set
mysqli_set_charset($conn, 'utf8mb4');

// Fetch the most recent 700 stories
if ($requestedSource !== '') {
    $sql = "SELECT article_id, pubDate, source, title, classification, description
            FROM rss_feed
            WHERE classification='Other' AND source = ?
            ORDER BY pubDate DESC LIMIT 700";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("s", $requestedSource);
} else {
    $sql = "SELECT article_id, pubDate, source, title, classification, description
            FROM rss_feed
            WHERE classification='Other'
            ORDER BY pubDate DESC LIMIT 700";
    $stmt = $conn->prepare($sql);
}

$stmt->execute();


$result = $stmt->get_result();

if ($result && $result->num_rows > 0) {
    while($row = $result->fetch_assoc()) {
        $pubDate = date("H:i:s \o\\n jS F Y", strtotime($row["pubDate"]));
        $title = htmlspecialchars($row["title"]);
        $classification = $row["classification"];
        $source = $row["source"];
        $description = htmlspecialchars($row["description"]);
        $article_id = $row["article_id"];

        echo "<div class='story'>\n";
        echo "<div class='pubDate'>AT $pubDate from $source:</div>\n";
        echo "<div class='headline'><a href='story.php?article_id=$article_id'>$title</a></div>\n";
#       echo "<div class='description'>Category: $classification</div>\n";
        echo "<div class='description'>$description</div>\n";
        echo "</div>\n";
    }
} else {
    echo "No stories found.";
}

$stmt->close();
?>
</body>
</html>
