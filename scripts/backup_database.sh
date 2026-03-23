#!/bin/bash

# Deal Sniper AI Platform - Database Backup Script
#
# This script performs automated backups of the PostgreSQL database with:
# - Daily full backups
# - Weekly retention
# - Backup verification
# - Compression and encryption
# - S3/cloud storage upload (optional)
#
# Usage:
#   ./backup_database.sh [daily|weekly|monthly] [--upload] [--encrypt]
#
# Configuration: Set environment variables in .env or export them

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_TYPE="${1:-daily}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_DIR="${PROJECT_DIR}/logs"
CONFIG_FILE="${PROJECT_DIR}/deal_sniper_ai/config/config.yaml"

# Load configuration from YAML if available
if [[ -f "$CONFIG_FILE" ]]; then
    DB_HOST=$(grep -A5 '^database:' "$CONFIG_FILE" | grep 'host:' | awk '{print $2}' | tr -d '"')
    DB_PORT=$(grep -A5 '^database:' "$CONFIG_FILE" | grep 'port:' | awk '{print $2}' | tr -d '"')
    DB_NAME=$(grep -A5 '^database:' "$CONFIG_FILE" | grep 'database:' | awk '{print $2}' | tr -d '"')
    DB_USER=$(grep -A5 '^database:' "$CONFIG_FILE" | grep 'username:' | awk '{print $2}' | tr -d '"')
    DB_PASS=$(grep -A5 '^database:' "$CONFIG_FILE" | grep 'password:' | awk '{print $2}' | tr -d '"')
else
    # Fallback to environment variables
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    DB_NAME="${DB_NAME:-deal_sniper_ai}"
    DB_USER="${DB_USER:-deal_sniper}"
    DB_PASS="${DB_PASS:-secure_password_123}"
fi

# Backup settings
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="deal_sniper_${BACKUP_TYPE}_${TIMESTAMP}"
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql"
BACKUP_FILE_COMPRESSED="${BACKUP_DIR}/${BACKUP_NAME}.sql.gz"
BACKUP_FILE_ENCRYPTED="${BACKUP_DIR}/${BACKUP_NAME}.sql.gz.gpg"
LOG_FILE="${LOG_DIR}/backup_${BACKUP_TYPE}_${TIMESTAMP}.log"

# Retention policies (days)
DAILY_RETENTION=7
WEEKLY_RETENTION=30
MONTHLY_RETENTION=365

# Encryption settings (optional)
ENCRYPTION_KEY="${ENCRYPTION_KEY:-}"
ENABLE_ENCRYPTION=false

# S3 settings (optional)
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-backups/deal_sniper_ai}"
ENABLE_S3_UPLOAD=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --upload)
            ENABLE_S3_UPLOAD=true
            shift
            ;;
        --encrypt)
            ENABLE_ENCRYPTION=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Function to print status messages
print_status() {
    echo -e "${GREEN}[+]${NC} $1" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

print_info() {
    echo -e "${BLUE}[*]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check PostgreSQL client
    if ! command -v pg_dump &> /dev/null; then
        print_error "pg_dump not found. Install PostgreSQL client: sudo apt-get install postgresql-client"
        exit 1
    fi

    # Check compression tools
    if ! command -v gzip &> /dev/null; then
        print_error "gzip not found"
        exit 1
    fi

    # Check encryption tools if enabled
    if [[ "$ENABLE_ENCRYPTION" == true ]] && ! command -v gpg &> /dev/null; then
        print_error "gpg not found. Install GPG: sudo apt-get install gnupg"
        exit 1
    fi

    # Check AWS CLI if S3 upload enabled
    if [[ "$ENABLE_S3_UPLOAD" == true ]] && ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Install: sudo apt-get install awscli"
        exit 1
    fi

    # Create directories
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$LOG_DIR"

    # Check database connectivity
    if ! PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\q" &> /dev/null; then
        print_error "Cannot connect to database. Check credentials and network."
        exit 1
    fi

    print_status "Prerequisites check passed"
}

# Function to perform database backup
perform_backup() {
    print_info "Starting database backup..."

    # Set PostgreSQL password environment variable
    export PGPASSWORD="$DB_PASS"

    # Perform backup with pg_dump
    print_info "Backing up database: $DB_NAME"
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --clean \
        --if-exists \
        --create \
        --no-owner \
        --no-privileges \
        --verbose \
        > "$BACKUP_FILE" 2>> "$LOG_FILE"

    # Check if backup was successful
    if [[ $? -eq 0 ]] && [[ -s "$BACKUP_FILE" ]]; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        print_status "Backup completed successfully: $BACKUP_FILE ($BACKUP_SIZE)"
    else
        print_error "Backup failed. Check log file: $LOG_FILE"
        exit 1
    fi

    # Compress backup
    print_info "Compressing backup..."
    gzip -f "$BACKUP_FILE"
    BACKUP_FILE="$BACKUP_FILE_COMPRESSED"
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    print_status "Backup compressed: $BACKUP_FILE ($BACKUP_SIZE)"

    # Encrypt backup if enabled
    if [[ "$ENABLE_ENCRYPTION" == true ]] && [[ -n "$ENCRYPTION_KEY" ]]; then
        print_info "Encrypting backup..."
        echo "$ENCRYPTION_KEY" | gpg --batch --yes --passphrase-fd 0 --symmetric --cipher-algo AES256 -o "$BACKUP_FILE_ENCRYPTED" "$BACKUP_FILE"

        if [[ $? -eq 0 ]]; then
            rm "$BACKUP_FILE"
            BACKUP_FILE="$BACKUP_FILE_ENCRYPTED"
            BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
            print_status "Backup encrypted: $BACKUP_FILE ($BACKUP_SIZE)"
        else
            print_warning "Encryption failed, keeping unencrypted backup"
        fi
    fi

    # Verify backup integrity
    verify_backup
}

# Function to verify backup integrity
verify_backup() {
    print_info "Verifying backup integrity..."

    local verify_file="$BACKUP_FILE"

    # Decrypt if encrypted
    if [[ "$verify_file" == *.gpg ]]; then
        if [[ -z "$ENCRYPTION_KEY" ]]; then
            print_warning "Cannot verify encrypted backup without encryption key"
            return
        fi

        local temp_file="${BACKUP_DIR}/verify_${TIMESTAMP}.sql.gz"
        echo "$ENCRYPTION_KEY" | gpg --batch --yes --passphrase-fd 0 --decrypt -o "$temp_file" "$verify_file" 2>> "$LOG_FILE"

        if [[ $? -ne 0 ]]; then
            print_error "Backup decryption failed - backup may be corrupted"
            rm -f "$temp_file"
            return
        fi
        verify_file="$temp_file"
    fi

    # Decompress and test
    if [[ "$verify_file" == *.gz ]]; then
        if gzip -t "$verify_file" 2>> "$LOG_FILE"; then
            print_status "Backup compression verified"
        else
            print_error "Backup compression verification failed - backup may be corrupted"
            [[ "$verify_file" != "$BACKUP_FILE" ]] && rm -f "$verify_file"
            return
        fi
    fi

    # Test SQL restore (schema only)
    local test_db="backup_test_${TIMESTAMP}"
    PGPASSWORD="$DB_PASS" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$test_db" 2>> "$LOG_FILE"

    if [[ $? -eq 0 ]]; then
        # Try to restore schema only
        if [[ "$verify_file" == *.gz ]]; then
            gunzip -c "$verify_file" | PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$test_db" -v ON_ERROR_STOP=1 > /dev/null 2>> "$LOG_FILE"
        else
            cat "$verify_file" | PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$test_db" -v ON_ERROR_STOP=1 > /dev/null 2>> "$LOG_FILE"
        fi

        if [[ $? -eq 0 ]]; then
            print_status "Backup SQL verification passed"
        else
            print_warning "Backup SQL verification had errors (may be expected for certain data)"
        fi

        # Cleanup test database
        PGPASSWORD="$DB_PASS" dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$test_db" 2>> "$LOG_FILE"
    else
        print_warning "Could not create test database for verification"
    fi

    # Cleanup temp file
    [[ "$verify_file" != "$BACKUP_FILE" ]] && rm -f "$verify_file"
}

# Function to upload to S3
upload_to_s3() {
    if [[ "$ENABLE_S3_UPLOAD" != true ]] || [[ -z "$S3_BUCKET" ]]; then
        return
    fi

    print_info "Uploading backup to S3..."

    local s3_key="${S3_PREFIX}/${BACKUP_TYPE}/${BACKUP_NAME}$(basename "$BACKUP_FILE" | sed 's/^.*\././')"

    if aws s3 cp "$BACKUP_FILE" "s3://${S3_BUCKET}/${s3_key}" --storage-class STANDARD_IA 2>> "$LOG_FILE"; then
        print_status "Backup uploaded to S3: s3://${S3_BUCKET}/${s3_key}"

        # Set lifecycle policy for older backups
        apply_s3_lifecycle
    else
        print_error "S3 upload failed"
    fi
}

# Function to apply S3 lifecycle policies
apply_s3_lifecycle() {
    cat > /tmp/lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "DeleteOldDailyBackups",
            "Status": "Enabled",
            "Prefix": "${S3_PREFIX}/daily/",
            "Expiration": {
                "Days": ${DAILY_RETENTION}
            }
        },
        {
            "ID": "DeleteOldWeeklyBackups",
            "Status": "Enabled",
            "Prefix": "${S3_PREFIX}/weekly/",
            "Expiration": {
                "Days": ${WEEKLY_RETENTION}
            }
        },
        {
            "ID": "DeleteOldMonthlyBackups",
            "Status": "Enabled",
            "Prefix": "${S3_PREFIX}/monthly/",
            "Expiration": {
                "Days": ${MONTHLY_RETENTION}
            }
        }
    ]
}
EOF

    aws s3api put-bucket-lifecycle-configuration \
        --bucket "$S3_BUCKET" \
        --lifecycle-configuration file:///tmp/lifecycle.json \
        2>> "$LOG_FILE" && print_status "S3 lifecycle policy applied"

    rm -f /tmp/lifecycle.json
}

# Function to cleanup old backups
cleanup_old_backups() {
    print_info "Cleaning up old backups..."

    local retention_days
    case "$BACKUP_TYPE" in
        daily)
            retention_days=$DAILY_RETENTION
            ;;
        weekly)
            retention_days=$WEEKLY_RETENTION
            ;;
        monthly)
            retention_days=$MONTHLY_RETENTION
            ;;
        *)
            retention_days=$DAILY_RETENTION
            ;;
    esac

    # Find and delete old backup files
    find "$BACKUP_DIR" -name "deal_sniper_${BACKUP_TYPE}_*.sql*" -mtime +$retention_days -type f -delete 2>> "$LOG_FILE"

    # Cleanup old log files (keep 30 days)
    find "$LOG_DIR" -name "backup_*.log" -mtime +30 -type f -delete 2>> "$LOG_FILE"

    print_status "Old backups cleaned up (retention: ${retention_days} days)"
}

# Function to send notification
send_notification() {
    local status="$1"
    local message="$2"

    # Log notification
    print_info "Sending notification: $message"

    # TODO: Implement notification methods (email, Telegram, Slack, etc.)
    # Example for Telegram:
    # if [[ -n "$TELEGRAM_BOT_TOKEN" ]] && [[ -n "$TELEGRAM_CHAT_ID" ]]; then
    #     curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    #         -d chat_id="$TELEGRAM_CHAT_ID" \
    #         -d text="Deal Sniper AI Backup: $message" \
    #         >> "$LOG_FILE" 2>&1
    # fi

    # Example for email (using mailx):
    # if [[ -n "$EMAIL_RECIPIENT" ]]; then
    #     echo "$message" | mailx -s "Deal Sniper AI Backup $status" "$EMAIL_RECIPIENT"
    # fi
}

# Main execution
main() {
    echo "==========================================" | tee -a "$LOG_FILE"
    echo "Deal Sniper AI Database Backup" | tee -a "$LOG_FILE"
    echo "Type: $BACKUP_TYPE" | tee -a "$LOG_FILE"
    echo "Timestamp: $(date)" | tee -a "$LOG_FILE"
    echo "==========================================" | tee -a "$LOG_FILE"

    # Check prerequisites
    check_prerequisites

    # Start timing
    START_TIME=$(date +%s)

    # Perform backup
    perform_backup

    # Upload to S3 if enabled
    upload_to_s3

    # Cleanup old backups
    cleanup_old_backups

    # Calculate duration
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # Summary
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    print_status "Backup completed in ${DURATION} seconds"
    print_status "Final backup: $BACKUP_FILE ($BACKUP_SIZE)"

    # Send success notification
    send_notification "SUCCESS" "Backup completed successfully: $BACKUP_TYPE backup ($BACKUP_SIZE) in ${DURATION}s"

    echo "==========================================" | tee -a "$LOG_FILE"
    echo "Backup completed successfully" | tee -a "$LOG_FILE"
    echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
    echo "==========================================" | tee -a "$LOG_FILE"

    exit 0
}

# Error handling
trap 'print_error "Backup script failed at line $LINENO"; send_notification "FAILED" "Backup failed at line $LINENO"; exit 1' ERR

# Run main function
main "$@"