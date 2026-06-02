"""记忆管理器 — ChromaDB 对话历史 + 站点经验文档。

两层存储:
- Layer 1: 对话历史（ChromaDB VectorStoreRetrieverMemory）
- Layer 2: 站点经验（Markdown 文件 + ChromaDB 元数据索引）
"""

from pathlib import Path

from chromadb import Client
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from src.config.settings import settings


class MemoryManager:
    """ChromaDB 记忆管理器。

    管理对话历史和站点经验文档的存储与检索。
    """

    def __init__(self):
        self._persist_dir = str(settings.resolve_path(settings.chroma_persist_dir))
        self._experience_dir = settings.resolve_path(settings.experience_dir)
        self._embed_fn = DefaultEmbeddingFunction()
        self._client = Client(ChromaSettings(is_persistent=True, persist_directory=self._persist_dir))

        self._chat_collection = self._client.get_or_create_collection("chat_history", embedding_function=self._embed_fn)
        self._experience_collection = self._client.get_or_create_collection(
            "site_experiences", embedding_function=self._embed_fn
        )

    def add_chat_message(self, content: str, role: str = "human", step: int = 0) -> None:
        """添加一条对话消息到历史。"""
        self._chat_collection.add(
            documents=[content],
            metadatas=[{"role": role, "step": step}],
            ids=[f"{role}_{step}"],
        )

    def search_chat(self, query: str, k: int = 5) -> list[str]:
        """检索相关对话历史。"""
        results = self._chat_collection.query(query_texts=[query], n_results=k)
        if results and results["documents"] and results["documents"][0]:
            return results["documents"][0]
        return []

    def search_experience(self, domain: str) -> str:
        """检索指定站点的操作经验。"""
        results = self._experience_collection.get(where={"domain": domain})
        if results and results["documents"]:
            return "\n\n".join(results["documents"])
        return ""

    def add_experience(self, domain: str, task_summary: str, detail: str) -> str:
        """写入站点操作经验。"""
        self._experience_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._experience_dir / f"{domain}.md"

        header = f"# {domain} 操作经验\n\n## 最近任务\n{task_summary}\n\n{detail}\n"

        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            existing = existing.replace(f"# {domain} 操作经验\n\n", "")
            header = f"# {domain} 操作经验\n\n{header[header.find('##'):]}\n---\n{existing}"

        file_path.write_text(header, encoding="utf-8")

        self._experience_collection.add(
            documents=[detail],
            metadatas=[{"domain": domain, "task": task_summary}],
            ids=[f"{domain}_{task_summary}"],
        )

        return str(file_path)


memory_manager = MemoryManager()
