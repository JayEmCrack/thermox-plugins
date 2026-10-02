<?php
declare(strict_types=1);
require __DIR__ . '/../db.php';

require_method('POST');
$in = read_json();

$name = trim((string)($in['experiment_name'] ?? ''));
$mode = strtoupper(trim((string)($in['mode'] ?? '')));
$target = $in['target_temperature'] ?? null;

if ($name === '' || mb_strlen($name) > 100) {
    json_out(['error' => 'experiment_name is required (max 100 characters).'], 422);
}
if (!in_array($mode, ['HEATING', 'COOLING'], true)) {
    json_out(['error' => 'mode must be HEATING or COOLING.'], 422);
}
if (!is_numeric($target) || $target < 20 || $target > 50) {
    json_out(['error' => 'target_temperature must be a number from 20 to 50.'], 422);
}
$target = round((float)$target, 1);

try {
    $pdo = db();
    $pdo->beginTransaction();
    // Only one experiment runs at a time: close any open one first.
    $pdo->exec('UPDATE experiments SET end_time = NOW() WHERE end_time IS NULL');
    $stmt = $pdo->prepare('INSERT INTO experiments (experiment_name, mode, target_temperature) VALUES (?, ?, ?)');
    $stmt->execute([$name, $mode, $target]);
    $id = (int)$pdo->lastInsertId();
    $pdo->commit();
} catch (PDOException $e) {
    if (isset($pdo) && $pdo->inTransaction()) {
        $pdo->rollBack();
    }
    db_error($e);
}
json_out(['experiment_id' => $id], 201);
