<?php
// Copy this file to config.php and fill in your own values.
// config.php is git-ignored; never commit real credentials.
return [
    'db_host' => '127.0.0.1',
    'db_name' => 'thermox',
    'db_user' => 'thermox_user',
    'db_pass' => 'CHANGE_ME',
    // Shared secret the receiver sends in the X-API-Key header. Use a long random string.
    'api_key' => 'CHANGE_ME_TO_A_LONG_RANDOM_STRING',
    'timezone' => 'Asia/Manila',
];
