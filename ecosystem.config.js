module.exports = {
    apps: [{
      name: "stairs",
      script: "bash",
      args: "-c 'sudo /home/connor/crazy-stairs/venv/bin/python3 /home/connor/crazy-stairs/main.py'",
      watch: true,
      env: {
        "PYTHONUNBUFFERED": "1"
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/error.log",
      out_file: "logs/output.log",
      merge_logs: true,
      autorestart: true,
      restart_delay: 4000
    }]
  };