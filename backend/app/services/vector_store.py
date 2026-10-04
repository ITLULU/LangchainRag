"""向量库服务——Chroma (dev) / Qdrant (prod) 统一接口"""
import os
from typing import List, Dict, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.config import get_settings

settings = get_settings()


class DashScopeEmbeddings(Embeddings):
    """LangChain 兼容的 DashScope Embedding 包装"""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        from app.services.embedding_service import embedding_service
        return embedding_service.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        from app.services.embedding_service import embedding_service
        return embedding_service.embed_query(text)


class VectorStoreService:
    """向量库抽象层——管理 Chroma/Qdrant collections"""

    def __init__(self):
        self._embeddings = DashScopeEmbeddings()
        persist_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            settings.CHROMA_PERSIST_DIR,
        )

    def get_collection(self, collection_name: str) -> Chroma:
        """获取指定 knowledge base 的向量 collection"""
        persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
        return Chroma(
            collection_name=collection_name,
            embedding_function=self._embeddings,
            persist_directory=persist_dir,
        )

    def add_documents(
        self,
        collection_name: str,
        documents: List[Document],
    ) -> List[str]:
        """向指定 collection 批量写入文档切片"""
        vector_store = self.get_collection(collection_name)
        ids = [doc.metadata.get("chunk_id", f"{collection_name}_{i}")
               for i, doc in enumerate(documents)]
        return vector_store.add_documents(documents, ids=ids)

    def similarity_search(
        self,
        collection_name: str,
        query: str,
        k: int = 20,
        filter_dict: Optional[Dict] = None,
    ) -> List[Document]:
        """向量相似度检索"""
        vector_store = self.get_collection(collection_name)
        if filter_dict:
            return vector_store.similarity_search(query, k=k, filter=filter_dict)
        return vector_store.similarity_search(query, k=k)

    def similarity_search_with_score(
        self,
        collection_name: str,
        query: str,
        k: int = 20,
        filter_dict: Optional[Dict] = None,
    ) -> List[tuple]:
        """带分数的向量检索"""
        vector_store = self.get_collection(collection_name)
        if filter_dict:
            return vector_store.similarity_search_with_score(query, k=k, filter=filter_dict)
        return vector_store.similarity_search_with_score(query, k=k)

    def delete_collection(self, collection_name: str) -> None:
        """删除 collection（删除知识库时调用）"""
        vector_store = self.get_collection(collection_name)
        vector_store.delete_collection()

    def delete_by_ids(self, collection_name: str, ids: List[str]) -> None:
        """按 ID 删除指定切片（版本替换用）"""
        vector_store = self.get_collection(collection_name)
        vector_store.delete(ids=ids)

    def search_multiple_collections(
        self,
        collection_names: List[str],
        query: str,
        k_per_collection: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[Document]:
        """并行检索多个 collection"""
        all_docs = []
        for name in collection_names:
            try:
                docs = self.similarity_search(name, query, k=k_per_collection, filter_dict=filter_dict)
                all_docs.extend(docs)
            except Exception:
                # 单个 collection 失败不中断整体检索
                continue
        return all_docs


# 全局单例
vector_store_service = VectorStoreService()