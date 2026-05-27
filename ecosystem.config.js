module.exports = {
  apps: [
    {
      name: "unifield-dashboard",
      script: "gunicorn",
      args: "app:server --workers 1 --threads 4 --bind 0.0.0.0:8050",
      cwd: "/opt/smsi/unifield",
      interpreter: "none",
      env: {
        APP_ENV: "production",
      },
      out_file: "logs/dashboard.out.log",
      error_file: "logs/dashboard.err.log",
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
    {
      name: "unifield-alerter",
      script: "alerter.py",
      interpreter: "python3",
      cwd: "/opt/smsi/unifield",
      env: {
        APP_ENV: "production",
      },
      out_file: "logs/alerter.out.log",
      error_file: "logs/alerter.err.log",
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
  ],
};
