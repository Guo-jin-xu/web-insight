"""浏览器 Watchdog — 弹窗/对话框自动处理。

参考 browser-use 的 PopupsWatchdog 和 AboutBlankWatchdog。
"""

import logging

logger = logging.getLogger(__name__)


class PopupHandler:
    """自动处理 JavaScript 弹窗（alert/confirm/prompt）。

    在 BrowserManager.connect() 时注册，自动处理页面弹出的所有对话框：
    - alert/confirm/beforeunload → 自动接受
    - prompt → 自动取消
    - 其他类型 → 忽略
    """

    def __init__(self, page):
        self.page = page
        self._closed_popup_messages: list[str] = []
        self._handler_registered = False

    async def register(self) -> None:
        """注册弹窗处理 handler。"""
        if self._handler_registered:
            return

        async def handle_dialog(dialog):
            """处理弹窗：alert 和 confirm 自动接受，prompt 自动取消。"""
            dialog_type = dialog.type
            message = dialog.message
            logger.info(f"Dialog detected: {dialog_type} - '{message[:100]}'")

            if dialog_type in ("alert", "confirm", "beforeunload"):
                await dialog.accept()
                self._closed_popup_messages.append(f"[{dialog_type}] {message}")
                logger.info(f"Dialog accepted: {dialog_type}")
            elif dialog_type == "prompt":
                await dialog.dismiss()
                self._closed_popup_messages.append(f"[{dialog_type}] {message}")
                logger.info(f"Dialog dismissed: {dialog_type}")
            # 未知类型弹窗忽略，不添加到消息列表

        self.page.on("dialog", handle_dialog)
        self._handler_registered = True
        logger.debug("PopupHandler registered")

    def get_and_clear_messages(self) -> list[str]:
        """获取并清空已关闭的弹窗消息。"""
        messages = self._closed_popup_messages.copy()
        self._closed_popup_messages.clear()
        return messages

    def has_pending_popups(self) -> bool:
        """检查是否有未处理的弹窗消息。"""
        return len(self._closed_popup_messages) > 0


class PageCrashHandler:
    """检测页面崩溃并尝试恢复。"""

    def __init__(self, browser_manager):
        self.browser = browser_manager
        self._crash_count = 0

    async def check_and_recover(self) -> bool:
        """检查页面是否崩溃，尝试恢复。

        Returns:
            True 如果页面正常或恢复成功，False 如果连续崩溃超过限制。
        """
        try:
            # 尝试执行简单 JS 检测页面是否响应
            await self.browser.page.evaluate("1 + 1")
            return True
        except Exception:
            self._crash_count += 1
            logger.warning(f"Page appears crashed (attempt {self._crash_count})")
            if self._crash_count >= 3:
                logger.error("Page crashed 3 times, cannot recover")
                return False
            try:
                await self.browser.page.reload()
                logger.info("Page reloaded after crash")
                return True
            except Exception:
                return False