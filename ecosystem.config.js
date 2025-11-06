module.exports = {
  apps: [
    {
      name: "rfp-api",
      cwd: "/home/azureuser/RFP-Proposal-Platform", // Working directory path
      script: "/home/azureuser/RFP-Proposal-Platform/.venv/bin/uvicorn", // Path to the uvicorn executable inside the virtual environment
      interpreter: "none", // No interpreter as it's already handled by the script (uvicorn in this case)
      args: [
        "-m", "uvicorn", // Running uvicorn
        "apps.main:app", // FastAPI app location
        "--host", "0.0.0.0", // Bind to all network interfaces
        "--port", "8000" // Port for the FastAPI app
      ],
      watch: false, // No file watching (set to true if you want PM2 to watch for changes)
      autorestart: true, // Auto-restart the app on failure
      max_restarts: 10, // Maximum restarts before stopping the app
      windowsHide: false, // No hiding the PM2 process window (this is for Windows, so not relevant on Linux)
      merge_logs: true, // Merge the logs (stdout and stderr) into one file
      error_file: "/home/azureuser/.pm2/logs/rfp-api-error.log", // Error log file path for Linux
      out_file: "/home/azureuser/.pm2/logs/rfp-api-out.log" // Output log file path for Linux
    }
  ]
};
