<?php
declare(strict_types=1);
require __DIR__ . '/../db.php';

// Returns an experiment, its latest sample and its history.
// ?experiment_id=N for a specific one; otherwise the running one, else the most recent.
require_method('GET');

try {
    $pdo = db();
    if (isset($_GET['experiment_id'])) {
        $stmt = $pdo->prepare('SELECT * FROM experiments WHERE id = ?');
        $stmt->execute([(int)$_GET['experiment_id']]);
        $exp = $stmt->fetch() ?: null;
    } else {
        $exp = active_experiment() ?? ($pdo->query('SELECT * FROM experiments ORDER BY id DESC LIMIT 1')->fetch() ?: null);
    }
    if ($exp === null) {
        json_out(['experiment' => null, 'latest' => null, 'logs' => []]);
    }

    // Newest 3000 samples, returned oldest-first for the graph.
    $stmt = $pdo->prepare(
        'SELECT * FROM (
           SELECT id, `timestamp`, temperature, target_temperature, peltier_status, fan_status, battery_voltage
           FROM temperature_logs WHERE experiment_id = ? ORDER BY id DESC LIMIT 3000
         ) t ORDER BY id ASC'
    );
    $stmt->execute([$exp['id']]);
    $logs = $stmt->fetchAll();
} catch (PDOException $e) {
    db_error($e);
}

$exp['active'] = $exp['end_time'] === null;
json_out([
    'experiment' => $exp,
    'latest' => $logs ? end($logs) : null,
    'logs' => $logs,
    'server_time' => date('Y-m-d H:i:s'),
]);
