<?php
declare(strict_types=1);
require __DIR__ . '/../db.php';

// Receives one ThermoX line from the receiver, e.g.
//   TEMP=28.4,TARGET=18.0,MODE=COOLING,PELTIER=1,FAN=1,BATTERY=12.1
// sent as the raw text/plain POST body with an X-API-Key header.
require_method('POST');

$key = (string)($config['api_key'] ?? '');
if ($key === '' || !hash_equals($key, (string)($_SERVER['HTTP_X_API_KEY'] ?? ''))) {
    json_out(['error' => 'Invalid or missing API key.'], 401);
}

$line = trim(file_get_contents('php://input', false, null, 0, 300));
if ($line === '' || strlen($line) > 200) {
    json_out(['error' => 'Empty or oversized line.'], 400);
}

// Parse KEY=VALUE pairs, accepting only known keys.
$allowed = ['TEMP', 'TARGET', 'MODE', 'PELTIER', 'FAN', 'BATTERY'];
$v = [];
foreach (explode(',', $line) as $pair) {
    $parts = explode('=', $pair, 2);
    $k = strtoupper(trim($parts[0]));
    if (count($parts) !== 2 || !in_array($k, $allowed, true) || isset($v[$k])) {
        json_out(['error' => "Bad field: $pair"], 422);
    }
    $v[$k] = trim($parts[1]);
}
foreach (['TEMP', 'TARGET', 'MODE', 'PELTIER', 'FAN'] as $k) {
    if (!isset($v[$k])) {
        json_out(['error' => "Missing $k."], 422);
    }
}

function num_in_range(string $s, float $min, float $max): ?float
{
    if (!preg_match('/^-?\d{1,3}(\.\d{1,3})?$/', $s)) {
        return null;
    }
    $f = (float)$s;
    return ($f >= $min && $f <= $max) ? $f : null;
}

$temp = num_in_range($v['TEMP'], -55, 125);   // DS18B20 range
$target = num_in_range($v['TARGET'], 0, 100);
$mode = strtoupper($v['MODE']);
$battery = isset($v['BATTERY']) ? num_in_range($v['BATTERY'], 0, 60) : null;

if ($temp === null || $target === null) {
    json_out(['error' => 'TEMP or TARGET out of range.'], 422);
}
if (!in_array($mode, ['HEATING', 'COOLING', 'IDLE', 'FAULT'], true)) {
    json_out(['error' => 'MODE must be HEATING, COOLING, IDLE or FAULT.'], 422);
}
if (!in_array($v['PELTIER'], ['0', '1'], true) || !in_array($v['FAN'], ['0', '1'], true)) {
    json_out(['error' => 'PELTIER and FAN must be 0 or 1.'], 422);
}
if (isset($v['BATTERY']) && $battery === null) {
    json_out(['error' => 'BATTERY out of range.'], 422);
}

try {
    $exp = active_experiment();
    if ($exp === null) {
        json_out(['error' => 'No active experiment. Start one on the dashboard first.'], 409);
    }
    $stmt = db()->prepare(
        'INSERT INTO temperature_logs
           (experiment_id, temperature, target_temperature, peltier_status, fan_status, battery_voltage)
         VALUES (?, ?, ?, ?, ?, ?)'
    );
    $stmt->execute([$exp['id'], $temp, $target, (int)$v['PELTIER'], (int)$v['FAN'], $battery]);
} catch (PDOException $e) {
    db_error($e);
}
json_out(['stored' => true, 'experiment_id' => (int)$exp['id']], 201);
