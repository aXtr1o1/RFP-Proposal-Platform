module.exports = {
  apps: [
    {
      name: "rfp-api",
      cwd: "C:\\Services\\RFP-Proposal-Platform",
      script: "C:\\Windows\\system32\\.venv\\Scripts\\python.exe",
      interpreter: "none",
      args: [
        "-m", "uvicorn",
        "apps.main:app",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      watch: false,
      autorestart: true,
      max_restarts: 10,
      windowsHide: false,
      merge_logs: true,
      error_file: "C:\\Users\\Administrator\\.pm2\\logs\\rfp-api-error.log",
      out_file: "C:\\Users\\Administrator\\.pm2\\logs\\rfp-api-out.log"
    }
  ]
};
