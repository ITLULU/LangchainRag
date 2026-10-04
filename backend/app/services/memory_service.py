"""会话记忆服务——基于 Redis（dev可降级为内存）"""
import json
import time
from typing import List, Dict, Optional
from collections import defaultdict

from app.config import get_settings

settings = get_settings()


class MemoryService:
    """
    会话记忆管理
    开发环境使用内存字典降级，生产环境使用 Redis
    """

    def __init__(self):
        self._redis = None
        # 内存降级存储
        self._memory_store: Dict[str, List[dict]] = defaultdict(list)
        self._expiry: Dict[str, float] = {}
        self._use_redis = False

        # 尝试连接 Redis
        try:
            import redis
            r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            r.ping()
            self._redis = r
            self._use_redis = True
        except Exception:
            print("[MemoryService] Redis 不可用，使用内存降级模式")

    def _clean_expired(self):
        """清理内存中已过期的会话"""
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if exp < now]
        for k in expired:
            self._memory_store.pop(k, None)
            self._expiry.pop(k, None)

    def get_history(self, conversation_id: str, max_rounds: int = None) -> List[Dict[str, str]]:
        """获取最近 N 轮对话历史"""
        if max_rounds is None:
            max_rounds = settings.MAX_MEMORY_ROUNDS

        if self._use_redis:
            key = f"conv:{conversation_id}"
            raw = self._redis.get(key)
            if raw:
                messages = json.loads(raw)
                return messages[-(max_rounds * 2):]  # user+assistant 各1条/轮
            return []
        else:
            self._clean_expired()
            messages = self._memory_store.get(conversation_id, [])
            return messages[-(max_rounds * 2):]

    def add_message(self, conversation_id: str, role: str, content: str):
        """添加一条消息到会话"""
        ttl = settings.CONVERSATION_TTL_HOURS * 3600

        if self._use_redis:
            key = f"conv:{conversation_id}"
            raw = self._redis.get(key)
            messages = json.loads(raw) if raw else []
            messages.append({"role": role, "content": content})
            # 只保留最近轮次
            max_messages = settings.MAX_MEMORY_ROUNDS * 2
            if len(messages) > max_messages:
                messages = messages[-max_messages:]
            self._redis.setex(key, ttl, json.dumps(messages, ensure_ascii=False))
        else:
            self._clean_expired()
            self._memory_store[conversation_id].append({"role": role, "content": content})
            self._expiry[conversation_id] = time.time() + ttl

    def format_history(self, conversation_id: str) -> str:
        """格式化历史对话为 Prompt 文本"""
        history = self.get_history(conversation_id)
        if not history:
            return "（暂无历史对话）"

        lines = []
        for msg in history:
            role_label = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

    def delete_conversation(self, conversation_id: str):
        """删除会话"""
        if self._use_redis:
            self._redis.delete(f"conv:{conversation_id}")
        else:
            self._memory_store.pop(conversation_id, None)
            self._expiry.pop(conversation_id, None)


# 全局单例
memory_service = MemoryService()