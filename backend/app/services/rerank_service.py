"""阿里云百炼 Rerank 精排服务 (qwen3-rerank/gte-rerank)"""
import os
from typing import List, Tuple
import httpx
from app.config import get_settings

settings = get_settings()


class RerankService:
    """精排服务——对粗排结果重排序"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = settings.RERANK_MODEL
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
    ) -> List[Tuple[int, float, str]]:
        """
        精排并返回排序后的结果
        
        Returns:
            List of (original_index, score, document_text)
        """
        if not documents:
            return []

        # 使用 DashScope Rerank API (OpenAI 兼容格式)
        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": min(top_k, len(documents)),
                "return_documents": True,
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("output", {}).get("results", []):
                idx = item.get("index", 0)
                score = item.get("relevance_score", 0.0)
                doc = item.get("document", {}).get("text", documents[idx] if idx < len(documents) else "")
                results.append((idx, score, doc))

            return results

        except Exception as e:
            # 降级：返回原始顺序，用索引位置估算分数
            results = []
            for i, doc in enumerate(documents[:top_k]):
                score = 1.0 - (i * 0.1)  # 位置衰减分数
                results.append((i, max(score, 0.1), doc))
            return results


# 全局单例
rerank_service = RerankService()