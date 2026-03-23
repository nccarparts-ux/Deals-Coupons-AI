/**
 * PM2 Process Manager Configuration for Deal Sniper AI Platform
 *
 * This configuration manages all platform components for 24/7 operation:
 * - FastAPI server (API and monitoring dashboard)
 * - Celery worker (background task processing)
 * - Celery beat (scheduled task scheduler)
 *
 * Usage:
 *   pm2 start deal_sniper_ai/pm2.config.js
 *   pm2 stop all
 *   pm2 restart all
 *   pm2 logs
 *   pm2 monit
 */

module.exports = {
  apps: [
    // FastAPI Server (API and Dashboard)
    {
      name: "deal-sniper-api",
      script: "deal_sniper_ai/api/main.py",
      interpreter: "python3",
      interpreter_args: "-u",
      cwd: ".",
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      max_restarts: 10,
      min_uptime: "10s",
      kill_timeout: 5000,
      listen_timeout: 3000,
      env: {
        NODE_ENV: "production",
        PYTHONPATH: ".",
        PYTHONUNBUFFERED: "1",
        LOG_LEVEL: "INFO",
        DS_ENVIRONMENT: "production"
      },
      env_development: {
        NODE_ENV: "development",
        DS_ENVIRONMENT: "development",
        LOG_LEVEL: "DEBUG",
        PYTHONUNBUFFERED: "1"
      },
      log_file: "logs/api.log",
      error_file: "logs/api-error.log",
      out_file: "logs/api-out.log",
      time: true,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      // Health check configuration
      health_check: {
        url: "http://localhost:8000/api/health",
        interval: 30000, // 30 seconds
        timeout: 5000,
        retries: 3
      }
    },

    // Celery Worker (Task Processing)
    {
      name: "deal-sniper-worker",
      script: "celery",
      args: "-A deal_sniper_ai.scheduler.celery_app worker --loglevel=info --concurrency=4 --queues=default,monitoring,coupons,analytics,glitches,affiliate,scoring,community,posting,growth,maintenance --hostname=worker@%h --pool=prefork",
      interpreter: "python3",
      cwd: ".",
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "1.5G",
      max_restarts: 10,
      min_uptime: "30s",
      kill_timeout: 10000,
      env: {
        NODE_ENV: "production",
        PYTHONPATH: ".",
        PYTHONUNBUFFERED: "1",
        C_FORCE_ROOT: "true", // Allow Celery to run as root if needed
        LOG_LEVEL: "INFO",
        DS_ENVIRONMENT: "production"
      },
      env_development: {
        NODE_ENV: "development",
        DS_ENVIRONMENT: "development",
        LOG_LEVEL: "DEBUG",
        PYTHONUNBUFFERED: "1",
        C_FORCE_ROOT: "true"
      },
      log_file: "logs/worker.log",
      error_file: "logs/worker-error.log",
      out_file: "logs/worker-out.log",
      time: true,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z"
    },

    // Celery Beat (Task Scheduler)
    {
      name: "deal-sniper-beat",
      script: "celery",
      args: "-A deal_sniper_ai.scheduler.celery_app beat --loglevel=info --schedule=logs/celerybeat-schedule.db",
      interpreter: "python3",
      cwd: ".",
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      max_restarts: 10,
      min_uptime: "30s",
      kill_timeout: 5000,
      env: {
        NODE_ENV: "production",
        PYTHONPATH: ".",
        PYTHONUNBUFFERED: "1",
        LOG_LEVEL: "INFO",
        DS_ENVIRONMENT: "production"
      },
      env_development: {
        NODE_ENV: "development",
        DS_ENVIRONMENT: "development",
        LOG_LEVEL: "DEBUG",
        PYTHONUNBUFFERED: "1"
      },
      log_file: "logs/beat.log",
      error_file: "logs/beat-error.log",
      out_file: "logs/beat-out.log",
      time: true,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z"
    },

    // Optional: Flower Monitoring (Celery Task Monitor)
    {
      name: "deal-sniper-flower",
      script: "celery",
      args: "-A deal_sniper_ai.scheduler.celery_app flower --port=5555 --loglevel=info",
      interpreter: "python3",
      cwd: ".",
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      max_restarts: 5,
      min_uptime: "30s",
      kill_timeout: 5000,
      env: {
        NODE_ENV: "production",
        PYTHONPATH: ".",
        PYTHONUNBUFFERED: "1",
        LOG_LEVEL: "INFO",
        DS_ENVIRONMENT: "production"
      },
      env_development: {
        NODE_ENV: "development",
        DS_ENVIRONMENT: "development",
        LOG_LEVEL: "DEBUG",
        PYTHONUNBUFFERED: "1"
      },
      log_file: "logs/flower.log",
      error_file: "logs/flower-error.log",
      out_file: "logs/flower-out.log",
      time: true,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z"
    }
  ],

  // Deployment configuration
  deploy: {
    production: {
      user: "deploy",
      host: ["your-server-ip"],
      ref: "origin/master",
      repo: "git@github.com:your-username/deal-sniper-ai.git",
      path: "/var/www/deal-sniper-ai",
      "post-deploy": "npm install && pip install -r requirements.txt && pm2 reload ecosystem.config.js --env production",
      env: {
        NODE_ENV: "production",
        DS_ENVIRONMENT: "production"
      }
    },
    staging: {
      user: "deploy",
      host: ["staging-server-ip"],
      ref: "origin/develop",
      repo: "git@github.com:your-username/deal-sniper-ai.git",
      path: "/var/www/deal-sniper-ai-staging",
      "post-deploy": "npm install && pip install -r requirements.txt && pm2 reload ecosystem.config.js --env staging",
      env: {
        NODE_ENV: "staging",
        DS_ENVIRONMENT: "staging"
      }
    }
  }
};