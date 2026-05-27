"""基准任务测试: bing 搜索 langchain菜鸟教程 → 进入 runoob 教程 → 总结。

使用方法:
    conda activate web-ai
    cd web-insight
    python -m pytest test/test_runoob.py -v -s
    python test/test_runoob.py
"""

import asyncio
import logging
import os

import pytest
from langchain_core.messages import HumanMessage

from src.agent.factory import create_browser_agent
from src.browser.manager import BrowserManager, ensure_chrome_running
from src.config.settings import settings

logger = logging.getLogger("test_runoob")

RESULT_FILE = "data/task_result.md"


def _cleanup_result():
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)


@pytest.fixture
async def browser():
    """确保 Chrome 运行并返回已连接的 BrowserManager。"""
    if not ensure_chrome_running():
        pytest.skip("Chrome 未安装或无法自动启动，请手动运行 chrome --remote-debugging-port=9222")

    _cleanup_result()
    bm = BrowserManager()
    await bm.connect()
    yield bm
    await bm.disconnect()


@pytest.mark.asyncio
async def test_search_langchain_tutorial(browser: BrowserManager):
    """测试: 搜索 langchain菜鸟教程 → 进入 runoob 教程 → done 总结。"""
    agent = create_browser_agent(browser, task_domain="bing.com")

    result = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="搜索 langchain菜鸟教程 site:runoob.com，打开教程链接，"
                    "提取教程内容，用 done 工具总结以下要点并结束: "
                    "LangChain简介、核心模块、环境准备、适用人群"
                )
            ]
        },
        config={"recursion_limit": settings.agent_recursion_limit},
    )

    messages = result.get("messages", [])
    tool_names = [getattr(m, "name", "?") for m in messages if getattr(m, "type", "") == "tool"]
    unique_tools = set(tool_names)
    logger.info(f"工具调用 ({len(tool_names)}): {list(unique_tools)}")

    # 检查 done 是否被调用（通过结果文件）
    done_called = os.path.exists(RESULT_FILE)

    # 验证核心工具
    assert "search" in unique_tools, "search 工具未被调用"
    assert any(t in unique_tools for t in ["extract_article_content", "extract_content"]), "内容提取未调用"

    if done_called:
        with open(RESULT_FILE, encoding="utf-8") as f:
            content = f.read()
        logger.info(f"done 工具已调用，结果: {len(content)} 字符")
        assert len(content) > 200, f"结果太短 ({len(content)} 字符)"
        assert "LangChain" in content, "结果未包含 LangChain"
    else:
        # done 可能因 NodeInterrupt 提前返回，检查消息中是否有 done
        done_in_msgs = "done" in unique_tools
        assert done_in_msgs, "done 工具未被调用 — 任务未正确终止"


async def _main():
    """独立运行入口。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if not ensure_chrome_running():
        print("Chrome 未运行。请手动启动: chrome --remote-debugging-port=9222")
        return

    _cleanup_result()
    bm = BrowserManager()
    await bm.connect()

    try:
        agent = create_browser_agent(bm, task_domain="bing.com")
        task = (
            "搜索 langchain菜鸟教程 site:runoob.com，打开教程链接，"
            "提取教程内容，用 done 工具总结核心要点并结束"
        )

        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=task)]},
            config={"recursion_limit": settings.agent_recursion_limit},
        )

        # 展示工具调用摘要
        messages = result.get("messages", [])
        for msg in messages:
            t = getattr(msg, "type", "?")
            if t == "tool":
                name = getattr(msg, "name", "?")
                content = getattr(msg, "content", "")[:200]
                print(f"[{name}] {content}")
            elif t == "ai" and msg.content and not getattr(msg, "tool_calls", []):
                text = msg.content[:200]
                if text.strip():
                    print(f"[AI] {text}...")

        # 展示 done 结果
        if os.path.exists(RESULT_FILE):
            print(f"\n===== DONE 结果 ({os.path.getsize(RESULT_FILE)} 字节) =====")
            with open(RESULT_FILE, encoding="utf-8") as f:
                print(f.read())
        else:
            print("\n警告: done 工具未被调用，检查 result 文件")

    finally:
        await bm.disconnect()


if __name__ == "__main__":
    asyncio.run(_main())
