<?php
declare(strict_types=1);

// Shared helpers for the ThermoX API endpoints.
$configFile = __DIR__ . '/config.php';
if (!is_file($configFile)) {
    json_out(['error' => 'config.php is missing. Copy config.sample.php to config.php.'], 500);
}
$config = require $configFile;
date_default_timezone_set($config['timezone'] ?? 'UTC');

function json_out(array $data, int $code = 200)
{
    http_response_code($code);
    header('Content-Type: application/json');
    echo json_encode($data);
    exit;
}

function db(): PDO
{
    global $config;
    static $pdo = null;
    if ($pdo === null) {
        try {
            $pdo = new PDO(
                "mysql:host={$config['db_host']};port=" . (int)($config['db_port'] ?? 3306) . ";dbname={$config['db_name']};charset=utf8mb4",
                $config['db_user'],
                $config['db_pass'],
                [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false,
                ]
            );
            $pdo->exec("SET time_zone = '" . date('P') . "'");
        } catch (PDOException $e) {
            error_log('ThermoX DB connection failed: ' . $e->getMessage());
            json_out(['error' => 'Database connection failed. Check config.php.'], 500);
        }
    }
    return $pdo;
}

// Write endpoints need the shared key (sent as the X-API-Key header) because the
// dashboard is hosted on the public internet.
function require_key(): void
{
    global $config;
    $key = (string)($config['api_key'] ?? '');
    if ($key === '' || !hash_equals($key, (string)($_SERVER['HTTP_X_API_KEY'] ?? ''))) {
        json_out(['error' => 'Invalid or missing access key.'], 401);
    }
}

function require_method(string $method): void
{
    if ($_SERVER['REQUEST_METHOD'] !== $method) {
        header('Allow: ' . $method);
        json_out(['error' => "Use $method."], 405);
    }
}

// Reads a JSON request body. Requiring application/json stops plain cross-site form posts.
function read_json(): array
{
    if (stripos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) {
        json_out(['error' => 'Content-Type must be application/json.'], 415);
    }
    $data = json_decode(file_get_contents('php://input'), true);
    if (!is_array($data)) {
        json_out(['error' => 'Invalid JSON body.'], 400);
    }
    return $data;
}

// Returns the running experiment (end_time IS NULL) or null.
function active_experiment(): ?array
{
    $row = db()->query('SELECT * FROM experiments WHERE end_time IS NULL ORDER BY id DESC LIMIT 1')->fetch();
    return $row ?: null;
}

function db_error(PDOException $e)
{
    error_log('ThermoX DB error: ' . $e->getMessage());
    json_out(['error' => 'Database error.'], 500);
}
