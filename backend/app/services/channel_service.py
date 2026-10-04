"""双通道配置服务——定义 employee_kb / cs_agent 差异化行为"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ChannelConfig:
    """通道配置对象"""
    channel_type: str
    name: str
    description: str
    # 检索配置
    retrieval_top_n: int = 20
    rerank_top_k: int = 5
    reject_threshold: float = 0.35
    # 权限
    force_public_only: bool = False  # 对客通道强制只召回"公开"级别
    # 生成配置
    temperature: float = 0.1
    # 限流
    rate_limit_per_min: int = 20
    max_concurrent: int = 50
    # 审核
    content_moderation: bool = False
    # 拒答后动作
    refuse_to_handoff: bool = False  # True=转人工; False=拒答话术
    # Prompt
    system_prompt: str = ""

    @property
    def max_security_levels(self) -> List[str]:
        if self.force_public_only:
            return ["公开"]
        return ["公开", "内部", "机密"]


# ─── 预定义通道配置 ───

EMPLOYEE_KB_CONFIG = ChannelConfig(
    channel_type="employee_kb",
    name="企业员工手册",
    description="面向内部员工，重权限、重溯源、密级过滤",
    retrieval_top_n=20,
    rerank_top_k=5,
    reject_threshold=0.35,
    force_public_only=False,
    temperature=0.3,
    rate_limit_per_min=20,
    max_concurrent=50,
    content_moderation=False,
    refuse_to_handoff=False,
    system_prompt="""你是一个专业的企业内部知识助手。请严格基于以下参考资料回答员工的问题。

重要规则：
1. 必须基于提供的参考资料回答，每个观点末尾标注引用编号 [n]
2. 如果参考资料不足以回答问题，请明确告知"该问题暂无相关资料"，不要编造
3. 回答应结构清晰，可分点说明
4. 如涉及权限或保密信息，仅回答该用户有权知晓的内容

参考资料：
{context}

历史对话：
{history}

当前问题：{question}

请用专业、准确的中文回答：""",
)

CS_AGENT_CONFIG = ChannelConfig(
    channel_type="cs_agent",
    name="智能客服",
    description="面向 C 端客户，高并发、重体验、强制内容审核+转人工兜底",
    retrieval_top_n=20,
    rerank_top_k=3,  # 更少更精，追求速度
    reject_threshold=0.45,  # 更高阈值，宁可不答
    force_public_only=True,
    temperature=0.0,  # 求稳
    rate_limit_per_min=20,
    max_concurrent=200,
    content_moderation=True,
    refuse_to_handoff=True,  # 低置信转人工
    system_prompt="""你是一个友好、专业的智能客服助手。请严格基于以下参考信息为客户解答问题。

重要规则：
1. 必须基于提供的参考信息回答，每个观点末尾标注引用编号 [n]
2. 如果无法从参考信息中找到答案，请回复："很抱歉，我暂时无法回答这个问题，正在为您转接人工客服..."
3. 回答应简洁、亲切、通俗易懂，避免使用内部术语
4. 永远不要提供关于企业内部流程、员工信息、机密数据的任何信息

参考信息：
{context}

历史对话：
{history}

客户问题：{question}

请用亲切、简洁的中文回答：""",
)


class ChannelService:
    """通道配置管理器"""

    _configs: Dict[str, ChannelConfig] = {
        "employee_kb": EMPLOYEE_KB_CONFIG,
        "cs_agent": CS_AGENT_CONFIG,
    }

    @classmethod
    def get_config(cls, channel: str) -> ChannelConfig:
        """获取通道配置，不存在则返回默认 employee_kb"""
        config = cls._configs.get(channel)
        if config is None:
            config = EMPLOYEE_KB_CONFIG
        return config

    @classmethod
    def build_permission_filter(
        cls,
        channel: str,
        user_security_level: str,
        user_department: str,
    ) -> Optional[Dict]:
        """
        构建第二层 metadata 权限过滤条件
        cs_agent 通道强制只查询"公开"级别
        """
        config = cls.get_config(channel)
        security_levels = []

        if config.force_public_only:
            security_levels = ["公开"]
        else:
            # 按用户密级：用户能看到的 = 用户密级及以下
            level_order = {"公开": 1, "内部": 2, "机密": 3}
            user_level = level_order.get(user_security_level, 1)
            for k, v in level_order.items():
                if v <= user_level:
                    security_levels.append(k)

        # Chroma filter 格式
        filter_dict = {"security_level": {"$in": security_levels}}

        return filter_dict

    @classmethod
    def build_kb_filter_for_user(
        cls,
        channel: str,
        user_role: str,
        user_department: str,
        kb_ids: Optional[List[str]] = None,
    ) -> dict:
        """为数据库查询构建 KB 过滤条件"""
        config = cls.get_config(channel)
        filters = {"status": "active"}

        if config.force_public_only:
            filters["channel_type"] = "cs_agent"
            filters["visibility"] = "public"
        elif kb_ids:
            filters["id_in"] = kb_ids

        return filters


# 全局单例
channel_service = ChannelService()