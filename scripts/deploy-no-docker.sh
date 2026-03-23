#!/bin/bash

# Deal Sniper AI Platform - Deployment Script (No Docker)
# This script sets up the platform for 24/7 operation using PM2 process manager
# on a Linux server (Ubuntu/Debian recommended).

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="deal-sniper-ai"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
PM2_CONFIG="$PROJECT_DIR/deal_sniper_ai/pm2.config.js"
LOG_DIR="$PROJECT_DIR/logs"

echo -e "${GREEN}🚀 Deal Sniper AI Platform - Deployment Script${NC}"
echo -e "${YELLOW}Project directory: $PROJECT_DIR${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_warning "Running as root. It's recommended to run as a regular user with sudo privileges."
fi

# Step 1: Update system packages
print_status "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Step 2: Install system dependencies
print_status "Installing system dependencies..."
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    python3-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    nodejs \
    npm \
    git \
    curl \
    wget \
    build-essential

# Step 3: Install PM2 globally
print_status "Installing PM2 process manager..."
sudo npm install -g pm2

# Step 4: Set up PostgreSQL
print_status "Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE DATABASE deal_sniper_ai;" || print_warning "Database might already exist"
sudo -u postgres psql -c "CREATE USER deal_sniper WITH PASSWORD 'secure_password_123';" || print_warning "User might already exist"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE deal_sniper_ai TO deal_sniper;"
sudo -u postgres psql -c "ALTER USER deal_sniper WITH SUPERUSER;" || print_warning "Could not grant superuser"

# Step 5: Set up Redis
print_status "Configuring Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Step 6: Create Python virtual environment
print_status "Creating Python virtual environment..."
python3.11 -m venv "$VENV_DIR"

# Step 7: Install Python dependencies
print_status "Installing Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

# Install Playwright browsers
print_status "Installing Playwright browsers..."
python -m playwright install chromium

# Step 8: Create PM2 configuration
print_status "Creating PM2 configuration..."
cat > "$PM2_CONFIG" << 'EOF'
module.exports = {
  apps: [
    {
      name: "deal-sniper-api",
      script: "deal_sniper_ai/api/main.py",
      interpreter: "python3",
      interpreter_args: "-u",
      cwd: ".",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
        PYTHONPATH: "."
      },
      log_file: "logs/api.log",
      error_file: "logs/api-error.log",
      out_file: "logs/api-out.log",
      time: true
    },
    {
      name: "deal-sniper-worker",
      script: "celery",
      args: "-A deal_sniper_ai.scheduler.celery_app worker --loglevel=info --concurrency=4",
      interpreter: "python3",
      cwd: ".",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
        PYTHONPATH: "."
      },
      log_file: "logs/worker.log",
      error_file: "logs/worker-error.log",
      out_file: "logs/worker-out.log",
      time: true
    },
    {
      name: "deal-sniper-beat",
      script: "celery",
      args: "-A deal_sniper_ai.scheduler.celery_app beat --loglevel=info",
      interpreter: "python3",
      cwd: ".",
      instances: 1,
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: "production",
        PYTHONPATH: "."
      },
      log_file: "logs/beat.log",
      error_file: "logs/beat-error.log",
      out_file: "logs/beat-out.log",
      time: true
    }
  ]
};
EOF

# Step 9: Create log directory
print_status "Creating log directory..."
mkdir -p "$LOG_DIR"

# Step 10: Update configuration for production
print_status "Updating configuration for production..."
CONFIG_FILE="$PROJECT_DIR/deal_sniper_ai/config/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    # Backup original config
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup"

    # Update database configuration for production
    sed -i "s/host: \"localhost\"/host: \"localhost\"/g" "$CONFIG_FILE"
    sed -i "s/port: 54322/port: 5432/g" "$CONFIG_FILE"
    sed -i "s/database: \"postgres\"/database: \"deal_sniper_ai\"/g" "$CONFIG_FILE"
    sed -i "s/username: \"postgres\"/username: \"deal_sniper\"/g" "$CONFIG_FILE"
    sed -i "s/password: \"postgres\"/password: \"secure_password_123\"/g" "$CONFIG_FILE"

    # Update environment to production
    sed -i "s/environment: \"development\"/environment: \"production\"/g" "$CONFIG_FILE"
    sed -i "s/debug: true/debug: false/g" "$CONFIG_FILE"
    sed -i "s/log_level: \"INFO\"/log_level: \"WARNING\"/g" "$CONFIG_FILE"

    # Update API configuration
    sed -i "s/reload: true/reload: false/g" "$CONFIG_FILE"
    sed -i "s/workers: 4/workers: 2/g" "$CONFIG_FILE"
fi

# Step 11: Apply database migrations
print_status "Applying database migrations..."
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
python -c "
from deal_sniper_ai.database.session import engine, Base
import asyncio

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(migrate())
"

# Step 12: Start services with PM2
print_status "Starting Deal Sniper AI with PM2..."
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
pm2 start "$PM2_CONFIG"

# Step 13: Set up PM2 startup script
print_status "Setting up PM2 startup script..."
pm2 save
sudo pm2 startup systemd -u "$USER" --hp "/home/$USER"

# Step 14: Set up Nginx reverse proxy (optional)
read -p "Set up Nginx reverse proxy? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Setting up Nginx reverse proxy..."
    NGINX_CONFIG="/etc/nginx/sites-available/$PROJECT_NAME"
    sudo tee "$NGINX_CONFIG" > /dev/null << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /dashboard {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
    }

    # WebSocket support for real-time updates
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
EOF

    sudo ln -sf "$NGINX_CONFIG" "/etc/nginx/sites-enabled/$PROJECT_NAME"
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t
    sudo systemctl restart nginx
    sudo systemctl enable nginx
fi

# Step 15: Set up firewall
print_status "Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw --force enable

# Step 16: Set up log rotation
print_status "Setting up log rotation..."
sudo tee "/etc/logrotate.d/$PROJECT_NAME" > /dev/null << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $USER $USER
    sharedscripts
    postrotate
        pm2 reloadLogs > /dev/null 2>&1
    endscript
}
EOF

# Step 17: Set up monitoring stack (optional)
read -p "Set up monitoring stack (Prometheus/Grafana)? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Setting up monitoring stack..."

    # Create monitoring directory
    MONITORING_DIR="$PROJECT_DIR/scripts/monitoring"
    mkdir -p "$MONITORING_DIR"

    # Install monitoring dependencies
    print_status "Installing monitoring dependencies..."
    sudo apt-get install -y prometheus prometheus-node-exporter grafana

    # Configure Prometheus
    print_status "Configuring Prometheus..."
    sudo cp "$MONITORING_DIR/prometheus.yml" /etc/prometheus/prometheus.yml
    sudo cp "$MONITORING_DIR/alerts.yml" /etc/prometheus/alerts.yml
    sudo systemctl restart prometheus
    sudo systemctl enable prometheus

    # Configure Grafana
    print_status "Configuring Grafana..."
    sudo systemctl start grafana-server
    sudo systemctl enable grafana-server

    # Import dashboard
    print_status "Importing Grafana dashboard..."
    sleep 10  # Wait for Grafana to start
    curl -X POST \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $(sudo cat /etc/grafana/grafana.ini | grep 'admin_password' | cut -d'=' -f2)" \
      -d @"$MONITORING_DIR/grafana_dashboard.json" \
      http://localhost:3000/api/dashboards/db

    # Install exporters
    print_status "Installing exporters..."

    # PostgreSQL exporter
    wget https://github.com/prometheus-community/postgres_exporter/releases/download/v0.10.1/postgres_exporter-0.10.1.linux-amd64.tar.gz
    tar xvf postgres_exporter-0.10.1.linux-amd64.tar.gz
    sudo mv postgres_exporter-0.10.1.linux-amd64/postgres_exporter /usr/local/bin/
    sudo useradd --no-create-home --shell /bin/false postgres_exporter
    sudo chown postgres_exporter:postgres_exporter /usr/local/bin/postgres_exporter

    # Create systemd service for PostgreSQL exporter
    sudo tee /etc/systemd/system/postgres_exporter.service > /dev/null << EOF
[Unit]
Description=PostgreSQL Exporter
Wants=network-online.target
After=network-online.target postgresql.service

[Service]
User=postgres_exporter
Group=postgres_exporter
Type=simple
Environment="DATA_SOURCE_NAME=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME?sslmode=disable"
ExecStart=/usr/local/bin/postgres_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl start postgres_exporter
    sudo systemctl enable postgres_exporter

    # Redis exporter
    wget https://github.com/oliver006/redis_exporter/releases/download/v1.45.0/redis_exporter-v1.45.0.linux-amd64.tar.gz
    tar xvf redis_exporter-v1.45.0.linux-amd64.tar.gz
    sudo mv redis_exporter-v1.45.0.linux-amd64/redis_exporter /usr/local/bin/
    sudo useradd --no-create-home --shell /bin/false redis_exporter
    sudo chown redis_exporter:redis_exporter /usr/local/bin/redis_exporter

    # Create systemd service for Redis exporter
    sudo tee /etc/systemd/system/redis_exporter.service > /dev/null << EOF
[Unit]
Description=Redis Exporter
Wants=network-online.target
After=network-online.target redis-server.service

[Service]
User=redis_exporter
Group=redis_exporter
Type=simple
ExecStart=/usr/local/bin/redis_exporter --redis.addr=redis://localhost:6379
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl start redis_exporter
    sudo systemctl enable redis_exporter

    print_status "Monitoring stack setup completed!"
fi

# Step 18: Set up backup cron job
print_status "Setting up automated backups..."
BACKUP_SCRIPT="$PROJECT_DIR/scripts/backup_database.sh"
chmod +x "$BACKUP_SCRIPT"

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * $BACKUP_SCRIPT daily --encrypt") | crontab -
(crontab -l 2>/dev/null; echo "0 3 * * 0 $BACKUP_SCRIPT weekly --encrypt") | crontab -
(crontab -l 2>/dev/null; echo "0 4 1 * * $BACKUP_SCRIPT monthly --encrypt") | crontab -

print_status "Backup cron jobs configured (daily at 2 AM, weekly at 3 AM Sunday, monthly at 4 AM 1st)"

# Step 19: Display deployment summary
echo ""
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo -e "${YELLOW}📊 Deployment Summary:${NC}"
echo "   Project Directory: $PROJECT_DIR"
echo "   Virtual Environment: $VENV_DIR"
echo "   Log Directory: $LOG_DIR"
echo "   Backup Directory: $PROJECT_DIR/backups"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Monitoring Directory: $MONITORING_DIR"
fi
echo ""
echo -e "${YELLOW}🚀 Services Status:${NC}"
pm2 status
echo ""
echo -e "${YELLOW}🌐 Access Points:${NC}"
echo "   API Server:      http://localhost:8000"
echo "   API Documentation: http://localhost:8000/api/docs"
echo "   Dashboard:       http://localhost:8000/dashboard"
echo "   Health Check:    http://localhost:8000/api/health"
echo "   Metrics:         http://localhost:8000/api/metrics"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Nginx Proxy:     http://$(curl -s ifconfig.me)"
    echo "   Grafana:         http://localhost:3000 (admin/admin)"
    echo "   Prometheus:      http://localhost:9090"
fi
echo ""
echo -e "${YELLOW}🔧 Management Commands:${NC}"
echo "   View logs:              pm2 logs"
echo "   Restart all:            pm2 restart all"
echo "   Stop all:               pm2 stop all"
echo "   Monitor:                pm2 monit"
echo "   Check API health:       curl http://localhost:8000/api/health"
echo "   Detailed health:        curl http://localhost:8000/api/health/detailed"
echo "   Backup manually:        $BACKUP_SCRIPT daily"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "   1. Update affiliate IDs in $CONFIG_FILE"
echo "   2. Configure Telegram/Discord bots in config.yaml"
echo "   3. Set up SSL certificates (if using Nginx)"
echo "   4. Monitor system with: pm2 monit"
echo "   5. Test alerting system"
echo "   6. Review backup configuration"
echo ""
echo -e "${GREEN}🎉 Deal Sniper AI Platform is now running 24/7 with monitoring!${NC}"

# Step 18: Display important warnings
echo ""
echo -e "${RED}⚠️  IMPORTANT SECURITY NOTES:${NC}"
echo "   - Change the PostgreSQL password in config.yaml"
echo "   - Update Redis password if needed"
echo "   - Set up proper firewall rules"
echo "   - Regularly update the system and dependencies"
echo "   - Monitor logs for suspicious activity"