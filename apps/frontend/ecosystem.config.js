module.exports = {
  apps: [
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
