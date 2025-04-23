/*
 * @Descripttion: 
 * @version: 0.0.1
 * @Author: xiaoxin
 * @Date: 2024-02-21 16:23:39
 * @LastEditors: xiaoxin
 * @LastEditTime: 2024-02-27 18:56:09
 */
import express from 'express';
import axios from 'axios';
import dotenv from 'dotenv';
import winston from 'winston';

// 加载环境变量
dotenv.config();

// 配置日志
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
        new winston.transports.File({ filename: 'logs/combined.log' })
    ]
});

// 如果不是生产环境，也将日志打印到控制台
if (process.env.NODE_ENV !== 'production') {
    logger.add(new winston.transports.Console({
        format: winston.format.simple()
    }));
}

// 创建 Express 应用
const app = express();
app.use(express.json());

// 飞书配置
const FEISHU_CONFIG = {
    appId: process.env.FEISHU_APP_ID,
    appSecret: process.env.FEISHU_APP_SECRET,
    webhookUrl: process.env.FEISHU_WEBHOOK_URL || 'https://open.feishu.cn/open-apis/bot/v2/hook/ff7874aa-78c0-4ea9-930a-5bca0d5de86b'
};

// 获取飞书访问令牌
async function getFeishuAccessToken() {
    try {
        const response = await axios.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
            app_id: FEISHU_CONFIG.appId,
            app_secret: FEISHU_CONFIG.appSecret
        });
        return response.data.tenant_access_token;
    } catch (error) {
        logger.error('获取飞书访问令牌失败:', error.message);
        return null;
    }
}

// 发送消息到飞书
async function sendToFeishu(message) {
    try {
        // 使用 Webhook 方式发送消息
        const response = await axios.post(FEISHU_CONFIG.webhookUrl, {
            msg_type: 'text',
            content: {
                text: message
            }
        });
        logger.info('消息发送成功:', response.data);
        return response.data;
    } catch (error) {
        logger.error('发送消息失败:', error.message);
        return null;
    }
}

// 处理打卡消息
async function handleCheckin(text, username) {
    if (text.includes('#反馈')) {
        const response = `收到 ${username} 的打卡反馈：\n${text}`;
        await sendToFeishu(response);
        return true;
    }
    if (text.includes('#求助')) {
        const response = `收到 ${username} 的求助：\n${text}\n请相关同学帮忙解答~`;
        await sendToFeishu(response);
        return true;
    }
    if (text.includes('#解答')) {
        const response = `感谢 ${username} 的解答：\n${text}`;
        await sendToFeishu(response);
        return true;
    }
    return false;
}

// 处理 AI 对话
async function handleAIChat(text) {
    try {
        const response = await axios.post(process.env.CHATGPT_URL + '/v1/chat/completions', {
            model: process.env.CHATGPT_MODEL,
            messages: [{ role: "user", content: text }]
        }, {
            headers: {
                'Authorization': `Bearer ${process.env.CHATGPT_API_KEY}`,
                'Content-Type': 'application/json'
            }
        });

        const aiResponse = response.data.choices[0].message.content;
        await sendToFeishu(aiResponse);
    } catch (error) {
        logger.error('AI 响应出错:', error);
        await sendToFeishu("抱歉，AI 响应出现错误，请稍后再试。");
    }
}

// 处理接收到的消息
app.post('/webhook', async (req, res) => {
    const { challenge, type, event } = req.body;
    
    // 处理验证请求
    if (type === 'url_verification') {
        return res.json({ challenge });
    }

    // 处理消息事件
    if (event && event.message) {
        const { text_content, sender } = event.message;
        const username = sender?.sender_id?.user_name || '用户';
        
        logger.info('收到消息:', { text: text_content, username });

        try {
            // 先检查是否是打卡消息
            const isCheckin = await handleCheckin(text_content, username);
            
            // 如果不是打卡消息，则交给 AI 处理
            if (!isCheckin && text_content) {
                await handleAIChat(text_content);
            }
        } catch (error) {
            logger.error('处理消息失败:', error);
            await sendToFeishu('抱歉，处理消息时出现错误，请稍后再试。');
        }
    }

    res.json({ ok: true });
});

// 发送消息接口
app.post('/send', async (req, res) => {
    const { message } = req.body;
    if (!message) {
        return res.status(400).json({ error: '消息不能为空' });
    }

    try {
        const result = await sendToFeishu(message);
        res.json({ success: true, result });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 健康检查接口
app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// 启动服务器
const port = process.env.PORT || 3000;
app.listen(port, () => {
    logger.info(`服务器运行在端口 ${port}`);
    // 启动时测试飞书配置
    getFeishuAccessToken().then(token => {
        if (token) {
            logger.info('飞书配置验证成功');
        } else {
            logger.warn('飞书配置验证失败，但 Webhook 功能仍可使用');
        }
    });
});