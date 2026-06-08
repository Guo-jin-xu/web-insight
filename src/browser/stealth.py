"""浏览器防检测 — 注入反自动化检测脚本。

参考 browser-use 的 SecurityWatchdog 和防检测实践：
- 隐藏 webdriver 属性
- 覆盖 navigator 属性
- 处理权限请求
"""

STEALTH_SCRIPTS = [
    # 隐藏 webdriver 标记
    """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    """,
    # 覆盖 chrome.runtime（避免被检测为自动化）
    """
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
    """,
    # 覆盖 permissions（静默处理权限请求）
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    """,
    # 覆盖 plugins 和 languages（避免指纹检测）
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en']
    });
    """,
]


async def inject_stealth(page) -> None:
    """向页面注入防检测脚本。"""
    for script in STEALTH_SCRIPTS:
        try:
            await page.evaluate(script)
        except Exception:
            pass  # 某些脚本可能在某些页面无效，忽略


async def inject_permission_handling(context) -> None:
    """向浏览器上下文注入权限处理。"""
    await context.grant_permissions(["notifications", "geolocation"])


def get_stealth_scripts() -> list[str]:
    """获取所有防检测脚本。"""
    return STEALTH_SCRIPTS
