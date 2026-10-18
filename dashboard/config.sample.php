<?php
// Copy this file to config.php and fill in your own values.
// config.php is git-ignored; never commit real credentials.
return [
    // Use the host name from your hosting panel's MySQL page (NOT 127.0.0.1 on most free hosts).
    'db_host' => 'sqlXXX.example-host.com',
    'db_port' => 3306,
    'db_name' => 'your_database_name',
    'db_user' => 'your_database_user',
    'db_pass' => 'CHANGE_ME',
    // Access key you type into the dashboard. Start/stop/log requests are rejected without it.
    // Use a long random string.
    'api_key' => 'CHANGE_ME_TO_A_LONG_RANDOM_STRING',
    'timezone' => 'Asia/Manila',
];
