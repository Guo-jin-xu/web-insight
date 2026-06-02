"""文件读写工具 — write_file / read_file.

参考 Filesystem MCP 的接口设计。
"""

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from src.config.settings import settings


def create_file_tools() -> list:
    """创建文件读写工具。"""

    experience_dir = settings.resolve_path(settings.experience_dir)

    @tool
    async def write_file(
        path: Annotated[str, "文件路径（相对路径将写入 data/ 目录）"],
        content: Annotated[str, "文件内容"],
    ) -> str:
        """写入文件。用于保存总结、经验文档、提取的数据等。

        路径可以是:
        - 相对路径: 相对于项目 data/ 目录，如 'summary.md'
        - 绝对路径: 直接写入指定位置
        """
        p = Path(path)
        if not p.is_absolute():
            p = experience_dir.parent / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"文件已写入: {p} ({len(content)} 字符)"

    @tool
    async def read_file(
        path: Annotated[str, "要读取的文件路径"],
    ) -> str:
        """读取文件内容。用于查看之前保存的总结、经验文档等。"""
        p = Path(path)
        if not p.is_absolute():
            p = experience_dir.parent / p
        if not p.exists():
            return f"文件不存在: {p}"
        content = p.read_text(encoding="utf-8")
        if len(content) > 5000:
            content = content[:5000] + f"\n...(共 {len(content)} 字符，已截断)"
        return content

    return [write_file, read_file]
