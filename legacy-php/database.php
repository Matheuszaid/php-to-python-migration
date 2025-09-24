<?php
/**
 * Legacy Database Class
 * Demonstrates typical legacy patterns and issues
 */

class Database {
    private $connection;

    public function __construct() {
        // Legacy connection pattern - no connection pooling
        $this->connection = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);

        if ($this->connection->connect_error) {
            die("Connection failed: " . $this->connection->connect_error);
        }
    }

    // Legacy method - no prepared statements (SQL injection risk)
    public function query($sql) {
        $result = $this->connection->query($sql);

        if (!$result) {
            error_log("Database error: " . $this->connection->error);
            return false;
        }

        return $result;
    }

    // Better method - uses prepared statements
    public function prepare($sql) {
        return $this->connection->prepare($sql);
    }

    public function getLastInsertId() {
        return $this->connection->insert_id;
    }

    // Legacy pattern - manual escaping
    public function escape($string) {
        return $this->connection->real_escape_string($string);
    }

    public function __destruct() {
        if ($this->connection) {
            $this->connection->close();
        }
    }
}

/**
 * Legacy Database Helper Functions
 * Demonstrates old-school procedural patterns
 */

function createTablesIfNotExists($db) {
    $tables = [
        "CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )",

        "CREATE TABLE IF NOT EXISTS subscription_plans (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            billing_cycle ENUM('monthly', 'yearly') DEFAULT 'monthly',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )",

        "CREATE TABLE IF NOT EXISTS subscriptions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            plan_id INT NOT NULL,
            status ENUM('active', 'cancelled', 'past_due') DEFAULT 'active',
            next_billing_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
        )",

        "CREATE TABLE IF NOT EXISTS billing_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subscription_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            status ENUM('success', 'failed', 'pending') DEFAULT 'pending',
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
        )"
    ];

    foreach ($tables as $sql) {
        $db->query($sql);
    }
}
?>