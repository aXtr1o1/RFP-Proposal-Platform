module.exports = {
  apps: [
    {
      name: "frontend-build",
      cwd: "./",
      script: "npm",
      args: "run build",  // Run the 'build' script defined in your package.json
      autorestart: false,   // Don't restart after exit
      watch: false,         // Don't watch files
      instances: 1,
      exec_mode: "fork",    // Just run once
    },
    {
      name: "frontend-app",
      cwd: "./",
      script: "npm",
      args: "start",        // Run the 'start' script defined in your package.json
      env: {
        NODE_ENV: "production", // Set the environment variable
      },
    },
  ],
};
