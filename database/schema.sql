-- ThermoX experiment logging tables
-- Create a database first (named "thermox" if your host allows it; hosting panels often
-- add a prefix such as if0_12345_thermox), select it in phpMyAdmin, then use the
-- Import tab with this file. Command line alternative:  mysql -u USER -p DBNAME < schema.sql

CREATE TABLE IF NOT EXISTS experiments (
  id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  experiment_name    VARCHAR(100) NOT NULL,
  mode               ENUM('HEATING','COOLING') NOT NULL,
  target_temperature DECIMAL(4,1) NOT NULL,
  start_time         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  end_time           DATETIME NULL DEFAULT NULL,   -- NULL = still running
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS temperature_logs (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  experiment_id      INT UNSIGNED NOT NULL,
  `timestamp`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  temperature        DECIMAL(5,2) NOT NULL,
  target_temperature DECIMAL(4,1) NOT NULL,
  peltier_status     TINYINT(1) NOT NULL,           -- 1 = ON, 0 = OFF
  fan_status         TINYINT(1) NOT NULL,           -- 1 = ON, 0 = OFF
  battery_voltage    DECIMAL(5,2) NULL DEFAULT NULL, -- NULL = not measured
  PRIMARY KEY (id),
  KEY idx_logs_experiment_time (experiment_id, `timestamp`),
  CONSTRAINT fk_logs_experiment FOREIGN KEY (experiment_id)
    REFERENCES experiments (id) ON DELETE CASCADE
) ENGINE=InnoDB;
