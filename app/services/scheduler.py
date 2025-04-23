import logging
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models.database import Period, Signup, Checkin, get_db
from .openai_service import generate_ai_feedback
from .feishu_service import FeishuService

# 配置日志
logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self, client):
        """初始化任务调度器"""
        self.client = client
        self.running = False
        self.scheduler_thread = None
        self.feishu_service = FeishuService()
        self.tasks = []
        self.setup_tasks()

    def setup_tasks(self):
        """设置定时任务"""
        # 晚上9点发布打卡排名任务
        self.tasks.append({
            'name': 'checkin_ranking',
            'func': self.publish_checkin_ranking,
            'check_time': self.is_ranking_time
        })

    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已经在运行中")
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self.run, daemon=True)
        self.scheduler_thread.start()
        logger.info("任务调度器已启动")

    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
        logger.info("任务调度器已停止")

    def run(self):
        """运行调度器主循环"""
        logger.info("调度器开始运行")
        
        last_check = datetime.now() - timedelta(minutes=1)  # 确保首次检查会立即执行
        
        while self.running:
            try:
                now = datetime.now()
                
                # 每分钟检查一次是否有任务需要执行
                if (now - last_check).total_seconds() >= 60:
                    self.check_tasks()
                    last_check = now
                
                # 短暂休眠以减少CPU占用
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"调度器运行出错: {str(e)}", exc_info=True)
                time.sleep(60)  # 出错后休眠一分钟再继续
    
    def check_tasks(self):
        """检查并执行需要运行的任务"""
        for task in self.tasks:
            try:
                if task['check_time']():
                    logger.info(f"执行任务: {task['name']}")
                    task['func']()
            except Exception as e:
                logger.error(f"执行任务 {task['name']} 出错: {str(e)}", exc_info=True)

    def is_ranking_time(self):
        """
        检查当前是否是发布排名的时间
        在活动期间的第3、7、14、21天的晚上9点（21:00-21:05）发布
        """
        now = datetime.now()
        
        # 只在21:00-21:05之间触发
        if now.hour != 21 or now.minute > 5:
            return False
            
        # 获取数据库连接
        db = next(get_db())
        try:
            # 获取当前进行中的活动期数
            current_period = db.query(Period)\
                .filter(Period.status == '进行中')\
                .first()
                
            if not current_period:
                logger.info("没有正在进行的活动，跳过排名发布")
                return False
                
            # 计算活动进行的天数
            days_passed = (now.date() - current_period.start_date.date()).days + 1
            
            # 检查是否是第3、7、14或21天
            if days_passed in [3, 7, 14, 21]:
                # 检查今天是否已经发布过排名（避免重复发送）
                # 这里可以添加一个简单的状态检查，例如使用文件或数据库标记
                # 为简化实现，我们假设在5分钟窗口内只会触发一次
                logger.info(f"今天是活动第{days_passed}天，需要发布排名")
                return True
                
            return False
                
        except Exception as e:
            logger.error(f"检查排名时间出错: {str(e)}", exc_info=True)
            return False
        finally:
            db.close()

    def publish_checkin_ranking(self):
        """发布打卡排名"""
        db = next(get_db())
        try:
            # 获取当前进行中的活动期数
            current_period = db.query(Period)\
                .filter(Period.status == '进行中')\
                .first()
                
            if not current_period:
                logger.info("没有正在进行的活动，跳过排名发布")
                return
                
            # 计算活动进行的天数
            now = datetime.now()
            days_passed = (now.date() - current_period.start_date.date()).days + 1
            
            logger.info(f"正在为{current_period.period_name}期活动第{days_passed}天生成排名")
            
            # 获取该期所有开发者的报名记录
            signups = db.query(Signup)\
                .filter(Signup.period_id == current_period.id)\
                .all()
                
            # 收集每个开发者的打卡统计
            developer_stats = []
            
            for signup in signups:
                # 获取该开发者的所有打卡记录数量
                checkin_count = db.query(func.count(Checkin.id))\
                    .filter(Checkin.signup_id == signup.id)\
                    .scalar() or 0
                    
                developer_stats.append({
                    'nickname': signup.nickname,
                    'focus_area': signup.focus_area,
                    'goals': signup.goals,
                    'checkin_count': checkin_count,
                    'signup_id': signup.id
                })
                
            # 按打卡次数排序（降序）
            developer_stats.sort(key=lambda x: x['checkin_count'], reverse=True)
            
            # 生成排名消息
            top_developers = developer_stats[:10]  # 取前10名
            
            message_lines = [
                f"✨ {current_period.period_name}期活动第{days_passed}天打卡排行榜",
                f"📊 截至目前的打卡排名前10名：\n"
            ]
            
            # 添加排名信息
            for i, dev in enumerate(top_developers):
                if i < 5:  # 前5名显示项目进度
                    # 获取该开发者的最新打卡记录
                    latest_checkin = db.query(Checkin)\
                        .filter(Checkin.signup_id == dev['signup_id'])\
                        .order_by(Checkin.checkin_date.desc())\
                        .first()
                        
                    # 生成进度反馈
                    progress_feedback = ""
                    if latest_checkin:
                        try:
                            # 使用与活动结束相同的反馈生成逻辑
                            progress_feedback = generate_ai_feedback(
                                db=db,
                                signup_id=dev['signup_id'],
                                nickname=dev['nickname'],
                                goals=dev['goals'],
                                content=latest_checkin.content,
                                checkin_count=dev['checkin_count'],
                                is_final=False,  # 非最终反馈
                                is_ranking=True  # 标记这是排名反馈
                            )
                            
                            # 只保留进度部分
                            if progress_feedback:
                                progress_feedback = progress_feedback.split('\n\n')[-1]
                        except Exception as e:
                            logger.error(f"生成进度反馈失败: {str(e)}")
                            progress_feedback = "继续加油！"
                    else:
                        progress_feedback = "暂无打卡记录"
                    
                    message_lines.append(f"{i+1}. {dev['nickname']} ({dev['focus_area']}) - {dev['checkin_count']}次打卡")
                    message_lines.append(f"   项目进度: {progress_feedback}")
                else:
                    # 后5名只显示基本信息
                    message_lines.append(f"{i+1}. {dev['nickname']} ({dev['focus_area']}) - {dev['checkin_count']}次打卡")
            
            # 添加激励信息
            message_lines.extend([
                "\n💪 无论排名如何，坚持才是最大的胜利！",
                "🌟 记得每天打卡，分享你的进步与收获！",
                "📝 打卡格式: #打卡 你的进展内容"
            ])
            
            # 发送消息到飞书群
            content = "\n".join(message_lines)
            logger.info(f"准备发送排名消息: {content}")
            
            # 获取该期活动的聊天群ID
            chat_id = self.feishu_service.get_chat_id_for_period(current_period.id)
            if not chat_id:
                logger.error("未找到活动对应的聊天群ID，无法发送排名消息")
                return
                
            # 发送消息
            self.send_message_to_chat(chat_id, content)
            logger.info(f"排名消息已发送到聊天群 {chat_id}")
            
        except Exception as e:
            logger.error(f"发布排名出错: {str(e)}", exc_info=True)
        finally:
            db.close()
            
    def send_message_to_chat(self, chat_id, content):
        """发送消息到飞书群"""
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        
        try:
            # 格式化消息内容
            content_json = {"text": content}
            content_str = json.dumps(content_json)
            
            # 创建消息请求
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content_str)
                    .build()
                )
                .build()
            )
            
            # 发送消息
            response = self.client.im.v1.message.create(request)
            
            if not response.success():
                logger.error(f"发送消息失败: {response.msg}, log_id: {response.get_log_id()}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"发送消息到聊天群出错: {str(e)}", exc_info=True)
            return False

# 导入放在最后以避免循环导入
import json 