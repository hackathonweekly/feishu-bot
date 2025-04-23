module.exports = {
  apps: [{
    name: 'feishu-bot',
    script: './index.js',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'development'
    },
    env_production: {
      NODE_ENV: 'production'
    },
    error_file: 'logs/err.log',
    out_file: 'logs/out.log',
    log_file: 'logs/combined.log',
    time: true,
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    merge_logs: true,
    // 重启策略
    exp_backoff_restart_delay: 100, // 重启延迟，初始100ms，之后按指数增长
    max_restarts: 10, // 最大重启次数
    restart_delay: 4000, // 崩溃后等待4秒再重启
    // 监控配置
    monitoring: true,
    // 优雅退出
    kill_timeout: 5000, // 给程序5秒的时间来处理已有连接
  }]
}
