module.exports = {
    apps: [{
        name: "test-server-blueprint",
        script: "./app.py",
        interpreter: "./venv/bin/python",
        env: {
            NODE_ENV: "production",
        },
        autorestart: true,
        watch: false,
        max_memory_restart: '512M'
    }]
}
