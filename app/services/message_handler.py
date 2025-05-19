import json
import re
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models.database import Period, Signup, Checkin, Certificate
from .openai_service import generate_ai_feedback, generate_ai_response
from .feishu_service import FeishuService
import os
import requests
import time
import random

# 配置日志
logger = logging.getLogger(__name__)


class MessageHandler:
    def __init__(self, db: Session):
        self.db = db
        self.feishu_service = FeishuService()
        self._processed_messages = set()  # 用于存储已处理的消息ID

    def handle_message(self, message_content: str, chat_id: str, message_type: str = "text", message_id: str = None) -> str:
        """处理接收到的消息"""
        logger.info(f"开始处理消息，类型: {message_type}, ID: {message_id}")
        
        # 如果消息ID存在且已处理过，则跳过
        if message_id:
            if message_id in self._processed_messages:
                logger.info(f"消息 {message_id} 已经处理过，跳过")
                return None
            self._processed_messages.add(message_id)
            
            # 保持集合大小在合理范围内，避免内存泄漏
            if len(self._processed_messages) > 1000:
                self._processed_messages.clear()

        logger.info(f"消息内容: {message_content}")

        if message_type == "interactive":
            try:
                content_json = json.loads(message_content)
                title = content_json.get("title", "").strip()
                logger.info(f"处理 interactive 消息，标题: {title}")

                # 检查是否为接龙消息
                if title == "🌟本期目标制定":
                    logger.info("检测到目标制定标题")
                    elements = content_json.get("elements", [])
                    logger.info(f"消息元素: {elements}")
                    
                    # 检查是否包含接龙说明文本和参与人数文本
                    has_signup_text = False
                    has_participants_text = False
                    has_link = False
                    
                    # 遍历所有元素组
                    for element_group in elements:
                        if isinstance(element_group, list):
                            # 检查每个元素组中的文本元素
                            for element in element_group:
                                if element.get("tag") == "text":
                                    text = element.get("text", "")
                                    # 检查接龙说明文本
                                    if "修改群昵称" in text and "自我介绍" in text and "本期目标" in text:
                                        has_signup_text = True
                                        logger.info("找到接龙说明文本")
                                    # 检查参与人数文本
                                    elif "当前" in text and "人参加群接龙" in text:
                                        has_participants_text = True
                                        logger.info(f"找到参与人数文本: {text}")
                                # 检查链接元素
                                elif element.get("tag") == "a" and element.get("href"):
                                    has_link = True
                                    logger.info("找到链接元素")
                    
                    logger.info(f"检查结果 - 接龙说明: {has_signup_text}, 参与人数: {has_participants_text}, 链接: {has_link}")
                    
                    # 只有在有接龙说明、有链接但没有参与人数时才创建新期数
                    if has_link and not has_participants_text:
                        logger.info("检测到新接龙消息，开始创建新期数")
                        return self.create_new_period(chat_id, message_content)
                    else:
                        if has_participants_text:
                            logger.info("检测到参与接龙消息，不进行处理")
                        else:
                            logger.info("消息格式不符合要求")
                        return None
                else:
                    logger.info(f"不是目标制定消息，标题为: {title}")

            except json.JSONDecodeError as e:
                logger.error(f"解析消息内容失败: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"处理消息时发生错误: {str(e)}")
                return None
        elif message_type == "text":
            try:
                # 尝试解析JSON内容
                content_json = json.loads(message_content)
                text_content = content_json.get("text", "")
                
                # 检查是否包含@机器人的标记
                if "@_user_" in text_content:
                    return self.handle_mention(text_content, chat_id)
                elif message_content.strip() == '#接龙结束':
                    return self.handle_signup_end(chat_id)
                elif message_content.strip() == '#活动结束':
                    return self.handle_activity_end(chat_id)
                elif message_content.strip() == '#打卡开始':
                    return self.handle_checkin_start(chat_id)
                elif message_content.startswith('#打卡'):
                    return self.handle_checkin(message_content, chat_id)
                # 添加处理排名指令代码
                elif message_content.strip() in ['#3天打卡排名公布', '#7天打卡排名公布', '#14天打卡排名公布', '#21天打卡排名公布']:
                    return self.handle_ranking_publish(message_content, chat_id)
                elif message_content.strip() == '#最新打卡排名公布':
                    return self.handle_ranking_publish_latest(chat_id)
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接处理原始文本
                message_text = message_content.strip()
                # 检查是否是@消息
                if message_text.startswith("@"):
                    return self.handle_mention(message_content, chat_id)
                # 检查其他指令
                elif message_text == '#接龙结束':
                    return self.handle_signup_end(chat_id)
                elif message_text == '#活动结束':
                    return self.handle_activity_end(chat_id)
                elif message_text == '#打卡开始':
                    return self.handle_checkin_start(chat_id)
                elif message_text.startswith('#打卡'):
                    return self.handle_checkin(message_content, chat_id)
                # 添加处理排名指令代码
                elif message_text in ['#3天打卡排名公布', '#7天打卡排名公布', '#14天打卡排名公布', '#21天打卡排名公布']:
                    return self.handle_ranking_publish(message_content, chat_id)
                elif message_text == '#最新打卡排名公布':
                    return self.handle_ranking_publish_latest(chat_id)
        return None

    def create_new_period(self, chat_id: str, message_content: str) -> str:
        """创建新的活动期数"""
        try:
            logger.info("开始检查是否有正在进行的活动期数")
            # 检查是否有正在进行的活动期数
            existing_period = self.db.query(Period)\
                .filter(Period.status.in_(['报名中', '进行中']))\
                .first()

            if existing_period:
                error_msg = f"接龙失败：当前已有活动在进行中（{existing_period.period_name}，状态：{existing_period.status}）"
                logger.info(error_msg)
                return error_msg

            logger.info("获取最新的期数")
            try:
                # 解析消息内容获取接龙链接
                content_json = json.loads(message_content)
                elements = content_json.get("elements", [])
                signup_link = None

                # 查找链接元素
                for element_group in elements:
                    if isinstance(element_group, list):
                        for element in element_group:
                            if element.get("tag") == "a" and element.get("href"):
                                signup_link = element.get("href")
                                break
                    if signup_link:
                        break

                if not signup_link:
                    logger.warning("未找到接龙链接")

                # 获取最新的期数
                latest_period = self.db.query(Period)\
                    .order_by(Period.id.desc())\
                    .first()

                # 生成新的期数名称（格式：YYYY-MM）
                now = datetime.now()
                period_name = now.strftime("%Y-%m")

                if latest_period and latest_period.period_name == period_name:
                    # 如果同月已有期数，在月份后面加上字母
                    last_char = latest_period.period_name[-1]
                    if last_char.isalpha():
                        # 如果已经有字母，递增字母
                        next_char = chr(ord(last_char) + 1)
                        period_name = f"{period_name[:-1]}{next_char}"
                    else:
                        # 如果没有字母，添加字母a
                        period_name = f"{period_name}a"

                logger.info(f"准备创建新期数: {period_name}")
                # 创建新的活动期数，包含接龙链接
                new_period = Period(
                    period_name=period_name,
                    start_date=now,
                    end_date=now + timedelta(days=30),
                    status='报名中',
                    signup_link=signup_link
                )
                self.db.add(new_period)
                self.db.commit()
                logger.info(f"成功创建新期数: {period_name}")

                return "本期接龙已开启，请大家踊跃报名！"

            except Exception as e:
                error_msg = f"接龙失败：创建新期数时发生错误 - {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.db.rollback()
                return error_msg

        except Exception as e:
            error_msg = f"接龙失败：检查活动状态时发生错误 - {str(e)}"
            logger.error(error_msg, exc_info=True)
            if 'session' in dir(self.db):
                self.db.rollback()
            return error_msg

    def handle_signup_end(self, chat_id: str) -> str:
        """处理接龙结束命令，适配新多维表结构"""
        try:
            logger.info("开始处理接龙结束命令")
            # 获取当前报名中的活动期数
            current_period = self.db.query(Period)\
                .filter(Period.status == '报名中')\
                .first()

            if not current_period:
                error_msg = "接龙结束失败：没有正在进行的接龙活动"
                logger.info(error_msg)
                return error_msg

            if not current_period.signup_link:
                error_msg = "接龙结束失败：未找到接龙链接"
                logger.info(error_msg)
                return error_msg

            try:
                # 从飞书多维表获取数据（已适配新结构）
                logger.info(f"开始从多维表获取数据: {current_period.signup_link}")
                signup_data = self.feishu_service.fetch_signup_data(current_period.signup_link)
                
                if not signup_data:
                    error_msg = "接龙结束失败：未获取到有效的报名数据"
                    logger.error(error_msg)
                    return error_msg

                # 清除当前期数的所有报名记录
                self.db.query(Signup)\
                    .filter(Signup.period_id == current_period.id)\
                    .delete()
                logger.info(f"已清除期数 {current_period.period_name} 的现有报名记录")

                # 处理并添加新的报名记录
                success_count = 0
                developers = []
                for record in signup_data:
                    try:
                        # 直接取新结构字段
                        nickname = record.get('nickname', '').strip()
                        focus_area = record.get('focus_area', '未知').strip()
                        introduction = record.get('introduction', '').strip()  # 现在为项目介绍
                        goals = record.get('goals', '').strip()
                        signup_time = record.get('signup_time', datetime.now())

                        if not nickname:
                            logger.warning("跳过空昵称的记录")
                            continue

                        logger.info(f"处理报名记录 - 昵称: {nickname}, 项目: {focus_area}")
                        logger.info(f"项目介绍: {introduction}")
                        logger.info(f"目标: {goals}")

                        # 创建新的报名记录
                        signup = Signup(
                            period_id=current_period.id,
                            nickname=nickname,
                            focus_area=focus_area,
                            introduction=introduction,  # 现在为项目介绍
                            goals=goals,
                            signup_time=signup_time
                        )
                        self.db.add(signup)
                        success_count += 1
                        
                        # 收集开发者信息用于总结
                        developers.append({
                            'nickname': nickname,
                            'focus_area': focus_area
                        })
                        
                        logger.info(f"成功添加报名记录: {nickname}")
                    except Exception as e:
                        logger.error(f"处理报名记录时出错: {str(e)}")
                        continue

                if success_count == 0:
                    error_msg = "接龙结束失败：没有成功添加任何报名记录"
                    logger.error(error_msg)
                    self.db.rollback()
                    return error_msg

                # 更新活动状态为已结束
                current_period.status = '进行中'
                self.db.commit()
                logger.info(f"成功更新活动期数 {current_period.period_name} 状态为进行中")
                logger.info(f"总共处理了 {success_count} 条报名记录")

                # 生成报名统计信息
                total_signups = len(developers)
                focus_area_groups = {}
                
                for dev in developers:
                    focus_area = dev['focus_area']
                    if focus_area not in focus_area_groups:
                        focus_area_groups[focus_area] = []
                    focus_area_groups[focus_area].append(dev['nickname'])
                
                # 构建响应消息
                response_lines = [
                    f"✨ {current_period.period_name}期活动圆满结束！",
                    "感谢大家这段时间的倾情付出与坚持不懈！每一次打卡都见证了我们共同成长的足迹。\n"
                ]
                
                # 修改开发者统计信息部分，加入活动总结感慨
                response_lines.append("📊 这21天的旅程告诉我们，成长不在于速度，而在于坚持。无论你完成了多少次打卡，每一步都是向目标迈进的珍贵经历。")
                
                response_lines.append("🏆 为纪念你在本期的成长历程，我们为每位参与者准备了专属电子证书！")
                response_lines.append("💫 访问 https://superb-clafoutis-c8572b.netlify.app/ 输入你的昵称，即可查看为你量身定制的成长档案，记录你的每一步进步与收获！")
                
                # 添加达标情况说明，保持文风一致
                response_lines.append("\n✨ 在这场技术与毅力的共舞中，我们欣喜地看到许多伙伴坚持到最后，完成了我们设定的挑战：")
                response_lines.append("🔍 21天内完成7次有效打卡并实现自定目标")
                
                # 按专注领域分组显示
                response_lines.append("\n🌟 参与者名单：")
                for focus_area, nicknames in focus_area_groups.items():
                    response_lines.append(f"\n{focus_area}：")
                    for nickname in nicknames:
                        response_lines.append(f"- {nickname}")
                
                response_lines.append("\n\n祝愿大家在本期活动中收获满满！🎉")
                
                return "\n".join(response_lines)

            except Exception as e:
                error_msg = f"接龙结束失败：更新数据时发生错误 - {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.db.rollback()
                return error_msg

        except Exception as e:
            error_msg = f"接龙结束失败：处理命令时发生错误 - {str(e)}"
            logger.error(error_msg, exc_info=True)
            if 'session' in dir(self.db):
                self.db.rollback()
            return error_msg

    def handle_checkin(self, message_content: str, chat_id: str) -> str:
        """处理打卡消息"""
        logger.info(f"开始处理打卡消息: {message_content}")
        
        # 解析打卡信息
        pattern = r'#打卡\s+([\w-]+)\s+(.+)(?:\n|$)'
        match = re.search(pattern, message_content)

        if not match:
            error_msg = "📝 打卡格式不正确\n正确格式：#打卡 昵称 工作内容\n示例：#打卡 张三 完成了登录功能的开发"
            logger.info(f"打卡格式错误: {message_content}")
            return error_msg

        nickname = match.group(1)
        content = match.group(2).strip()

        # 检查工作内容
        if len(content) < 2:
            error_msg = "📝 打卡内容太短，请详细描述您的工作内容"
            logger.info(f"打卡内容过短: {content}")
            return error_msg
        
        if len(content) > 500:
            error_msg = "📝 打卡内容过长，请控制在500字以内"
            logger.info(f"打卡内容过长: {len(content)}字")
            return error_msg

        # 获取当前活动期数
        current_period = self.db.query(Period)\
            .filter(Period.status == '进行中')\
            .first()

        if not current_period:
            error_msg = "⚠️ 当前没有进行中的活动期数，请等待新的活动开始"
            logger.info("打卡失败：没有进行中的活动期数")
            return error_msg

        # 查找用户报名记录
        signup = self.db.query(Signup)\
            .filter(Signup.period_id == current_period.id)\
            .filter(Signup.nickname == nickname)\
            .first()

        if not signup:
            error_msg = f"⚠️ 未找到昵称为 {nickname} 的报名记录\n请先完成接龙或检查昵称是否正确"
            logger.info(f"打卡失败：未找到报名记录 - {nickname}")
            return error_msg

        try:
            # 检查是否重复打卡
            today = datetime.now().date()
            existing_checkin = self.db.query(Checkin)\
                .filter(Checkin.signup_id == signup.id)\
                .filter(Checkin.checkin_date == today)\
                .first()
            
            if existing_checkin:
                error_msg = "⚠️ 您今天已经打过卡了，明天再来吧！"
                logger.info(f"打卡失败：重复打卡 - {nickname}")
                return error_msg

            # 获取用户所有打卡记录
            user_checkins = self.db.query(Checkin)\
                .filter(Checkin.signup_id == signup.id)\
                .order_by(Checkin.checkin_date)\
                .all()

            # 创建打卡记录
            logger.info(f"创建打卡记录 - 用户: {nickname}, 内容长度: {len(content)}")
            checkin = Checkin(
                signup_id=signup.id,
                nickname=nickname,
                checkin_date=today,
                content=content,
                checkin_count=len(user_checkins) + 1
            )
            
            try:
                self.db.add(checkin)
                self.db.commit()
                logger.info(f"打卡记录添加成功 - 用户: {nickname}, 第 {len(user_checkins) + 1} 次打卡")
            except Exception as db_error:
                logger.error(f"数据库更新失败: {str(db_error)}")
                self.db.rollback()
                return "❌ 打卡失败，请稍后重试"

            # 生成打卡反馈
            try:
                logger.info(f"开始生成AI反馈 - 用户: {nickname}")
                retry_count = 3  # 最大重试次数
                ai_feedback = None
                
                # 综合目标：项目名称、项目介绍、本期目标
                combined_goals = f"项目名称：{signup.focus_area}\n项目介绍：{signup.introduction}\n本期目标：{signup.goals}"
                
                while retry_count > 0:
                    try:
                        ai_feedback = generate_ai_feedback(
                            db=self.db,
                            signup_id=signup.id,
                            nickname=nickname,
                            goals=combined_goals,
                            content=content,
                            checkin_count=len(user_checkins) + 1
                        )
                        if ai_feedback:
                            break
                    except Exception as e:
                        logger.error(f"生成AI反馈失败 (还剩{retry_count-1}次重试): {str(e)}")
                        retry_count -= 1
                        if retry_count > 0:
                            # 短暂等待后重试
                            time.sleep(1)
                
                if ai_feedback:
                    return ai_feedback
                else:
                    return f"✨ 打卡成功！\n📝 第 {len(user_checkins) + 1}/21 次打卡\n\n继续加油，你的每一步进展都很棒！ 🌟"
                
            except Exception as ai_error:
                logger.error(f"AI反馈生成失败: {str(ai_error)}")
                return f"✨ 打卡成功！\n📝 第 {len(user_checkins) + 1}/21 次打卡\n\n继续加油，你的每一步进展都很棒！ 🌟"
            
        except Exception as e:
            error_msg = f"打卡失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            self.db.rollback()
            return "❌ 打卡失败，请稍后重试或联系管理员"

    def handle_activity_end(self, chat_id: str) -> str:
        """处理活动结束，综合目标为项目名称+项目介绍+本期目标"""
        try:
            # 获取当前进行中的活动期数
            current_period = self.db.query(Period)\
                .filter(Period.status == '进行中')\
                .first()

            if not current_period:
                error_msg = "活动结束失败：没有正在进行的活动"
                logger.info(error_msg)
                return error_msg

            try:
                # 获取所有报名记录
                signups = self.db.query(Signup)\
                    .filter(Signup.period_id == current_period.id)\
                    .all()

                # 收集每个开发者的打卡统计和成果
                developer_stats = []
                qualified_developers = []  # 达标开发者
                
                for signup in signups:
                    # 获取该开发者的所有打卡记录
                    checkins = self.db.query(Checkin)\
                        .filter(Checkin.signup_id == signup.id)\
                        .order_by(Checkin.checkin_date)\
                        .all()
                    
                    checkin_count = len(checkins)
                    
                    # 检查是否达标（7次有效打卡）
                    is_qualified = checkin_count >= 7
                    
                    # 生成开发者的AI表扬语
                    praise = ""
                    if checkin_count > 0:
                        retry_count = 3  # 最大重试次数
                        while retry_count > 0:
                            try:
                                # 综合目标：项目名称、项目介绍、本期目标
                                combined_goals = f"项目名称：{signup.focus_area}\n项目介绍：{signup.introduction}\n本期目标：{signup.goals}"
                                # 使用最后一次打卡内容生成表扬
                                latest_checkin = checkins[-1]
                                praise = generate_ai_feedback(
                                    db=self.db,
                                    signup_id=signup.id,
                                    nickname=signup.nickname,
                                    goals=combined_goals,
                                    content=latest_checkin.content,
                                    checkin_count=checkin_count,
                                    is_final=True  # 标记这是结束总结
                                )
                                if praise:
                                    praise = praise.split('\n\n')[-1]  # 只取AI反馈部分
                                    break
                            except Exception as e:
                                logger.error(f"生成AI表扬失败 (还剩{retry_count-1}次重试): {str(e)}")
                                retry_count -= 1
                                if retry_count == 0:
                                    praise = "很棒的表现！期待下次再见！"  # 默认表扬语
                    
                    # 构建更详细的证书内容，侧重分析而非简单拼接
                    if checkin_count > 0:
                        # 分析用户的目标和进展
                        progress_percentage = (checkin_count/21*100)
                        
                        # 构建更有深度的证书内容
                        if "前端" in signup.focus_area.lower() or "web" in signup.focus_area.lower():
                            tech_area = "Web开发领域"
                        elif "后端" in signup.focus_area.lower() or "java" in signup.focus_area.lower() or "python" in signup.focus_area.lower():
                            tech_area = "后端开发领域"
                        elif "运营" in signup.focus_area.lower() or "营销" in signup.focus_area.lower():
                            tech_area = "运营领域"
                        elif "设计" in signup.focus_area.lower() or "ui" in signup.focus_area.lower():
                            tech_area = "设计领域"
                        elif "算法" in signup.focus_area.lower() or "ai" in signup.focus_area.lower() or "数据" in signup.focus_area.lower():
                            tech_area = "数据与AI领域"
                        else:
                            tech_area = "技术领域"
                            
                        # 构建证书内容
                        cer_content = f"在为期21天的{current_period.period_name}学习活动中，{signup.nickname}在{tech_area}展现出了非凡的学习热情与专注度。"
                        
                        # 根据打卡次数生成不同评价
                        if checkin_count >= 14:
                            cer_content += f"完成了{checkin_count}/21次打卡，展现出卓越的坚持力与执行力，"
                        elif checkin_count >= 7:
                            cer_content += f"完成了{checkin_count}/21次打卡，表现出良好的学习习惯与自律精神，"
                        else:
                            cer_content += f"完成了{checkin_count}/21次打卡，迈出了技术成长的重要一步，"
                        
                        # 分析用户目标类型
                        goal_keywords = f"{signup.focus_area} {signup.introduction} {signup.goals}".lower()
                        if "学习" in goal_keywords or "掌握" in goal_keywords or "了解" in goal_keywords:
                            goal_type = "技能提升"
                        elif "开发" in goal_keywords or "完成" in goal_keywords or "实现" in goal_keywords:
                            goal_type = "项目攻坚"
                        elif "优化" in goal_keywords or "改进" in goal_keywords:
                            goal_type = "系统优化"
                        else:
                            goal_type = "能力拓展"
                            
                        # 继续构建内容
                        cer_content += f"在{goal_type}方面取得了实质性进展。"
                        
                        # 添加AI评语，但不单独标记为"导师评语"
                        cer_content += f"\n\n{praise}"
                        
                        # 达标状态，不提及百分比
                        if checkin_count >= 7:
                            cer_content += f"\n\n🏆 恭喜达成本期活动达标要求！你的坚持与成长令人钦佩，期待未来技术之路上继续看到你的身影！"
                        else:
                            cer_content += f"\n\n💪 你已迈出了重要的几步！每一次打卡都是成长的见证，期待下一期活动中你的精彩表现！"
                    else:
                        cer_content = f"{current_period.period_name}活动期间，{signup.nickname}在{signup.focus_area}领域展现了学习的热情，"
                        cer_content += "虽然尚未开始打卡记录，但技术成长是一场长期的马拉松。期待在下一次活动中，看到你的精彩表现与持续进步！"

                    # 存储证书数据
                    try:
                        # 先检查是否已存在
                        existing_cert = self.db.query(Certificate).filter(
                            Certificate.period_id == current_period.id,
                            Certificate.nickname == signup.nickname
                        ).first()
                        
                        if existing_cert:
                            # 更新现有记录
                            existing_cert.cer_content = cer_content
                            logger.info(f"更新证书数据 - 用户: {signup.nickname}")
                        else:
                            # 创建新记录
                            certificate = Certificate(
                                period_id=current_period.id,
                                nickname=signup.nickname,
                                cer_content=cer_content
                            )
                            self.db.add(certificate)
                            logger.info(f"创建证书数据 - 用户: {signup.nickname}")
                    except Exception as cert_error:
                        logger.error(f"存储证书数据失败: {str(cert_error)}", exc_info=True)
                            
                    developer_stats.append({
                        'nickname': signup.nickname,
                        'focus_area': signup.focus_area,
                        'checkin_count': checkin_count,
                        'is_qualified': is_qualified,
                        'praise': praise
                    })
                    
                    if is_qualified:
                        qualified_developers.append(signup.nickname)

                # 更新活动状态为已结束
                current_period.status = '已结束'
                self.db.commit()
                logger.info(f"成功更新活动期数 {current_period.period_name} 状态为已结束")

                # 构建响应消息
                response_lines = [
                    f"✨ {current_period.period_name}期活动圆满结束！",
                    "感谢大家这段时间的倾情付出与坚持不懈！每一次打卡都见证了我们共同成长的足迹。\n"
                ]
                
                # 修改开发者统计信息部分，加入活动总结感慨
                response_lines.append("📊 这21天的旅程告诉我们，成长不在于速度，而在于坚持。无论你完成了多少次打卡，每一步都是向目标迈进的珍贵经历。")
                
                response_lines.append("🏆 为纪念你在本期的成长历程，我们为每位参与者准备了专属电子证书！")
                response_lines.append("💫 访问 https://superb-clafoutis-c8572b.netlify.app/ 输入你的昵称，即可查看为你量身定制的成长档案，记录你的每一步进步与收获！")
                
                # 添加达标情况说明，保持文风一致
                response_lines.append("\n✨ 在这场技术与毅力的共舞中，我们欣喜地看到许多伙伴坚持到最后，完成了我们设定的挑战：")
                response_lines.append("🔍 21天内完成7次有效打卡并实现自定目标")
                
                if qualified_developers:
                    response_lines.append("\n🏆 本期达标开发者：")
                    for dev in qualified_developers:
                        response_lines.append(f"- {dev}")
                else:
                    response_lines.append("\n本期暂无达标开发者，继续加油！")
                
                # 添加奖励机制说明
                response_lines.extend([
                    "\n🌟 完成达标有机会获得：",
                    "1. 社区网站展示机会",
                    "2. 公众号专题报道机会",
                    "3. 创新项目Demo日展示机会"
                ])
                
                # 对未达标者的鼓励，保持与前面一致的文风
                if len(qualified_developers) < len(developer_stats):
                    response_lines.extend([
                        "\n💫 致每一位参与者：",
                        "技术成长是一场漫长的旅程，而非短暂的冲刺。",
                        "每个人都有自己独特的节奏与步调，而真正的价值在于我们一路积累的思考与坚持。",
                        "你的每一次打卡，都已在这条路上留下了坚实的足迹。"
                    ])
                
                # 更新结束语，保持文风一致
                response_lines.extend([
                    "\n🌈 感谢每一位用心前行的伙伴！",
                    "这不是终点，而是新征程的起点。",
                    "愿我们在技术的星辰大海中继续探索，下期再会！ 🚀"
                ])
                
                return "\n".join(response_lines)

            except Exception as e:
                error_msg = f"活动结束失败：更新状态时发生错误 - {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.db.rollback()
                return error_msg

        except Exception as e:
            if "EOF occurred in violation of protocol" in str(e):
                # 如果是 SSL 错误，回滚事务并返回错误消息
                self.db.rollback()
                return "服务异常，请重试"
            # 其他错误照常处理
            logger.error(f"处理活动结束时出错: {str(e)}")
            raise e

    def handle_mention(self, message_content: str, chat_id: str) -> str:
        """处理@机器人的消息"""
        try:
            logger.info(f"处理@消息: {message_content}")

            content = message_content.strip()

            # 判断是否@社区机器人
            is_mentioned_community_bot = False

            # 检查JSON格式的@消息（通过API发送）
            if "社区机器人" in content:
                is_mentioned_community_bot = True
            else:
                logger.info("消息@的不是社区机器人，而是其他用户")
                return None
            
            # 提取@后面的内容
            # 注意：飞书消息格式可能如 "@机器人 你好"，需要去除前面的@和机器人名称
            # 如果内容包含空格，取第一个空格后的所有内容作为实际问题
            if " " in content:
                actual_content = content.split(" ", 1)[1].strip()
            else:
                actual_content = "你好"  # 如果只有@没有其他内容，默认回复
            
            logger.info(f"提取的实际内容: {actual_content}")
            
            # 使用DeepSeek API生成回复
            ai_response = generate_ai_response(actual_content)
            if ai_response:
                logger.info(f"AI生成回复: {ai_response}")
                return ai_response
            else:
                # 如果AI生成失败，使用预设回复
                responses = [
                    f"你好呀！有什么我能帮到你的吗？😊",
                    f"嗨！我已经准备好为你服务啦！有什么需要帮忙的？✨",
                    f"很高兴收到你的消息！请问有什么我可以协助你的？🌟"
                ]
                response = random.choice(responses)
                
                # 添加结束语，增加热情度
                endings = [
                    "如果还有其他问题，随时告诉我哦！",
                    "希望我的回答对你有所帮助！",
                    "期待与你有更多的交流！"
                ]
                response += f"\n\n{random.choice(endings)} 😄"
                
                logger.info(f"生成回复: {response}")
                return response
            
        except Exception as e:
            logger.error(f"处理@消息失败: {str(e)}", exc_info=True)
            return "抱歉，我好像遇到了点小问题，但我很乐意继续为你服务！请再试一次或换个方式提问吧！🙏"

    def handle_ranking_publish(self, message_content: str, chat_id: str) -> str:
        """处理打卡排名公布请求"""
        try:
            logger.info(f"开始处理打卡排名公布请求: {message_content}")
            
            # 提取天数
            days = None
            if message_content.strip() in ['#3天打卡排名公布', '#7天打卡排名公布', '#14天打卡排名公布', '#21天打卡排名公布']:
                days = int(message_content.strip().lstrip('#').split('天')[0])
            else:
                import re
                match = re.match(r'#(\d+)天打卡排名公布', message_content.strip())
                if match:
                    days = int(match.group(1))
            
            if not days:
                return "排名公布失败：无效的天数"
            
            # 获取当前进行中的活动期数
            current_period = self.db.query(Period)\
                .filter(Period.status == '进行中')\
                .first()
                
            if not current_period:
                error_msg = "排名公布失败：没有正在进行的活动"
                logger.info(error_msg)
                return error_msg
                
            # 获取该期所有开发者的报名记录
            signups = self.db.query(Signup)\
                .filter(Signup.period_id == current_period.id)\
                .all()
                
            # 收集每个开发者的打卡统计
            developer_stats = []
            
            for signup in signups:
                # 获取该开发者的所有打卡记录数量
                checkin_count = self.db.query(Checkin)\
                    .filter(Checkin.signup_id == signup.id)\
                    .count()
                # 获取开发者的最新打卡记录
                latest_checkin = self.db.query(Checkin)\
                    .filter(Checkin.signup_id == signup.id)\
                    .order_by(Checkin.checkin_date.desc())\
                    .first()
                goal_feedback = "目标推进中"
                if latest_checkin and checkin_count > 0:
                    try:
                        # 生成目标进度反馈，综合目标和打卡内容
                        combined_goals = f"项目名称：{signup.focus_area}\n项目介绍：{signup.introduction}\n本期目标：{signup.goals}"
                        feedback = generate_ai_feedback(
                            db=self.db,
                            signup_id=signup.id,
                            nickname=signup.nickname,
                            goals=combined_goals,
                            content=latest_checkin.content,
                            checkin_count=checkin_count,
                            is_final=False,
                            is_ranking=True
                        )
                        if feedback:
                            goal_feedback = feedback.split('\n\n')[-1].strip()
                        else:
                            goal_feedback = "目标推进中"
                    except Exception as e:
                        logger.error(f"生成目标进度反馈失败: {str(e)}")
                        goal_feedback = "目标推进中"
                developer_stats.append({
                    'nickname': signup.nickname,
                    'focus_area': signup.focus_area,
                    'checkin_count': checkin_count,
                    'goal_feedback': goal_feedback
                })
                
            # 按打卡次数排序（降序）
            developer_stats.sort(key=lambda x: x['checkin_count'], reverse=True)
            
            # 生成排名消息
            message_lines = [
                f"✨ {current_period.period_name}期活动第{days}天打卡排行榜",
                f"📊 截至目前的打卡排名：\n"
            ]
            
            # 添加排名信息
            top_count = 0
            for i, dev in enumerate(developer_stats):
                if i < 10 and dev['checkin_count'] > 0:
                    message_lines.append(f"{i+1}. {dev['nickname']} ({dev['focus_area']}) - {dev['checkin_count']}次打卡")
                    if i < 5 and dev['goal_feedback']:
                        message_lines.append(f"   目标进度: {dev['goal_feedback']}")
                    top_count += 1
                else:
                    break
            
            # 激励与表扬内容
            if top_count > 0:
                message_lines.extend([
                    f"\n🎉 恭喜以上{top_count}位小伙伴登上本期打卡榜！你们的坚持和努力值得点赞！",
                    "💪 没有上榜的小伙伴也不要气馁，坚持每天打卡，进步就在路上！",
                    "每一次打卡，都是成长的见证。让我们一起加油，迎接更好的自己！"
                ])
            else:
                message_lines.append("💪 目前还没有有效打卡记录，快来成为第一个上榜的小伙伴吧！")
            
            # 保留打卡格式说明
            message_lines.append("\n📝 打卡格式: #打卡 你的昵称 工作内容")
            
            return "\n".join(message_lines)
            
        except Exception as e:
            error_msg = f"排名公布失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return "❌ 排名公布失败，请稍后重试或联系管理员"

    def handle_checkin_start(self, chat_id: str) -> str:
        """处理打卡开始指令，欢迎用户参与打卡活动"""
        try:
            logger.info("开始处理打卡开始指令")
            
            # 获取当前进行中的活动期数
            current_period = self.db.query(Period)\
                .filter(Period.status == '进行中')\
                .first()
                
            if not current_period:
                error_msg = "打卡开始失败：没有正在进行的活动期数"
                logger.info(error_msg)
                return error_msg
                
            # 获取该期所有开发者的报名记录
            signups = self.db.query(Signup)\
                .filter(Signup.period_id == current_period.id)\
                .all()
                
            if not signups:
                error_msg = "打卡开始失败：未找到任何报名记录"
                logger.info(error_msg)
                return error_msg
            
            # 收集开发者信息和项目信息
            developers = []
            projects = {}
            
            for signup in signups:
                developers.append(signup.nickname)
                
                # 整理项目信息，按项目分组
                if signup.focus_area not in projects:
                    projects[signup.focus_area] = []
                projects[signup.focus_area].append({
                    'nickname': signup.nickname,
                    'introduction': signup.introduction,
                    'goals': signup.goals
                })
            
            # 构建欢迎消息
            message_lines = [
                f"🚀 {current_period.period_name}期打卡活动正式开始啦！",
                "欢迎每一位热情的开发者加入我们的21天技术成长挑战！👏\n"
            ]
            
            # 参与者概览
            message_lines.append(f"📌 本期共有 {len(developers)} 位开发者参与，让我们一起努力实现目标！")
            message_lines.append("每位开发者都带着精彩的项目和清晰的目标，这将是一场激动人心的技术之旅！\n")
            
            # 项目展示
            message_lines.append("🌟 本期项目概览：")
            for project_name, members in projects.items():
                message_lines.append(f"\n📍 {project_name}:")
                for i, member in enumerate(members, 1):
                    if i <= 3:  # 每个项目最多展示前3位成员
                        message_lines.append(f"   👤 {member['nickname']} - {member['introduction'][:30]}{'...' if len(member['introduction']) > 30 else ''}")
                if len(members) > 3:
                    message_lines.append(f"   ...以及其他 {len(members)-3} 位开发者")
            
            # 打卡规则
            message_lines.extend([
                "\n✅ 打卡规则与奖励：",
                "1️⃣ 打卡格式：#打卡 昵称 今日完成内容",
                "2️⃣ 21天内完成7次有效打卡即达标",
                "3️⃣ 达标可获得：专属成长奖状",
                "4️⃣ 表现优秀者有机会额外奖励"
            ])
            
            # 打卡激励
            message_lines.extend([
                "\n💬 不要担心进度比别人慢，重要的是保持前进！",
                "每一次打卡都是一次成长，每一天的坚持都在塑造更好的自己！",
                "社区导师将定期为大家提供专业反馈，帮助你更高效地实现目标。"
            ])
            
            # 补充说明链接
            message_lines.extend([
                "\n📋 查看详细报名数据与活动指南：",
                "https://hackathonweekly.feishu.cn/wiki/Q4Pwwk7S8iCl5skmk26cgu4Vnqh"
            ])
            
            # 结束语
            message_lines.extend([
                "\n🔥 让我们一起开启这段精彩的技术成长之旅吧！",
                "每一行代码都是进步，每一次思考都是成长。",
                "期待看到大家在项目中的精彩表现！加油！💪"
            ])
            
            return "\n".join(message_lines)
            
        except Exception as e:
            error_msg = f"处理打卡开始指令失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"❌ 打卡开始失败，请稍后重试或联系管理员。错误：{str(e)}"

    def handle_ranking_publish_latest(self, chat_id: str) -> str:
        """处理#最新打卡排名公布指令，自动统计当前天数"""
        try:
            logger.info("开始处理#最新打卡排名公布请求")
            # 获取当前进行中的活动期数
            current_period = self.db.query(Period)\
                .filter(Period.status == '进行中')\
                .first()
            if not current_period:
                error_msg = "排名公布失败：没有正在进行的活动"
                logger.info(error_msg)
                return error_msg
            # 计算当前天数
            now = datetime.now()
            days = (now.date() - current_period.start_date.date()).days + 1
            # 构造伪指令，复用handle_ranking_publish
            fake_message = f"#{days}天打卡排名公布"
            return self.handle_ranking_publish(fake_message, chat_id)
        except Exception as e:
            error_msg = f"最新排名公布失败：{str(e)}"
            logger.error(error_msg, exc_info=True)
            return "❌ 最新排名公布失败，请稍后重试或联系管理员"
