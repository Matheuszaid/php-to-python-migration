<?php
/**
 * Legacy Billing System Class
 * Demonstrates typical legacy patterns, technical debt, and issues
 */

class BillingSystem {
    private $db;

    public function __construct(Database $db) {
        $this->db = $db;
        createTablesIfNotExists($db);
        $this->seedSampleData();
    }

    /**
     * Create a new subscription
     * Legacy pattern: Mixed responsibilities, no validation
     */
    public function createSubscription($user_id, $plan_id, $payment_method_id) {
        // Legacy pattern - no input validation
        $next_billing = date('Y-m-d', strtotime('+1 month'));

        // Legacy pattern - direct SQL construction (safer version)
        $stmt = $this->db->prepare(
            "INSERT INTO subscriptions (user_id, plan_id, next_billing_date)
             VALUES (?, ?, ?)"
        );
        $stmt->bind_param("iis", $user_id, $plan_id, $next_billing);
        $stmt->execute();

        $subscription_id = $this->db->getLastInsertId();

        // Legacy pattern - immediate billing attempt
        $this->chargeBilling($subscription_id);

        return [
            'id' => $subscription_id,
            'user_id' => $user_id,
            'plan_id' => $plan_id,
            'status' => 'active',
            'next_billing_date' => $next_billing
        ];
    }

    /**
     * Process billing cycle for all active subscriptions
     * Legacy pattern: Synchronous processing, no error handling
     */
    public function processBillingCycle() {
        $today = date('Y-m-d');
        $processed = 0;
        $failed = 0;

        // Legacy pattern - fetch all at once (memory issue with large datasets)
        $result = $this->db->query(
            "SELECT s.*, sp.price
             FROM subscriptions s
             JOIN subscription_plans sp ON s.plan_id = sp.id
             WHERE s.status = 'active' AND s.next_billing_date <= '$today'"
        );

        if ($result) {
            while ($subscription = $result->fetch_assoc()) {
                // Legacy pattern - synchronous processing
                sleep(1); // Simulate payment processing delay

                $success = $this->chargeBilling($subscription['id']);

                if ($success) {
                    $this->updateNextBillingDate($subscription['id']);
                    $processed++;
                } else {
                    $this->markSubscriptionPastDue($subscription['id']);
                    $failed++;
                }
            }
        }

        return ['processed' => $processed, 'failed' => $failed];
    }

    /**
     * Get subscriptions for a user
     * Legacy pattern: N+1 query problem
     */
    public function getSubscriptions($user_id = null) {
        $whereClause = $user_id ? "WHERE s.user_id = " . intval($user_id) : "";

        $result = $this->db->query(
            "SELECT s.*, sp.name as plan_name, sp.price, u.email
             FROM subscriptions s
             JOIN subscription_plans sp ON s.plan_id = sp.id
             JOIN users u ON s.user_id = u.id
             $whereClause
             ORDER BY s.created_at DESC"
        );

        $subscriptions = [];
        if ($result) {
            while ($row = $result->fetch_assoc()) {
                // Legacy pattern - loading related data in loop (N+1)
                $row['billing_history'] = $this->getBillingHistory($row['id']);
                $subscriptions[] = $row;
            }
        }

        return $subscriptions;
    }

    /**
     * Cancel subscription
     * Legacy pattern: Hard delete vs soft delete inconsistency
     */
    public function cancelSubscription($subscription_id) {
        $stmt = $this->db->prepare(
            "UPDATE subscriptions SET status = 'cancelled' WHERE id = ?"
        );
        $stmt->bind_param("i", $subscription_id);
        return $stmt->execute();
    }

    /**
     * Private helper methods
     * Demonstrates legacy technical debt
     */
    private function chargeBilling($subscription_id) {
        // Legacy pattern - hardcoded success rate for demo
        $success = rand(1, 10) > 2; // 80% success rate

        $status = $success ? 'success' : 'failed';
        $amount = $this->getSubscriptionAmount($subscription_id);

        $stmt = $this->db->prepare(
            "INSERT INTO billing_history (subscription_id, amount, status)
             VALUES (?, ?, ?)"
        );
        $stmt->bind_param("ids", $subscription_id, $amount, $status);
        $stmt->execute();

        return $success;
    }

    private function getSubscriptionAmount($subscription_id) {
        $result = $this->db->query(
            "SELECT sp.price
             FROM subscriptions s
             JOIN subscription_plans sp ON s.plan_id = sp.id
             WHERE s.id = $subscription_id"
        );

        if ($result && $row = $result->fetch_assoc()) {
            return $row['price'];
        }
        return 0;
    }

    private function updateNextBillingDate($subscription_id) {
        $next_billing = date('Y-m-d', strtotime('+1 month'));
        $this->db->query(
            "UPDATE subscriptions
             SET next_billing_date = '$next_billing'
             WHERE id = $subscription_id"
        );
    }

    private function markSubscriptionPastDue($subscription_id) {
        $this->db->query(
            "UPDATE subscriptions
             SET status = 'past_due'
             WHERE id = $subscription_id"
        );
    }

    private function getBillingHistory($subscription_id) {
        $result = $this->db->query(
            "SELECT * FROM billing_history
             WHERE subscription_id = $subscription_id
             ORDER BY processed_at DESC LIMIT 5"
        );

        $history = [];
        if ($result) {
            while ($row = $result->fetch_assoc()) {
                $history[] = $row;
            }
        }
        return $history;
    }

    /**
     * Seed sample data for demonstration
     */
    private function seedSampleData() {
        // Check if data already exists
        $result = $this->db->query("SELECT COUNT(*) as count FROM users");
        if ($result && $row = $result->fetch_assoc() && $row['count'] > 0) {
            return; // Data already seeded
        }

        // Seed users
        $users = [
            ['john@example.com', 'John Doe'],
            ['jane@example.com', 'Jane Smith'],
            ['bob@example.com', 'Bob Johnson']
        ];

        foreach ($users as $user) {
            $stmt = $this->db->prepare("INSERT INTO users (email, name) VALUES (?, ?)");
            $stmt->bind_param("ss", $user[0], $user[1]);
            $stmt->execute();
        }

        // Seed subscription plans
        $plans = [
            ['Basic Plan', 9.99, 'monthly'],
            ['Pro Plan', 19.99, 'monthly'],
            ['Enterprise Plan', 199.99, 'yearly']
        ];

        foreach ($plans as $plan) {
            $stmt = $this->db->prepare(
                "INSERT INTO subscription_plans (name, price, billing_cycle) VALUES (?, ?, ?)"
            );
            $stmt->bind_param("sds", $plan[0], $plan[1], $plan[2]);
            $stmt->execute();
        }
    }
}
?>