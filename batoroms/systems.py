"""Batocera 系统(平台)注册表与 chdman 定位。

本工具的核心是用 chdman 把光盘镜像合并成 `.chd`,所以这里只收录 chdman 适用的**光盘类**
平台;卡带类平台是单文件 ROM,不需要合并,不在本工具范围内。

短名采用 Batocera 官方 `es_systems.yml` 的叫法,等同于 `roms/<system>/` 的目录名。

后续功能(system→LaunchBox 平台名等映射)会在此扩展。
"""

from __future__ import annotations

import shutil
import sys
from importlib import resources
from pathlib import Path

# chdman 适用的光盘(CD/DVD)类平台短名。
# 注:GameCube/Wii 用 Dolphin 的 RVZ 格式,不支持 CHD,故不在此列。
DISC_SYSTEMS: tuple[str, ...] = (
    "psx",
    "ps2",
    "megacd",
    "saturn",
    "dreamcast",
    "pcenginecd",
    "neogeocd",
    "3do",
    "amigacd32",
    "naomi",
    "atomiswave",
    "pcfx",
    "fmtowns",
    "cdi",
)

# 走 chdman `createdvd` 的 DVD 介质平台;其余 DISC_SYSTEMS 一律 `createcd`。
DVD_SYSTEMS: frozenset[str] = frozenset({"ps2"})


def chdman_mode(system: str) -> str:
    """返回该平台应使用的 chdman 子命令:`createcd` 或 `createdvd`。"""
    return "createdvd" if system in DVD_SYSTEMS else "createcd"


def chdman_path() -> str:
    """定位 chdman 可执行文件。

    优先用随包分发的 `batoroms/vendor/chdman/chdman.exe`(Windows);
    非 Windows 或包内缺失时回退到 PATH 上的 `chdman`。找不到则抛 FileNotFoundError。
    """
    if sys.platform.startswith("win"):
        bundled = resources.files("batoroms").joinpath("vendor/chdman/chdman.exe")
        bundled_path = Path(str(bundled))
        if bundled_path.is_file():
            return str(bundled_path)

    found = shutil.which("chdman")
    if found:
        return found

    raise FileNotFoundError(
        "未找到 chdman:包内未带可用的 chdman,且 PATH 上也没有 `chdman` 命令。"
    )
