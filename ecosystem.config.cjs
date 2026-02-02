module.exports = {
  apps: [{
    name: 'brain-api',
    script: '.venv/bin/uvicorn',
    args: 'api.main:app --host 0.0.0.0 --port 8765 --workers 2',
    cwd: '/root/claude-brain',
    interpreter: 'none',
    instances: 1,
    exec_mode: 'fork',
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      PYTHONPATH: '/root/claude-brain',
      ENVIRONMENT: 'production'
    },
    error_file: '/root/.pm2/logs/brain-api-error.log',
    out_file: '/root/.pm2/logs/brain-api-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true
  }]
};
