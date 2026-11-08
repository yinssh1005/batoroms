"""Batocera 系统(平台)注册表。

本工具的核心是用 chdman 把光盘镜像合并成 `.chd`,所以这里只收录 chdman 适用的**光盘类**
平台;卡带类平台是单文件 ROM,不需要合并,不在本工具范围内。

短名采用 Batocera 官方 `es_systems.yml` 的叫法,等同于 `roms/<system>/` 的目录名。

后续功能(system→chdman createcd/createdvd 模式、system→LaunchBox 平台名等映射)会在此扩展。
"""

# chdman 适用的光盘(CD/DVD)类平台短名。
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
    "gamecube",
    "wii",
)
