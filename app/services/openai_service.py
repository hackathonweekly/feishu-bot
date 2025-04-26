from dotenv import load_dotenv
import os
import httpx
import json
import logging
from typing import List
from app.models.database import Signup, Checkin
from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger(__name__)

# 创建自定义的 httpx 客户端
http_client = httpx.Client(
    timeout=30.0
)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_ENDPOINT = os.getenv("DEEPSEEK_API_ENDPOINT", "https://aiproxy.gzg.sealos.run")
DEEPSEEK_API_URL = f"{DEEPSEEK_API_ENDPOINT}/v1/chat/completions"

logger.info(f"使用 API 端点: {DEEPSEEK_API_URL}")

def get_all_checkins(db: Session, signup_id: int) -> List[Checkin]:
    """获取用户所有的打卡记录"""
    return db.query(Checkin).filter(Checkin.signup_id == signup_id).order_by(Checkin.checkin_date).all()

def generate_ai_feedback(db: Session, signup_id: int, nickname: str, goals: str, content: str, checkin_count: int, is_final: bool = False, is_ranking: bool = False) -> str:
    """生成AI反馈，基于用户的所有打卡记录和目标"""
    # 获取所有历史打卡记录
    all_checkins = get_all_checkins(db, signup_id)
    
    # 构建历史打卡内容字符串
    history = ""
    for i, checkin in enumerate(all_checkins, 1):
        if i == len(all_checkins):  # 最新的打卡
            continue
        history += f"第{i}次打卡内容：{checkin.content}\n"
    
    # 根据不同场景调整提示词
    if is_ranking:
        prompt = f"""
        用户 {nickname} 的学习情况：
        
        【报名目标】
        {goals}
        
        【历史打卡记录】
        {history}
        
        【最新打卡】（第{checkin_count}次）
        {content}
        
        请生成一个简洁的项目进度总结（20字左右），要求：
        1. 清晰说明用户目标的完成程度（已完成XX%/部分完成/刚起步）
        2. 提及一项具体的进展或成就
        3. 语气客观、中立
        4. 不要包含鼓励性语言，纯粹描述事实
        5. 不超过25个字
        
        示例格式：
        - Python基础完成70%，已掌握函数和类
        - 项目部署完成40%，配置好Docker环境
        - Vue组件开发中，完成3个基础组件
        """
    elif is_final:
        prompt = f"""
        用户 {nickname} 的学习情况：
        
        【报名目标】
        {goals}
        
        【历史打卡记录】
        {history}
        
        【本次打卡】（第{checkin_count}次）
        {content}
        
        请生成一个简短的总结（20-30字），要求：
        1. 首先说明用户具体的目标内容（例如："学习Python基础"、"完成项目部署"等）
        2. 然后说明该目标的完成程度（已完成/部分完成/刚起步）
        3. 结合打卡内容，具体说明在目标上取得了什么进展
        4. 加入1个emoji表情点缀
        5. 语气要积极但实事求是

        示例格式：
        - 🚀 Python基础学习目标完成70%，已掌握函数和类的使用，数据处理很扎实！
        - ⭐ 项目部署目标完成40%，成功配置了Docker环境，正在学习K8s！
        """
    else:
        prompt = f"""
        用户 {nickname} 的学习情况：
        
        【报名目标】
        {goals}
        
        【历史打卡记录】
        {history}
        
        【本次打卡】（第{checkin_count}次）
        {content}
        
        请根据以上信息生成一段活泼的回复（50字左右），要求：
        1. 将本次打卡内容与用户目标关联，体现进展
        2. 参考历史打卡，体现连续性和进步
        3. 用充满活力的语气表达惊喜和赞赏
        4. 加入emoji表情，增添趣味性
        5. 给出温暖有趣的鼓励
        
        回复要求：
        1. 语气要活泼自然，像朋友间的对话
        2. 避免过于正式或说教的语气
        3. 多用感叹号表达惊喜
        4. 适当加入一些俏皮可爱的表达
        """

    try:
        response = http_client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system", 
                        "content": """你是一个超级活泼可爱的AI助手，善于分析用户的学习进展并给出鼓励。你的回复要既体现对用户目标和历史的关注，又保持轻松愉快的语气。"""
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 100
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_feedback = result['choices'][0]['message']['content'].strip()
            
            # 如果是排名反馈，直接返回生成的内容
            if is_ranking:
                return ai_feedback
            
            # 构建普通打卡反馈消息
            return f"✨ 打卡成功！\n📝 第 {checkin_count}/21 次打卡\n\n{ai_feedback}"
            
        else:
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"生成AI反馈失败: {str(e)}")
        if is_ranking:
            return "项目进行中，持续推进"
        else:
            return f"✅ 打卡成功！\n📊 第 {checkin_count}/21 次打卡\n\n💪 继续加油，期待您的下次分享！"

def generate_ai_response(query: str) -> str:
    """生成AI回复"""
    try:
        prompt = f"""
        用户在飞书群里@了机器人，并发送了以下消息:
        "{query}"
        
        请生成一个热情、有帮助性且不敷衍的回复。回复应该:
        1. 语气友好活泼
        2. 内容具体有深度，不泛泛而谈
        3. 表达对用户问题的理解
        4. 适当使用emoji增加亲和力
        5. 整体控制在100字以内
        """
        
        response = http_client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system", 
                        "content": """你是一个热情友好的飞书助手，喜欢用活泼的语气回答问题，善于理解用户真实需求并给予有价值的回应。"""
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 200
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"生成AI回复失败: {str(e)}")
        return None
