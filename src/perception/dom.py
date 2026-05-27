"""DOM 解析 — 纯函数，用 BeautifulSoup + lxml 快速提取网页信息。

与 VLM 视觉分析互补：DOM 更快更精确地提取文本和链接。
"""

import re

from bs4 import BeautifulSoup

SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "iframe", "aside"}
CONTENT_KEYWORDS = ["article", "content", "post", "main", "body", "text", "entry", "detail", "news"]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_page_text(html: str, max_length: int = 4000) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in SKIP_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    text = soup.get_text(separator="\n")
    lines = [_clean(line) for line in text.split("\n") if _clean(line)]
    result = "\n".join(lines)
    if len(result) > max_length:
        result = result[:max_length] + f"\n...(truncated, {len(result)} chars total)"
    return result


def extract_article(html: str, max_len: int = 5000) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_tag = soup.find("h1") or soup.find("title")
    if title_tag:
        title = _clean(title_tag.get_text())

    content = ""
    for keyword in CONTENT_KEYWORDS:
        for tag_name in ("div", "article", "section", "main"):
            for candidate in soup.find_all(tag_name):
                cls = candidate.get("class", [])
                cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
                node_id = candidate.get("id", "")
                if keyword in cls_str or keyword in node_id:
                    text = _clean(candidate.get_text())
                    if len(text) > len(content):
                        content = text

    if not content:
        body = soup.find("body")
        if body:
            content = _clean(body.get_text())

    if len(content) > max_len:
        content = content[:max_len] + f"\n...(truncated, {len(content)} chars original)"

    return {"title": title, "content": content, "length": len(content)}


def _is_nav_link(href: str) -> bool:
    return href.startswith(("#", "javascript:")) or "FORM=" in href or "scope=" in href


def extract_links(html: str, max_count: int = 50) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    i = 0
    for a in soup.find_all("a", href=True):
        text = _clean(a.get_text())
        href = a["href"].strip()
        if not text and not href:
            continue
        if _is_nav_link(href):
            continue
        if i >= max_count:
            break
        links.append({"index": i, "text": text or "(no text)", "href": href})
        i += 1
    return links


def extract_headings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    headings = []
    for level in ("h1", "h2", "h3"):
        for tag in soup.find_all(level):
            text = _clean(tag.get_text())
            if text:
                headings.append({"level": level, "text": text})
    return headings
