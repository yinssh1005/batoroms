"""合成光盘镜像构造器,供测试在不下载真实 ROM 的情况下验证序列号解析。"""

from __future__ import annotations


def make_iso9660(serial_boot: str, *, sector_size: int = 2048, data_off: int = 0) -> bytes:
    """造一个最小 ISO9660 镜像:根目录下只有一个 SYSTEM.CNF,内容带给定 BOOT 行。

    serial_boot 如 ``SLUS_005.94``。支持 cooked(2048/0)与 raw(2352/16|24)帧。
    """
    content = f"BOOT = cdrom:\\{serial_boot};1\r\nVER = 1.0\r\n".encode("ascii")

    root_lba, dir_lba, file_lba = 16, 20, 21
    total_sectors = file_lba + 2
    img = bytearray(sector_size * total_sectors)

    def put(lba: int, data: bytes) -> None:
        base = lba * sector_size + data_off
        img[base : base + len(data)] = data

    # PVD:标识 CD001 + 根目录记录(指向 dir_lba)。
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    root = bytearray(34)
    root[0] = 34
    root[2:6] = dir_lba.to_bytes(4, "little")
    root[10:14] = (2048).to_bytes(4, "little")
    pvd[156 : 156 + 34] = root
    put(root_lba, pvd)

    # 根目录:一条 SYSTEM.CNF;1 记录。
    name = b"SYSTEM.CNF;1"
    rlen = 33 + len(name)
    if rlen % 2:
        rlen += 1
    rec = bytearray(rlen)
    rec[0] = rlen
    rec[2:6] = file_lba.to_bytes(4, "little")
    rec[10:14] = len(content).to_bytes(4, "little")
    rec[32] = len(name)
    rec[33 : 33 + len(name)] = name
    put(dir_lba, rec)

    put(file_lba, content)
    return bytes(img)


def make_saturn(product: str) -> bytes:
    h = bytearray(0x200)
    h[0:15] = b"SEGA SEGASATURN"
    h[0x20 : 0x20 + len(product)] = product.encode("ascii")
    h[0x60:0x6A] = b"GAME NAME "
    return bytes(h)


def make_dreamcast(product: str) -> bytes:
    h = bytearray(0x200)
    h[0:15] = b"SEGA SEGAKATANA"
    h[0x40 : 0x40 + len(product)] = product.encode("ascii")
    return bytes(h)


def make_megacd(serial_field: str) -> bytes:
    h = bytearray(0x300)
    h[0:14] = b"SEGADISCSYSTEM"
    h[0x100:0x110] = b"SEGA MEGA DRIVE "
    field = serial_field.encode("ascii")
    h[0x180 : 0x180 + len(field)] = field
    return bytes(h)
