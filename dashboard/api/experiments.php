<?php
declare(strict_types=1);
require __DIR__ . '/../db.php';

require_method('GET');

try {
    $rows = db()->query(
        'SELECT e.id, e.experiment_name, e.mode, e.target_temperature, e.start_time, e.end_time,
                COUNT(l.id) AS samples
         FROM experiments e LEFT JOIN temperature_logs l ON l.experiment_id = e.id
         GROUP BY e.id ORDER BY e.id DESC LIMIT 200'
    )->fetchAll();
} catch (PDOException $e) {
    db_error($e);
}
json_out(['experiments' => $rows]);
