"""从光盘原始镜像里读出游戏内部序列号(serial),供 rename 的 online 回退使用。

只读 `origin-roms/<system>/` 下的生镜像(.cue→.bin / .iso / .gdi→track;dreamcast 的 .zip 直接在包内读),
不动任何文件。
支持的 platform(其余返回 None,交回常规跳过):
- psx / ps2 :解析 ISO9660 找 `SYSTEM.CNF`,取 `BOOT`/`BOOT2` 的 `SLUS_005.94` → `SLUS-00594`。
- saturn    :IP.BIN("SEGA SEGASATURN")产品号在 +0x20(10 字节)。
- dreamcast :IP.BIN("SEGA SEGAKATANA")产品号在 +0x40(10 字节)。
- megacd    :"SEGADISCSYSTEM" 起的 MD 头,序列号在 +0x180。
- psp       :ISO9660 根目录 `UMD_DATA.BIN` 首字段(用 `|` 分隔)即 gamecode,如 `ULUS-10041`。

任何解析失败都返回 None,绝不抛出中断整批。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path, PurePosixPath

# 支持内部序列号读取的 platform(与 task-spec 一致)。
SERIAL_SYSTEMS: frozenset[str] = frozenset(
    {"psx", "ps2", "saturn", "dreamcast", "megacd", "psp"}
)

# ISO9660 逻辑扇区候选(扇区大小, 用户数据偏移):cooked 2048、raw mode1/mode2。
_FRAMES: tuple[tuple[int, int], ...] = (
    (2048, 0),
    (2352, 16),
    (2352, 24),
    (2448, 16),
    (2448, 24),
)

# SYSTEM.CNF 里的引导序列号,如 SLUS_005.94 / SCES_123.45。
_PSX_RE = re.compile(rb"([A-Za-z]{4})_(\d{3})\.(\d{2})")
# Mega Drive 头里的产品号,如 T-50015 / GM MK-xxxxx / GS-9099。
_MD_SERIAL_RE = re.compile(r"([A-Z]{1,2}-?\d{4,6}[A-Z]?)")
# PSP UMD gamecode,如 ULUS-10041 / ULES00151 / NPUG-80086(连字符可有可无)。
_PSP_RE = re.compile(rb"([A-Za-z]{4})-?(\d{5})")


def read_serial(system: str, primary: Path) -> str | None:
    """从一个游戏单元的主文件读出内部序列号;读不到返回 None。"""
    if system not in SERIAL_SYSTEMS:
        return None
    if primary.suffix.lower() == ".zip":
        return _zip_serial(system, primary)
    for data_file in _resolve_data_files(primary):
        if not data_file.is_file():
            continue
        try:
            if system in ("psx", "ps2"):
                serial = _psx_serial(data_file)
            elif system in _HEAD_PARSERS:
                serial = _HEAD_PARSERS[system](_read_head(data_file, _HEAD_BYTES))
            elif system == "psp":
                serial = _psp_serial(data_file)
            else:
                serial = None
        except OSError:
            serial = None
        if serial:
            return serial
    return None


def _resolve_data_files(primary: Path) -> list[Path]:
    """把主文件解析成待扫描的实际数据文件列表。"""
    ext = primary.suffix.lower()
    if ext in (".cue", ".gdi"):
        names = _referenced_tracks(ext, _read_text(primary))
        return [primary.parent / n for n in names] or [primary]
    return [primary]


def _referenced_tracks(ext: str, text: str) -> list[str]:
    """从 .cue / .gdi 文本里取出它引用的 track 文件名(相对主文件所在目录)。"""
    if ext == ".cue":
        return re.findall(r'FILE\s+"([^"]+)"', text, re.IGNORECASE)
    files: list[str] = []
    for line in text.splitlines()[1:]:
        m = re.search(r'"([^"]+)"', line)
        if m:
            files.append(m.group(1))
            continue
        for tok in line.split():
            if tok.lower().endswith((".bin", ".iso", ".raw", ".img")):
                files.append(tok)
    return files


def zip_primary_member(names: list[str]) -> str:
    """在 zip 成员名里选出唯一的光盘主文件(优先 .gdi/.cue,没有才看 .iso)。

    找不到或有多个时抛 ValueError(信息可直接进报告)。
    """
    files = [n for n in names if not n.endswith("/")]
    for exts in ((".gdi", ".cue"), (".iso",)):
        hits = [n for n in files if n.lower().endswith(exts)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError(f"zip 内有多个主文件:{', '.join(hits)}")
    raise ValueError("zip 内没有 .gdi/.cue/.iso 主文件")


def _zip_serial(system: str, archive: Path) -> str | None:
    """不解压,直接在 zip 里解析主文件与 track 头部读序列号(仅头部可解析的 Sega 系平台)。"""
    parser = _HEAD_PARSERS.get(system)
    if parser is None:
        return None
    try:
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            primary = zip_primary_member(names)
            ext = PurePosixPath(primary).suffix.lower()
            members = [primary]
            if ext in (".cue", ".gdi"):
                folder = PurePosixPath(primary).parent
                text = zf.read(primary).decode("utf-8", errors="replace")
                members = [
                    (folder / n).as_posix() for n in _referenced_tracks(ext, text)
                ] or [primary]
            existing = set(names)
            for member in members:
                if member not in existing:
                    continue
                with zf.open(member) as fp:
                    serial = parser(fp.read(_HEAD_BYTES))
                if serial:
                    return serial
    except (OSError, ValueError, zipfile.BadZipFile):
        return None
    return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ---- PSX / PS2:ISO9660 → SYSTEM.CNF ---------------------------------------


def _psx_serial(path: Path) -> str | None:
    content = _read_iso_file(path, "SYSTEM.CNF")
    if content is None:
        # 兜底:扫描文件头部(SYSTEM.CNF 一般很靠前)。
        content = _read_head(path, 4 << 20)
    m = _PSX_RE.search(content)
    if not m:
        return None
    prefix = m.group(1).decode("ascii").upper()
    return f"{prefix}-{m.group(2).decode()}{m.group(3).decode()}"


def _detect_frame(fp) -> tuple[int, int] | None:
    """按 PVD(逻辑扇区 16,标识 "CD001")探测扇区大小与数据偏移。"""
    for sector_size, data_off in _FRAMES:
        fp.seek(16 * sector_size + data_off)
        if fp.read(6)[1:6] == b"CD001":
            return sector_size, data_off
    return None


def _read_sectors(fp, sector_size: int, data_off: int, lba: int, nbytes: int) -> bytes:
    """按逻辑扇区读出 nbytes 用户数据(跨扇区自动拼接)。"""
    out = bytearray()
    sec = lba
    remaining = nbytes
    while remaining > 0:
        fp.seek(sec * sector_size + data_off)
        chunk = fp.read(min(2048, remaining))
        if not chunk:
            break
        out += chunk
        remaining -= len(chunk)
        sec += 1
    return bytes(out)


def _read_iso_file(path: Path, name: str) -> bytes | None:
    """在 ISO9660 根目录里找 name 文件并返回其内容;失败返回 None。"""
    target = name.upper()
    with path.open("rb") as fp:
        frame = _detect_frame(fp)
        if frame is None:
            return None
        sector_size, data_off = frame
        pvd = _read_sectors(fp, sector_size, data_off, 16, 2048)
        if len(pvd) < 190:
            return None
        root = pvd[156 : 156 + 34]
        root_lba = int.from_bytes(root[2:6], "little")
        root_size = int.from_bytes(root[10:14], "little")
        if not root_lba or not root_size or root_size > (16 << 20):
            return None
        dir_data = _read_sectors(fp, sector_size, data_off, root_lba, root_size)

        i = 0
        while i < len(dir_data):
            rlen = dir_data[i]
            if rlen == 0:
                nxt = ((i // 2048) + 1) * 2048
                if nxt <= i:
                    break
                i = nxt
                continue
            if i + 33 > len(dir_data):
                break
            name_len = dir_data[i + 32]
            fname = dir_data[i + 33 : i + 33 + name_len]
            nm = fname.split(b";")[0].decode("ascii", "replace").upper()
            if nm == target:
                ext_lba = int.from_bytes(dir_data[i + 2 : i + 6], "little")
                ext_size = int.from_bytes(dir_data[i + 10 : i + 14], "little")
                if not ext_lba or not ext_size or ext_size > (1 << 20):
                    return None
                return _read_sectors(fp, sector_size, data_off, ext_lba, ext_size)
            i += rlen
    return None


# ---- PSP：ISO9660 → UMD_DATA.BIN ----------------------------------------


def _psp_serial(path: Path) -> str | None:
    content = _read_iso_file(path, "UMD_DATA.BIN")
    if content is None:
        return None
    # 首字段(遇 `|` 截断)即 gamecode;容错地直接在整段上正则。
    head = content.split(b"|", 1)[0]
    m = _PSP_RE.search(head) or _PSP_RE.search(content)
    if not m:
        return None
    return f"{m.group(1).decode('ascii').upper()}-{m.group(2).decode()}"


# ---- Sega 系：IP.BIN / MD 头 ------------------------------------------------


def _read_head(path: Path, nbytes: int) -> bytes:
    with path.open("rb") as fp:
        return fp.read(nbytes)


def _sega_product(head: bytes, signature: bytes, offset: int, length: int = 10) -> str | None:
    """在文件头里定位 Sega IP.BIN 签名,取其 +offset 处的产品号。"""
    idx = head.find(signature)
    if idx < 0:
        return None
    raw = head[idx + offset : idx + offset + length]
    text = raw.decode("ascii", "replace").strip().strip("\x00").strip()
    return text or None


def _megacd_serial(head: bytes) -> str | None:
    """Mega CD:"SEGADISCSYSTEM" 起 +0x180 的序列号字段里提取产品号。"""
    idx = head.find(b"SEGADISCSYSTEM")
    if idx < 0:
        return None
    field = head[idx + 0x180 : idx + 0x180 + 16].decode("ascii", "replace")
    m = _MD_SERIAL_RE.search(field)
    return m.group(1) if m else None


# 只看文件头部即可解析的平台:头部字节 → 序列号。
_HEAD_BYTES = 0x20000
_HEAD_PARSERS = {
    "saturn": lambda head: _sega_product(head, b"SEGA SEGASATURN", 0x20),
    "dreamcast": lambda head: _sega_product(head, b"SEGA SEGAKATANA", 0x40),
    "megacd": _megacd_serial,
}
