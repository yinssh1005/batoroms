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
    "psp",
)

# 走 chdman `createdvd` 的 DVD 介质平台;其余 DISC_SYSTEMS 一律 `createcd`。
# PSP 的 UMD 镜像(ISO)也走 createdvd;PPSSPP 1.17+ 与 Batocera 均可读 CHD。
DVD_SYSTEMS: frozenset[str] = frozenset({"ps2", "psp"})

# 卡带类平台:单文件 ROM,chdman 不适用(不合并)。merge 对它们只做原样拷贝到 out/,
# 真正的整理在 rename(按游戏名改名)。gamecube 用 RVZ/ISO,同样不走 CHD。
CART_SYSTEMS: tuple[str, ...] = (
    "nes",
    "snes",
    "megadrive",
    "n64",
    "gamecube",
)

# 各卡带平台的 ROM 文件扩展名(用于 merge 拷贝与 rename 改名时识别产物)。
CART_EXTS: dict[str, frozenset[str]] = {
    "nes": frozenset({".nes", ".unf", ".unif", ".fds"}),
    "snes": frozenset({".sfc", ".smc", ".swc", ".fig", ".bs"}),
    "megadrive": frozenset({".md", ".gen", ".bin", ".smd", ".sgd"}),
    "n64": frozenset({".z64", ".n64", ".v64"}),
    "gamecube": frozenset({".iso", ".rvz", ".gcm", ".gcz", ".ciso"}),
}

# 本工具认得的全部平台(光盘 + 卡带)。
ALL_SYSTEMS: tuple[str, ...] = DISC_SYSTEMS + CART_SYSTEMS


def is_cart(system: str) -> bool:
    """该平台是否为卡带类(单文件 ROM,merge 走原样拷贝)。"""
    return system in CART_SYSTEMS

# Batocera 短名 → LaunchBox `Metadata.xml` 里的 `Platform` 字符串(可多个)。
# 取值按实际库核对,用于 rename 时按平台过滤。
SYSTEM_TO_LAUNCHBOX: dict[str, tuple[str, ...]] = {
    "psx": ("Sony Playstation",),
    "ps2": ("Sony Playstation 2",),
    "megacd": ("Sega CD",),
    "saturn": ("Sega Saturn",),
    "dreamcast": ("Sega Dreamcast",),
    "pcenginecd": ("NEC TurboGrafx-CD",),
    "neogeocd": ("SNK Neo Geo CD",),
    "3do": ("3DO Interactive Multiplayer",),
    "amigacd32": ("Commodore Amiga CD32",),
    "naomi": ("Sega Naomi",),
    "atomiswave": ("Sammy Atomiswave",),
    "pcfx": ("NEC PC-FX",),
    "fmtowns": ("Fujitsu FM Towns Marty",),
    "cdi": ("Philips CD-i",),
    "psp": ("Sony PSP",),
    # 卡带类平台。
    "nes": ("Nintendo Entertainment System",),
    "snes": ("Super Nintendo Entertainment System",),
    "megadrive": ("Sega Genesis", "Sega Mega Drive"),
    "n64": ("Nintendo 64",),
    "gamecube": ("Nintendo GameCube",),
}

# Batocera 短名 → redump.org 的 system 代码(用于 rename online 回退按序列号查标题)。
# 只收录能读出内部序列号的 platform(见 disc_meta.SERIAL_SYSTEMS)。
SYSTEM_TO_REDUMP: dict[str, str] = {
    "psx": "psx",
    "ps2": "ps2",
    "saturn": "ss",
    "dreamcast": "dc",
    "megacd": "mcd",
    "psp": "psp",
}


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
