import logging
import re
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class FeishuService:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        # 从环境变量中获取默认聊天群ID
        self.default_chat_id = os.getenv("DEFAULT_CHAT_ID")
        if not self.app_id or not self.app_secret:
            raise ValueError(
                "未找到飞书配置信息，请检查环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        self.access_token = None

    def get_access_token(self) -> str:
        """获取飞书访问令牌"""
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()

            if result.get("code") == 0:
                self.access_token = result.get("tenant_access_token")
                return self.access_token
            else:
                raise Exception(f"获取访问令牌失败: {result.get('msg')}")
        except Exception as e:
            logger.error(f"获取访问令牌时发生错误: {str(e)}")
            raise

    def extract_base_info(self, url: str) -> tuple:
        """从URL中提取多维表的base_id和table_id"""
        try:
            logger.info(f"开始解析URL: {url}")
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('/')
            query_params = parse_qs(parsed_url.query)

            # 查找base_id（从路径中查找最后一个非空部分）
            base_id = None
            for part in reversed(path_parts):
                if part and len(part) > 20:  # base_id 通常较长
                    base_id = part
                    break

            if not base_id:
                raise ValueError("未在URL中找到base_id")

            # 从查询参数中获取table_id
            table_id = query_params.get('table', [None])[0]
            if not table_id:
                # 如果URL中没有table参数，尝试从路径中查找
                for part in path_parts:
                    if part.startswith('tbl'):
                        table_id = part
                        break
                
                # 如果仍然没有找到，使用默认值
                if not table_id:
                    table_id = 'tblzscrkKqRba5r6'  # 使用默认的table_id
            
            logger.info(f"从URL中提取到 base_id: {base_id}, table_id: {table_id}")
            logger.info(f"URL解析结果 - 路径部分: {path_parts}")
            logger.info(f"URL解析结果 - 查询参数: {query_params}")

            return base_id, table_id
        except Exception as e:
            logger.error(f"解析URL时发生错误: {str(e)}")
            logger.error(f"URL: {url}")
            logger.error(f"解析后的URL对象: {parsed_url}")
            raise

    def fetch_signup_data(self, signup_link: str) -> List[Dict[str, Any]]:
        """获取接龙数据，适配新多维表结构，筛选开发者角色"""
        try:
            logger.info(f"开始获取接龙数据，链接: {signup_link}")

            if not self.access_token:
                logger.info("获取新的访问令牌")
                self.get_access_token()

            logger.info(f"使用访问令牌: {self.access_token[:10]}...")

            base_id, _ = self.extract_base_info(signup_link)
            logger.info(f"提取到的 base_id: {base_id}")

            # 首先获取多维表的表格列表
            list_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_id}/tables"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"获取表格列表，URL: {list_url}")
            list_response = requests.get(list_url, headers=headers)
            list_result = list_response.json()
            
            if list_result.get("code") != 0:
                error_msg = f"获取表格列表失败: {list_result.get('msg')} (错误码: {list_result.get('code')})"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            tables = list_result.get("data", {}).get("items", [])
            if not tables:
                error_msg = "未找到任何表格"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # 使用第一个表格的ID
            table_id = tables[0].get("table_id")
            logger.info(f"使用第一个表格的ID: {table_id}")

            # 构建API URL
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_id}/tables/{table_id}/records"
            params = {"page_size": 100}

            logger.info(f"准备请求URL: {url}")
            logger.info(f"请求参数: {params}")

            try:
                response = requests.get(url, headers=headers, params=params)
                logger.info(f"API响应状态码: {response.status_code}")
                response_text = response.text
                logger.info(f"API响应内容: {response_text[:500]}...")

                if not response.ok:
                    logger.error(f"API请求失败: 状态码 {response.status_code}")
                    logger.error(f"错误响应: {response_text}")
                    if response.status_code in [401, 403]:
                        logger.info("检测到认证错误，尝试重新获取访问令牌")
                        self.access_token = None
                        self.get_access_token()
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        response = requests.get(url, headers=headers, params=params)
                        logger.info(f"重试请求状态码: {response.status_code}")
                        response_text = response.text

                result = response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"发送请求时发生错误: {str(e)}")
                raise
            except ValueError as e:
                logger.error(f"解析JSON响应时发生错误: {str(e)}")
                logger.error(f"原始响应内容: {response_text}")
                raise

            if result.get("code") == 0:
                records = result.get("data", {}).get("items", [])
                logger.info(f"获取到 {len(records)} 条记录")

                signup_data = []
                for record in records:
                    fields = record.get("fields", {})
                    # 筛选角色为开发者
                    role = fields.get("您想做什么角色？", "")
                    if "开发者" not in str(role):
                        continue
                    nickname = fields.get("您的姓名/昵称", "").strip()
                    focus_area = fields.get("您计划在活动中开发的项目名称", "").strip()
                    introduction = fields.get("项目简介（100 字以内）", "").strip()
                    goals = fields.get("预期 21 天内要达成的目标！目标会在社群中公示哦，一起加油！", "").strip()
                    signup_time = fields.get("提交时间")
                    # 处理提交时间为datetime对象
                    if signup_time:
                        try:
                            # 飞书多维表一般为ISO格式
                            signup_time = datetime.fromisoformat(signup_time.replace('Z', '+00:00'))
                        except Exception:
                            signup_time = datetime.now()
                    else:
                        signup_time = datetime.now()
                    signup_data.append({
                        "nickname": nickname,
                        "focus_area": focus_area,
                        "introduction": introduction,
                        "goals": goals,
                        "signup_time": signup_time
                    })
                    logger.info(f"添加报名记录 - 昵称: {nickname}, 项目: {focus_area}, 目标: {goals}")
                logger.info(f"成功处理 {len(signup_data)} 条报名数据")
                return signup_data
            else:
                error_msg = f"获取数据失败: {result.get('msg')} (错误码: {result.get('code')})"
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取接龙数据时发生错误: {str(e)}", exc_info=True)
            raise

    def get_chat_id_for_period(self, period_id):
        """
        获取指定活动期数的聊天群ID
        目前简单实现，返回默认聊天群ID
        未来可扩展为从数据库中查询特定期数对应的聊天群ID
        """
        # 这里可以添加从数据库查询期数对应的聊天群ID的逻辑
        # 例如：根据period_id从数据库中查询对应的chat_id
        
        # 目前简单返回默认聊天群ID
        if self.default_chat_id:
            logger.info(f"使用默认聊天群ID: {self.default_chat_id}")
            return self.default_chat_id
        else:
            logger.warning("未找到默认聊天群ID，请在环境变量中设置 DEFAULT_CHAT_ID")
            return None
