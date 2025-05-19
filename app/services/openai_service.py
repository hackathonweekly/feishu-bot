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
        
        请根据以上信息生成一段专业且积极的打卡反馈（50字左右），要求：
        1. 结合用户目标和本次打卡内容，具体指出本次进步或成果，给予真诚的肯定和夸奖。
        2. 参考历史打卡，体现连续性和成长，但不要出现"第一次打卡""历史打卡为空"等字眼。
        3. 语气积极、认可成长，避免哄小孩式表达。
        4. 结尾可鼓励继续坚持目标和提升。
        5. 不要使用"你很棒""加油哦"这类简单口头禅，要有内容、有针对性。
        6. 可适当加入一个专业相关emoji。
        
        示例：
        - 本次在数据分析方法上有新突破，目标推进扎实，继续保持！📊
        - 项目开发进度明显，已完成核心模块，目标实现稳步前进。🚀
        - 你的学习方法很系统，目标达成度持续提升，值得肯定！💡
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
