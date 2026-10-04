"""阿里云百炼 text-embedding-v4 向量化服务"""
import os
from typing import List
from dashscope import TextEmbedding
from app.config import get_settings

settings = get_settings()


class EmbeddingService:
    """文本向量化服务，支持批量调用"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = settings.EMBEDDING_MODEL
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置，请在环境变量中设置")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化文本
        DashScope embedding batch 最大支持 10 条
        """
        embeddings = []
        batch_size = 10

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = TextEmbedding.call(
                model=self.model,
                input=batch,
                api_key=self.api_key,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Embedding 调用失败: {resp.code} - {resp.message}")

            for item in resp.output.get("embeddings", []):
                embeddings.append(item["embedding"])

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """单条查询向量化"""
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """文档批量向量化（与 embed_texts 别名）"""
        return self.embed_texts(texts)


# 全局单例
embedding_service = EmbeddingService()