<?php
/**
 * Legacy Subscription Billing System
 * Built: 2015 (typical legacy codebase patterns)
 * Technology: PHP 7.4 + MySQL
 */

require_once 'config.php';
require_once 'database.php';
require_once 'billing.php';

// Initialize database connection
$db = new Database();
$billing = new BillingSystem($db);

// Simple routing (legacy pattern)
$action = $_GET['action'] ?? 'home';

switch ($action) {
    case 'create_subscription':
        handleCreateSubscription($billing);
        break;
    case 'process_billing':
        handleProcessBilling($billing);
        break;
    case 'get_subscriptions':
        handleGetSubscriptions($billing);
        break;
    case 'cancel_subscription':
        handleCancelSubscription($billing);
        break;
    default:
        showHomePage();
        break;
}

function handleCreateSubscription($billing) {
    $data = json_decode(file_get_contents('php://input'), true);

    $subscription = $billing->createSubscription(
        $data['user_id'],
        $data['plan_id'],
        $data['payment_method_id']
    );

    header('Content-Type: application/json');
    echo json_encode($subscription);
}

function handleProcessBilling($billing) {
    $result = $billing->processBillingCycle();

    header('Content-Type: application/json');
    echo json_encode([
        'status' => 'success',
        'processed' => $result['processed'],
        'failed' => $result['failed']
    ]);
}

function handleGetSubscriptions($billing) {
    $user_id = $_GET['user_id'] ?? null;
    $subscriptions = $billing->getSubscriptions($user_id);

    header('Content-Type: application/json');
    echo json_encode($subscriptions);
}

function handleCancelSubscription($billing) {
    $subscription_id = $_GET['subscription_id'] ?? null;
    $result = $billing->cancelSubscription($subscription_id);

    header('Content-Type: application/json');
    echo json_encode(['status' => $result ? 'success' : 'error']);
}

function showHomePage() {
    echo '<h1>Legacy Billing System</h1>';
    echo '<p>PHP-based subscription billing system (circa 2015)</p>';
    echo '<ul>';
    echo '<li><a href="?action=get_subscriptions">View Subscriptions</a></li>';
    echo '<li><a href="?action=process_billing">Process Billing</a></li>';
    echo '</ul>';
}
?>