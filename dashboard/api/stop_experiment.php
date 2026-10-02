<?php
declare(strict_types=1);
require __DIR__ . '/../db.php';

require_method('POST');
read_json();

try {
    $stmt = db()->prepare('UPDATE experiments SET end_time = NOW() WHERE end_time IS NULL');
    $stmt->execute();
} catch (PDOException $e) {
    db_error($e);
}
json_out(['stopped' => $stmt->rowCount()]);
