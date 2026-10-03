<?php
declare(strict_types=1);
require __DIR__ . '/../db.php';

// CSV export of one experiment for Chapter IV analysis: export.php?experiment_id=N
require_method('GET');

try {
    $stmt = db()->prepare('SELECT * FROM experiments WHERE id = ?');
    $stmt->execute([(int)($_GET['experiment_id'] ?? 0)]);
    $exp = $stmt->fetch();
    if (!$exp) {
        json_out(['error' => 'Experiment not found.'], 404);
    }
    $stmt = db()->prepare(
        'SELECT `timestamp`, temperature, target_temperature, peltier_status, fan_status, battery_voltage
         FROM temperature_logs WHERE experiment_id = ? ORDER BY id ASC'
    );
    $stmt->execute([$exp['id']]);
} catch (PDOException $e) {
    db_error($e);
}

// Stop spreadsheet apps from running a name like "=SUM(...)" as a formula.
function csv_safe(string $s): string
{
    return preg_match('/^[=+\-@\t\r]/', $s) ? "'" . $s : $s;
}

$file = 'thermox_experiment_' . (int)$exp['id'] . '.csv';
header('Content-Type: text/csv; charset=utf-8');
header("Content-Disposition: attachment; filename=\"$file\"");

$out = fopen('php://output', 'w');
fputcsv($out, ['experiment_id', 'experiment_name', 'mode', 'timestamp', 'elapsed_s', 'temperature_c',
               'target_temperature_c', 'peltier_status', 'fan_status', 'battery_voltage'], ',', '"', '');
$start = strtotime($exp['start_time']);
while ($r = $stmt->fetch()) {
    fputcsv($out, [
        $exp['id'], csv_safe($exp['experiment_name']), $exp['mode'], $r['timestamp'],
        strtotime($r['timestamp']) - $start, $r['temperature'], $r['target_temperature'],
        $r['peltier_status'], $r['fan_status'], $r['battery_voltage'],
    ], ',', '"', '');
}
fclose($out);
