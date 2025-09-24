<?php
/**
 * Legacy Configuration
 * Typical patterns found in legacy PHP applications
 */

// Database configuration (hardcoded - legacy pattern)
define('DB_HOST', 'localhost');
define('DB_NAME', 'billing_legacy');
define('DB_USER', 'billing_user');
define('DB_PASS', 'billing_pass');

// Payment processing (hardcoded API keys - security issue in legacy)
define('STRIPE_SECRET_KEY', 'sk_test_legacy_key_here');
define('PAYPAL_CLIENT_ID', 'paypal_legacy_client_id');

// Application settings
define('APP_NAME', 'Legacy Billing System');
define('APP_VERSION', '1.2.3');
define('DEBUG_MODE', true);

// Legacy global variables (anti-pattern)
$GLOBALS['current_user'] = null;
$GLOBALS['billing_errors'] = array();

// Error reporting (legacy pattern - all errors shown)
if (DEBUG_MODE) {
    error_reporting(E_ALL);
    ini_set('display_errors', 1);
}

// Timezone (hardcoded - legacy issue)
date_default_timezone_set('America/New_York');
?>