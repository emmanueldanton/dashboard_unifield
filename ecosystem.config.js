/**
 * Ecosystem PM2 — dev local uniquement (unifield/ seul).
 * En production : utiliser l'ecosystem.config.js à la RACINE du monorepo SMSI.
 */
module.exports = {
  apps: [
    {
      name: 'unifield-node',
      cwd: __dirname + '/server',
      script: 'index.js',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      max_memory_restart: '256M',
      env: {
        NODE_ENV: 'development',
        PORT: 3005,
        BASE_PATH: '/unifield',
      },
      out_file: 'logs/unifield-node.out.log',
      error_file: 'logs/unifield-node.err.log',
      merge_logs: true,
      time: true,
    },
    {
      name: 'unifield-dashboard',
      cwd: __dirname,
      script: 'gunicorn',
      args: 'app:server --workers 1 --threads 4 --bind 127.0.0.1:8050 --timeout 120',
      interpreter: 'none',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      max_memory_restart: '512M',
      env: {
        APP_ENV: 'development',
        NODE_PROXY: 'false',
      },
      out_file: 'logs/unifield-dashboard.out.log',
      error_file: 'logs/unifield-dashboard.err.log',
      merge_logs: true,
      time: true,
    },
    {
      name: 'unifield-alerter',
      cwd: __dirname,
      script: 'alerter.py',
      interpreter: 'python3',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      max_memory_restart: '256M',
      env: {
        APP_ENV: 'development',
      },
      out_file: 'logs/unifield-alerter.out.log',
      error_file: 'logs/unifield-alerter.err.log',
      merge_logs: true,
      time: true,
    },
  ],
};
