# 飞书群聊机器人

一个功能强大的飞书群聊机器人，支持打卡管理、AI 对话等功能。

## 功能特点

- 📝 **打卡管理**
  - 使用 `#反馈` 命令记录工作进展
  - 使用 `#求助` 命令寻求帮助
  - 使用 `#解答` 命令提供解答

- 🤖 **AI 对话**
  - 支持自然语言交互
  - 智能问答功能
  - 基于 DeepSeek AI 引擎

## 快速开始

1. **安装依赖**
   ```bash
   npm install
   ```

2. **配置环境变量**
   复制 `.env.example` 到 `.env` 并填写以下配置：
   - FEISHU_APP_ID
   - FEISHU_APP_SECRET
   - CHATGPT_API_KEY

3. **启动服务**
   ```bash
   # 开发模式
   npm run dev
   
   # 生产模式
   npm start
   ```

## 使用方法

1. **打卡功能**
   - 发送 `#反馈 [内容]` 记录工作进展
   - 发送 `#求助 [问题]` 寻求帮助
   - 发送 `#解答 [答案]` 提供解答

2. **AI 对话**
   - 直接发送消息即可与 AI 对话
   - AI 会根据上下文提供相应回答

## 技术栈

- Node.js
- Express
- Axios
- Winston (日志管理)
- DeepSeek AI API

## 配置说明

主要配置项（在 `.env` 文件中设置）：

```env
# 飞书配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# AI 配置
CHATGPT_API_KEY=your_api_key

# 服务配置
PORT=3000
NODE_ENV=development
```

## 开发说明

- 使用 `npm run dev` 启动开发服务器
- 代码变更会自动重启服务
- 日志文件位于 `logs` 目录

## 注意事项

- 请确保 `.env` 文件中的敏感信息安全
- 建议在生产环境使用 PM2 等进程管理工具
- 定期检查日志文件大小