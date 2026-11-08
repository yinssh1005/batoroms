"""online 回退:用内部序列号去 redump.org 查正式游戏标题,供 rename 再照离线库拿 ID。

- 走 `redump.org/discs/system/<code>/quicksearch/<serial>/`,按 platform 服务端过滤。
- `urllib` + 浏览器 UA,自动遵循 `HTTP(S)_PROXY`(与 db.update_db 一致)。
- 带超时;任何网络/解析失败都返回 None,绝不抛出中断整批。
- 只取首个命中条目的标题,交回调用侧做去标签 + 归一化 + 离线库再照。
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

from batoroms.systems import SYSTEM_TO_REDUMP

_UA = "batoroms/0.1 (+https://batocera.org)"
# 结果表里指向具体 disc 的标题链接:<a href="/disc/NNN/">Title</a>。
_TITLE_RE = re.compile(r'href="/disc/\d+/"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)


def lookup_title(system: str, serial: str, timeout: float = 15.0) -> str | None:
    """用序列号在 redump 查首个命中标题;查不到 / 失败返回 None。"""
    code = SYSTEM_TO_REDUMP.get(system)
    if not code or not serial:
        return None
    url = f"http://redump.org/discs/system/{code}/quicksearch/{quote(serial)}/"
    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 (固定可信域名)
            body = resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 (网络层任何异常都回退,不中断批处理)
        return None

    m = _TITLE_RE.search(body)
    if not m:
        return None
    return _clean_title(m.group(1))


def _clean_title(raw: str) -> str | None:
    """清洗 redump 标题:取 <br> 前首行、去标签、解转义、折叠空白。"""
    first = re.split(r"<br\s*/?>", raw, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.sub(r"<[^>]+>", "", first)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None
