module.exports = {
  apps: [
    {
      name: "frontend-build",
      cwd: "./",
      script: "cmd",
      args: "/c npm run build",
      autorestart: false,   // don't restart after exit
      watch: false,         // don't watch files
      instances: 1,
      exec_mode: "fork",    // just run once
    },
    {
      name: "frontend-app",
      cwd: "./",
      script: "cmd",
      args: "/c npm start",
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};
