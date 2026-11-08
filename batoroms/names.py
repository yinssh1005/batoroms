"""文件名解析与游戏名归一化工具,供 merge / rename 共用。"""

from __future__ import annotations

import re

# 盘号标记:(Disc 1) / Disc 2 / (Disk 1 of 3) / CD1 / (CD 2) 等。
DISC_RE = re.compile(
    r"\s*[\(\[]?\s*(?:disc|disk|cd)\s*#?\s*(\d+)(?:\s*of\s*\d+)?\s*[\)\]]?",
    re.IGNORECASE,
)

# 圆括号 / 方括号 标签组,如 (USA)、(En,Fr)、[!]、[T-En]。
_TAG_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")

# 归一化时要去掉的标点。
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def game_base(stem: str) -> str:
    """去掉盘号标记,得到同一多盘游戏共享的基名(保留区域等其它标签)。"""
    return DISC_RE.sub("", stem).strip().rstrip("-_").strip()


def disc_number(stem: str) -> int:
    """从文件名提取盘号用于排序;无盘号记为 1。"""
    m = DISC_RE.search(stem)
    return int(m.group(1)) if m else 1


def search_name(stem: str) -> str:
    """从文件名推断用于查库的游戏名:去掉盘号与所有 (…)/[…] 标签。"""
    name = DISC_RE.sub("", stem)
    name = _TAG_RE.sub("", name)
    return name.strip().rstrip("-_").strip()


def normalize(name: str) -> str:
    """归一化游戏名用于匹配:小写、去标点、折叠空白、去首词 "the"。"""
    text = _PUNCT_RE.sub(" ", name.lower())
    text = _WS_RE.sub(" ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    return text
