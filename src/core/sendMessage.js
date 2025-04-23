import { log } from "wechaty"
import * as MessageType from "../entity/Message-Type.js"
import * as MYCONFIG from "../../config/config.js"
import axios from "axios"
import { WxPushData } from "../entity/wx-push-data.js"
import * as CHATGPT_CONFIG from "../../config/config-chatgpt.js"
import { ChatGPTModel } from "../entity/ChatGPTModel.js"
import { HttpsProxyAgent } from "https-proxy-agent"
import { PROXY_CONFIG } from "../../config/config-proxy.js";
import { CheckInRecorder, isRoomInWhiteList } from '../utils/checkInRecorder.js';
import { PROMPTS } from '../../config/config-prompt.js';
import { chatHistoryManager } from '../utils/chatHistoryManager.js';

/**
 * 处理消息是否需要回复
 * @param message 消息对象
 */
export async function sendMessage(message) {
    const MyMessage = {
        type: await message.type(),
        self: await message.self(),
        text: await message.text(),
        room: await message.room(),
        mentionSelf: await message.mentionSelf(),
        roomName: (await message.room()?.topic()) || null,
        alias: await message.talker().alias(),
        talkerName: await message.talker().name(),
        date: await message.date(),
        talkerId: await message.payload.talkerId,
        listenerId: await message.payload.listenerId == undefined ? null : message.payload.listenerId,
        roomId: await message.payload.roomId == undefined ? null : message.payload.roomId
    }

    console.log("收到消息：", {
        talkerName: MyMessage.talkerName,
        roomName: MyMessage.roomName,
        text: MyMessage.text,
        isRoom: !!MyMessage.room,
        inWhitelist: isRoomInWhiteList(MyMessage.roomName)
    });

    // 先检查基本条件
    if (MyMessage.self || MyMessage.type !== MessageType.MESSAGE_TYPE_TEXT) {
        return;
    }

    // 如果是群消息，记录到历史中（无论是否@机器人）
    if (MyMessage.room && MyMessage.roomId) {
        chatHistoryManager.addMessage(MyMessage.roomId, "user", MyMessage.text, MyMessage.talkerName);
    }

    // 处理打卡消息 - 移到最前面处理
    const trimmedText = MyMessage.text.trim();
    if (MYCONFIG.dakaKeyWordList.some(keyword => trimmedText.includes(keyword))) {
        console.log("检测到打卡消息");
        // 只在白名单群聊中记录打卡信息并回复
        if (MyMessage.room && isRoomInWhiteList(MyMessage.roomName)){
            console.log("群聊在白名单中，准备记录和回复");
            const recorded = await CheckInRecorder.recordCheckIn(message);
            if (recorded) {
                console.log("打卡记录成功，准备发送夸奖消息");
                const praisePrompt = PROMPTS.CHECKIN_PRAISE(MyMessage.talkerName, MyMessage.text);
                await sendChatGPTResponse(message, praisePrompt, MyMessage, true);
                console.log("打卡记录成功，发送夸奖消息完成");
            }
            return;
        }
    }

    // 处理统计命令
    if (MyMessage.mentionSelf && MyMessage.text.includes('统计')) {
        if (MyMessage.room && isRoomInWhiteList(MyMessage.roomName)) {
            const stats = await CheckInRecorder.getCheckInStats(MyMessage.roomName);
            const replyText = PROMPTS.CHECKIN_STATS(stats);
            console.log("返回统计消息：", replyText);
            await message.room().say(replyText);
            return;
        }
    }

    // 处理其他需要回复的消息
    if (!checkIfNeedReply(MyMessage)) {
        return;
    }

    // 处理普通对话
    if (MyMessage.room && MyMessage.mentionSelf) {
        await sendChatGPTResponse(message, MyMessage.text, MyMessage);
    } else if (!MyMessage.room && MYCONFIG.aliasWhiteList.includes(MyMessage.alias)) {
        await sendChatGPTResponse(message, MyMessage.text, MyMessage);
    }
}

/**
 * 判断消息是否需要回复
 * 
 * @param {MyMessage} message 消息 
 * @returns 需要回复返回true；否则返回false
 */
function checkIfNeedReply(message) {
    //消息类型不是文本
    if (message.type != MessageType.MESSAGE_TYPE_TEXT) {
        return false
    }
    //自己发送的消息不处理
    if (message.self) {
        return false
    }
    //引用的文本不处理
    const regexp = /「[^」]+」\n- - - - - - - - - - - - - -/;
    if (regexp.test(message.text)) {
        return false
    }
    //非白名单内的不处理
    if (isRoomOrPrivate(message) == 0) {
        return false;
    }
    return true;
}

/**
 * 判断消息是否
 * 
 *      是房间消息且@机器人，则返回1
 *      是私聊且在白名单内，则返回2
 *      否则回0
 * 
 * @param {MyMessage} message 消息内容
 */
function isRoomOrPrivate(message) {
    //房间内的消息需要@ 且群聊在名单内
    if (message.room != null && message.mentionSelf == true && isRoomInWhiteList(message.roomName)) {
        return 1;
    }//非房间内消息，且发送人备注在名单内
    else if (message.room == null && MYCONFIG.aliasWhiteList.includes(message.alias)) {
        return 2;
    } else {
        return 0;
    }
}

/**
 * 发送后端处理消息，并返回发送微信
 * @param {Message} message 消息对象
 */
async function forwardMsg(MyMessage, message) {
    log.info(`\n 消息发送时间:${MyMessage.date} 
    消息发送人:${MyMessage.talkerName} 
    消息类型:${MyMessage.type} 
    消息是否@我:${MyMessage.mentionSelf} 
    消息内容:${MyMessage.text} `)

    //1、简单返回消
    // sendSay(message,"你好");

    //2、发送后端
    // axios({
    //     url: MYCONFIG.msgPushUrl,
    //     method: 'post',
    //     headers: {
    //         'Content-Type': 'application/json'
    //     },
    //     data: JSON.stringify(
    //         new WxPushData(
    //             //消息
    //             MyMessage.text,
    //             //消息发送人备注
    //             MyMessage.alias,
    //             //消息发送者ID 微信ID不是永久性
    //             MyMessage.talkerId,
    //             //私聊才有listenerID
    //             MyMessage.listenerId,
    //             //群聊才有房间ID
    //             MyMessage.roomId,
    //             //apikey
    //             MYCONFIG.apiKey
    //             ))
    // }).then(result => {
    //     var reMsg = result.data.msg;
    //     sendSay(message, reMsg,MyMessage);
    // }).catch(response => {
    //     log.error(`异常响应：${response}`);
    //     sendSay(message, `异常响应:${response}`,MyMessage);
    //     return `异常响应：${responese}`;
    // })

    //3、发送ChatGPT
    // 是否启用代理
    let agent = null;
    if (PROXY_CONFIG.enable) {
        agent = new HttpsProxyAgent(PROXY_CONFIG);
    }
    //对话参数配置
    let data = JSON.stringify({
        "model": CHATGPT_CONFIG.CHATGPT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": `${MyMessage.text}`
            }
        ],
        "max_tokens": 1024,
        "temperature": 1,
        "stream": false
    });
    //请求参数配置
    let config = {
        timeout: 120000,
        method: 'post',
        maxBodyLength: Infinity,
        url: CHATGPT_CONFIG.CHATGPT_URL,
        headers: {
            'Authorization': `Bearer ${CHATGPT_CONFIG.CHATGPT_API_KEY}`,
            'Content-Type': 'application/json'
        },
        httpsAgent: agent,
        data: data
    };

    axios.request(config)
        .then((response) => {
            var reMsg = response.data.choices[0].message.content;
            sendSay(message, reMsg, MyMessage);
        })
        .catch((error) => {
            log.error(`异常响应：${JSON.stringify(error)}`);
            sendSay(message, `异常响应:${JSON.stringify(error)}`, MyMessage);
            return `异常响应：${JSON.stringify(error)}`;
        });
}

/**
 * 发送回复逻辑
 * 
 * @param {Message} message 消息内容
 * @param {String} reStr 回复内容
 * @param {Object} MyMessage 消息对象
 * @param {boolean} isCheckIn 是否是打卡消息
 */
function sendSay(message, reStr, MyMessage, isCheckIn = false) {
    // 如果是打卡消息，直接在群里回复
    if (isCheckIn && MyMessage.room) {
        message.room().say(`${reStr}`, message.talker());
        return;
    }

    const isROP = isRoomOrPrivate(MyMessage);
    //房间内消息
    if (isROP == 1) {
        message.room().say(`${reStr}`, message.talker());
    } else if (isROP == 2) {
        //私聊消息
        message.talker().say(`${reStr}\n`);
    }
}

async function sendChatGPTResponse(message, prompt, MyMessage, isCheckIn = false) {
    // 获取聊天ID（群聊用roomId，私聊用talkerId）
    const chatId = MyMessage.roomId || MyMessage.talkerId;
    
    // 注意：用户的消息已经在sendMessage函数中添加过了，这里不需要重复添加
    // 只有私聊消息需要在这里添加
    if (!MyMessage.room) {
        chatHistoryManager.addMessage(chatId, "user", prompt, MyMessage.talkerName);
    }

    // 是否启用代理
    let agent = null;
    if (PROXY_CONFIG.enable) {
        agent = new HttpsProxyAgent(PROXY_CONFIG);
    }

    // 获取历史消息
    const history = chatHistoryManager.getHistory(chatId);
    
    // 打印历史消息日志
    console.log("=== 当前对话的历史消息 ===");
    console.log(`群/用户ID: ${chatId}`);
    console.log(`历史消息数量: ${history.length}`);
    // history.forEach((msg, index) => {
    //     console.log(`[${index + 1}] ${msg.role}: ${msg.content}`);
    // });
    // console.log("========================");

    // 对话参数配置
    let data = JSON.stringify({
        "model": CHATGPT_CONFIG.CHATGPT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": PROMPTS.SYSTEM_ROLE
            },
            ...history, // 添加历史消息
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1024,
        "temperature": 1,
        "stream": false
    });

    // 请求参数配置
    let config = {
        timeout: 200000,
        method: 'post',
        maxBodyLength: Infinity,
        url: CHATGPT_CONFIG.CHATGPT_URL,
        headers: {
            'Authorization': `Bearer ${CHATGPT_CONFIG.CHATGPT_API_KEY}`,
            'Content-Type': 'application/json'
        },
        httpsAgent: agent,
        data: data
    };

    try {
        const response = await axios.request(config);
        const reMsg = response.data.choices[0].message.content;
        console.log(`ChatGPT 回复：${reMsg}`);
        
        // 将AI的回复也添加到历史记录中
        chatHistoryManager.addMessage(chatId, "assistant", reMsg);
        
        await sendSay(message, reMsg, MyMessage, isCheckIn);
    } catch (error) {
        console.error('ChatGPT API Error:', error);
        // const errorMsg = `抱歉，我遇到了一些问题：${error.message}`;
        const errorMsg = `抱歉，我遇到了一些问题`;
        await sendSay(message, errorMsg, MyMessage, isCheckIn);
    }
}
