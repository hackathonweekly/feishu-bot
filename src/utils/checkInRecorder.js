import fs from 'fs/promises';
import path from 'path';
import { roomWhiteList, roomWhiteKeyWordList } from '../../config/config.js';

const CHECKIN_FILE = 'data/checkins.json';

export function isRoomInWhiteList(roomName) {
    if (!roomName) {
        return false;
    }
    // 检查房间是否在白名单中
    const inWhiteList = roomWhiteList.includes(roomName);
    // 检查房间名是否包含任何关键词
    const containsKeyWord = roomWhiteKeyWordList.some(keyword => roomName.includes(keyword));
    // 如果房间在白名单中或房间名包含关键词，则记录打卡信息
    return inWhiteList || containsKeyWord;
}

export class CheckInRecorder {
    static async recordCheckIn(message) {
        const room = await message.room();
        const roomName = await room?.topic();

        // 只记录白名单群聊中的打卡信息
        if (room && !isRoomInWhiteList(roomName)) {
            return false;
        }

        const checkInData = {
            name: await message.talker().name(),
            time: message.date().toISOString(),
            msg: await message.text(),
            room: roomName || null
        };

        try {
            // Ensure data directory exists
            await fs.mkdir('data', { recursive: true });

            // Read existing records
            let records = [];
            try {
                const data = await fs.readFile(CHECKIN_FILE, 'utf8');
                records = JSON.parse(data);
            } catch (error) {
                // File doesn't exist or is invalid, start with empty array
            }

            // Add new record
            records.push(checkInData);

            // Write back to file
            await fs.writeFile(CHECKIN_FILE, JSON.stringify(records, null, 2));

            return true;
        } catch (error) {
            console.error('Failed to record check-in:', error);
            return false;
        }
    }

    /**
     * 获取打卡统计数据
     * @param {string} roomName - 群聊名称，如果提供则只统计该群的打卡记录
     * @returns {Object} 统计结果，格式为 {name: count}
     */
    static async getCheckInStats(roomName = null) {
        try {
            // 读取记录
            let records = [];
            try {
                const data = await fs.readFile(CHECKIN_FILE, 'utf8');
                records = JSON.parse(data);
            } catch (error) {
                return {};
            }

            // 如果指定了群聊，只统计该群的记录
            if (roomName) {
                records = records.filter(record => record.room === roomName);
            }

            // 统计每个人的打卡次数
            const stats = {};
            records.forEach(record => {
                stats[record.name] = (stats[record.name] || 0) + 1;
            });

            return stats;
        } catch (error) {
            console.error('Failed to get check-in stats:', error);
            return {};
        }
    }
} 