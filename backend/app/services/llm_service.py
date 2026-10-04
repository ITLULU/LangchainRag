"""阿里云百炼 LLM 服务 (qwen-plus, 支持流式)"""
import os
from typing import AsyncIterator, List, Dict, Optional
from dashscope.aigc.generation import Generation
from app.config import get_settings

settings = get_settings()


class LLMService:
    """Qwen-plus 大模型调用服务"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = settings.LLM_MODEL
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        流式生成（SSE）
        """
        gen = Generation.call(
            model=self.model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens or 2048,
            api_key=self.api_key,
            result_format="message",
        )

        for event in gen:
            if event.status_code != 200:
                raise RuntimeError(f"LLM 调用失败: {event.code} - {event.message}")

            chunk_text = ""
            try:
                output = event.output
                if output and "choices" in output:
                    choice = output["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        chunk_text = choice["message"]["content"]
                    elif "delta" in choice:
                        chunk_text = choice["delta"].get("content", "")
            except (KeyError, IndexError, TypeError):
                pass

            if chunk_text:
                yield chunk_text

    def generate_sync(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """非流式生成（同步包装）"""
        resp = Generation.call(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or 2048,
            api_key=self.api_key,
            result_format="message",
        )

        if resp.status_code != 200:
            raise RuntimeError(f"LLM 调用失败: {resp.code} - {resp.message}")

        return resp.output["choices"][0]["message"]["content"]


# 全局单例
llm_service = LLMService()