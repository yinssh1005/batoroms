"""merge:把 origin-roms/<system>/ 下的镜像合并成 .chd 写到 out/<system>/。

- 主文件(一个游戏单元):`.cue` / `.gdi` / `.iso`,各合并成一个 chd(沿用源基名)。
- `.cdi`(DiscJuggler):chdman 不支持,跳过并提示先转 gdi/cue。
- 多盘游戏(文件名含 Disc/CD 盘号标记):每盘一个 chd,另生成 `.m3u` 供模拟器自动换盘。
- 已存在同名 chd 跳过(除非 --force);单个游戏失败不中断整批,最后打印报告。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from batoroms.names import disc_number, game_base
from batoroms.systems import DISC_SYSTEMS, chdman_mode, chdman_path

# 作为"游戏单元"主文件的扩展名。
PRIMARY_EXTS = {".cue", ".gdi", ".iso"}


@dataclass
class MergeReport:
    merged: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    skipped_cdi: list[str] = field(default_factory=list)
    m3u_written: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def print_summary(self) -> None:
        print(
            f"\n小结:合并 {len(self.merged)} 个,跳过已存在 {len(self.skipped_existing)} 个,"
            f"跳过 .cdi {len(self.skipped_cdi)} 个,生成 m3u {len(self.m3u_written)} 个,"
            f"失败 {len(self.failed)} 个。"
        )
        if self.failed:
            print("  失败:")
            for name, why in self.failed:
                print(f"    ! {name}: {why}")
        if self.skipped_cdi:
            print("  跳过的 .cdi(chdman 不支持,请先转成 gdi/cue):")
            for name in self.skipped_cdi:
                print(f"    - {name}")


def _run_chdman(mode: str, primary: Path, output: Path, force: bool) -> tuple[bool, str]:
    """调用 chdman 合并单个主文件。返回 (成功, 错误信息)。"""
    cmd = [chdman_path(), mode, "-i", str(primary), "-o", str(output)]
    if force:
        cmd.append("-f")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # 清掉可能残留的半成品。
        if output.exists():
            try:
                output.unlink()
            except OSError:
                pass
        msg = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, (msg[-1] if msg else f"chdman 返回码 {proc.returncode}")
    return True, ""


def _merge_system(
    system: str, origin: Path, out_base: Path, force: bool, report: MergeReport
) -> None:
    sys_dir = origin / system
    if not sys_dir.is_dir():
        return

    # 收集主文件,并挑出 .cdi 记为跳过。
    primaries: list[Path] = []
    for entry in sorted(sys_dir.iterdir()):
        if not entry.is_file():
            continue
        ext = entry.suffix.lower()
        if ext == ".cdi":
            report.skipped_cdi.append(f"{system}/{entry.name}")
        elif ext in PRIMARY_EXTS:
            primaries.append(entry)

    if not primaries:
        return

    out_dir = out_base / system
    out_dir.mkdir(parents=True, exist_ok=True)

    # 按去盘号基名分组。
    games: dict[str, list[Path]] = {}
    for primary in primaries:
        games.setdefault(game_base(primary.stem), []).append(primary)

    for base, discs in games.items():
        discs.sort(key=lambda p: disc_number(p.stem))
        produced: list[Path] = []  # 本游戏最终存在的 chd(用于 m3u)

        for primary in discs:
            output = out_dir / f"{primary.stem}.chd"
            label = f"{system}/{primary.name}"
            if output.exists() and not force:
                report.skipped_existing.append(label)
                produced.append(output)
                continue
            print(f"合并 {label} → {output.name} …")
            ok, why = _run_chdman(chdman_mode(system), primary, output, force)
            if ok:
                report.merged.append(label)
                produced.append(output)
            else:
                report.failed.append((label, why))

        # 多盘游戏:写 m3u(只列实际存在的盘)。
        if len(discs) > 1 and len(produced) > 1:
            m3u = out_dir / f"{base}.m3u"
            if m3u.exists() and not force:
                report.skipped_existing.append(f"{system}/{m3u.name}")
            else:
                m3u.write_text(
                    "".join(f"{p.name}\n" for p in produced), encoding="utf-8"
                )
                report.m3u_written.append(f"{system}/{m3u.name}")


def run_merge(
    base_dir: Path, system: str | None = None, force: bool = False
) -> MergeReport:
    """执行 merge。system 为 None 时处理所有已识别平台目录。"""
    base = base_dir.resolve()
    origin = base / "origin-roms"
    out_base = base / "out"

    if not origin.is_dir():
        raise FileNotFoundError(f"找不到 {origin};请先运行 `batoroms init`。")

    if system is not None:
        if system not in DISC_SYSTEMS:
            raise ValueError(
                f"平台 `{system}` 不在支持清单内(光盘类):{', '.join(DISC_SYSTEMS)}"
            )
        systems = [system]
    else:
        systems = list(DISC_SYSTEMS)

    report = MergeReport()
    for sys_name in systems:
        _merge_system(sys_name, origin, out_base, force, report)
    report.print_summary()
    return report
