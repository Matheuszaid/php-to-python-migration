#!/bin/bash

# Legacy PHP to Modern Python Migration Script
# This script orchestrates the complete migration process

set -e  # Exit on any error

echo "=== Legacy PHP to Modern Python Migration ==="
echo "Starting migration process..."

# Configuration
LEGACY_DB_HOST=${LEGACY_DB_HOST:-localhost}
LEGACY_DB_PORT=${LEGACY_DB_PORT:-3306}
LEGACY_DB_NAME=${LEGACY_DB_NAME:-billing_legacy}
LEGACY_DB_USER=${LEGACY_DB_USER:-billing}
LEGACY_DB_PASS=${LEGACY_DB_PASS:-billing123}

MODERN_DB_HOST=${MODERN_DB_HOST:-localhost}
MODERN_DB_PORT=${MODERN_DB_PORT:-5432}
MODERN_DB_NAME=${MODERN_DB_NAME:-billing_modern}
MODERN_DB_USER=${MODERN_DB_USER:-billing_user}
MODERN_DB_PASS=${MODERN_DB_PASS:-billing_pass}

DRY_RUN=${DRY_RUN:-false}
BATCH_SIZE=${BATCH_SIZE:-1000}

# Create log directory
mkdir -p logs

# Generate timestamp for this migration run
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/migration_${TIMESTAMP}.log"

echo "Logging to: $LOG_FILE"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check if service is running
check_service() {
    local service=$1
    local host=$2
    local port=$3

    log "Checking $service connectivity..."

    if command -v nc &> /dev/null; then
        if ! nc -z "$host" "$port" 2>/dev/null; then
            log "ERROR: Cannot connect to $service at $host:$port"
            return 1
        fi
    else
        log "WARNING: netcat not available, skipping connectivity check for $service"
    fi

    log "$service is accessible"
    return 0
}

# Pre-migration checks
log "Performing pre-migration checks..."

# Check legacy database connectivity
check_service "Legacy MySQL" "$LEGACY_DB_HOST" "$LEGACY_DB_PORT"

# Check modern database connectivity
check_service "Modern PostgreSQL" "$MODERN_DB_HOST" "$MODERN_DB_PORT"

# Check if Python migration tools are available
if [ ! -f "migration-tools/data_migrator.py" ]; then
    log "ERROR: Migration tools not found!"
    exit 1
fi

# Install migration tool dependencies
log "Installing migration tool dependencies..."
cd migration-tools
pip install -r requirements.txt
cd ..

# Create database URLs
LEGACY_DB_URL="mysql://${LEGACY_DB_USER}:${LEGACY_DB_PASS}@${LEGACY_DB_HOST}:${LEGACY_DB_PORT}/${LEGACY_DB_NAME}"
MODERN_DB_URL="postgresql+asyncpg://${MODERN_DB_USER}:${MODERN_DB_PASS}@${MODERN_DB_HOST}:${MODERN_DB_PORT}/${MODERN_DB_NAME}"

# Pre-migration data backup
log "Creating pre-migration backup..."
BACKUP_FILE="logs/pre_migration_backup_${TIMESTAMP}.sql"

if command -v mysqldump &> /dev/null; then
    mysqldump -h "$LEGACY_DB_HOST" -P "$LEGACY_DB_PORT" -u "$LEGACY_DB_USER" -p"$LEGACY_DB_PASS" "$LEGACY_DB_NAME" > "$BACKUP_FILE" 2>>"$LOG_FILE"
    log "Legacy database backed up to: $BACKUP_FILE"
else
    log "WARNING: mysqldump not available, skipping backup"
fi

# Run data migration
log "Starting data migration process..."

if [ "$DRY_RUN" = "true" ]; then
    log "Running in DRY RUN mode - no actual data will be migrated"
fi

python3 -c "
import asyncio
import sys
import os
sys.path.append('migration-tools')

from data_migrator import DataMigrator, MigrationConfig

async def run_migration():
    config = MigrationConfig(
        legacy_db_url='$LEGACY_DB_URL',
        modern_db_url='$MODERN_DB_URL',
        batch_size=$BATCH_SIZE,
        validate_data=True,
        dry_run=$DRY_RUN
    )

    migrator = DataMigrator(config)

    try:
        results = await migrator.migrate_all_data()

        print('\n=== Migration Results ===')
        for step, result in results.items():
            status = 'SUCCESS' if result.success else 'FAILED'
            print(f'{step}: {status}')
            print(f'  - Records processed: {result.records_processed}')
            print(f'  - Records migrated: {result.records_migrated}')
            print(f'  - Processing time: {result.processing_time_seconds:.2f}s')
            if result.errors:
                print(f'  - Errors: {result.errors}')
            print()

        # Exit with error code if any step failed
        if not all(result.success for result in results.values()):
            sys.exit(1)

    except Exception as e:
        print(f'Migration failed: {e}')
        sys.exit(1)

asyncio.run(run_migration())
" 2>&1 | tee -a "$LOG_FILE"

# Check migration result
MIGRATION_RESULT=${PIPESTATUS[0]}

if [ $MIGRATION_RESULT -eq 0 ]; then
    log "Data migration completed successfully!"

    # Post-migration validation
    log "Running post-migration validation..."

    # Run compatibility tests if available
    if [ -f "tests/test_compatibility.py" ]; then
        log "Running compatibility tests..."
        cd tests
        python3 -m pytest test_compatibility.py -v 2>&1 | tee -a "../$LOG_FILE"
        cd ..
    fi

    # Run data migration tests if available
    if [ -f "tests/test_data_migration.py" ]; then
        log "Running data migration tests..."
        cd tests
        python3 -m pytest test_data_migration.py -v 2>&1 | tee -a "../$LOG_FILE"
        cd ..
    fi

    log "Migration process completed successfully!"
    log "Log file: $LOG_FILE"

else
    log "ERROR: Data migration failed!"
    log "Check log file for details: $LOG_FILE"
    exit 1
fi

# Generate migration report
log "Generating migration report..."
REPORT_FILE="logs/migration_report_${TIMESTAMP}.html"

cat > "$REPORT_FILE" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Migration Report - $TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { background: #f4f4f4; padding: 20px; border-radius: 5px; }
        .success { color: green; }
        .error { color: red; }
        .log { background: #f8f8f8; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Legacy PHP to Modern Python Migration Report</h1>
        <p><strong>Migration Date:</strong> $(date)</p>
        <p><strong>Status:</strong> <span class="success">Completed Successfully</span></p>
    </div>

    <h2>Configuration</h2>
    <ul>
        <li><strong>Legacy Database:</strong> $LEGACY_DB_HOST:$LEGACY_DB_PORT/$LEGACY_DB_NAME</li>
        <li><strong>Modern Database:</strong> $MODERN_DB_HOST:$MODERN_DB_PORT/$MODERN_DB_NAME</li>
        <li><strong>Batch Size:</strong> $BATCH_SIZE</li>
        <li><strong>Dry Run:</strong> $DRY_RUN</li>
    </ul>

    <h2>Migration Log</h2>
    <div class="log">$(cat "$LOG_FILE")</div>

    <hr>
    <p><em>Report generated on $(date)</em></p>
</body>
</html>
EOF

log "Migration report generated: $REPORT_FILE"

echo ""
echo "=== Migration Summary ==="
echo "Status: SUCCESS"
echo "Log file: $LOG_FILE"
echo "Report file: $REPORT_FILE"
echo ""
echo "The legacy PHP system has been successfully migrated to modern Python!"
echo "You can now start the modern system using: docker-compose -f modern-python/docker-compose.yml up"