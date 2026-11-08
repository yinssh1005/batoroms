"""rename:按 LaunchBox 离线库把 out/<system>/ 里的 chd 改成 <id>.chd,并更新多盘 m3u。

- 搜索名:默认从 chd 文件名去掉区域/版本标签与盘号;索引 .txt(`基名 | 游戏名`)若提供则优先。
- 单盘 → `<id>.chd`;多盘 → `<id> (Disc N).chd` + `<id>.m3u`(内容更新为新盘名)。
- 多候选/查不到/目标已存在/基名已是纯数字 → 跳过并记报告,不中断。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from batoroms.db import load_index
from batoroms.disc_meta import read_serial
from batoroms.names import DISC_RE, disc_number, game_base, normalize, search_name
from batoroms.online import lookup_title
from batoroms.systems import SYSTEM_TO_LAUNCHBOX

PRIMARY_EXTS = (".cue", ".gdi", ".iso")


@dataclass
class RenameReport:
    renamed: list[str] = field(default_factory=list)
    recovered: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    skipped_exists: list[str] = field(default_factory=list)
    skipped_already_id: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print(
            f"\n小结:改名 {len(self.renamed)} 个游戏(其中 online 回退救回 {len(self.recovered)} 个),"
            f"查不到 {len(self.not_found)} 个,"
            f"多候选跳过 {len(self.ambiguous)} 个,目标已存在 {len(self.skipped_exists)} 个,"
            f"已是 id 跳过 {len(self.skipped_already_id)} 个。"
        )
        for title, items in (
            ("online 回退救回", self.recovered),
            ("查不到(请用 --index 指定游戏名)", self.not_found),
            ("多候选,已跳过", self.ambiguous),
            ("目标已存在,已跳过", self.skipped_exists),
        ):
            if items:
                print(f"  {title}:")
                for it in items:
                    print(f"    - {it}")


def parse_index_file(path: Path) -> dict[str, str]:
    """解析索引 .txt:每行 `基名 | 游戏名`,# 开头为注释。返回 {基名: 游戏名}。"""
    mapping: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        base, name = line.split("|", 1)
        base, name = base.strip(), name.strip()
        if base and name:
            mapping[base] = name
    return mapping


def _find_origin_primary(origin_sys_dir: Path, base: str) -> Path | None:
    """在 origin-roms/<system>/ 找与 base 同去盘号基名的主文件(用于读序列号)。"""
    if not origin_sys_dir.is_dir():
        return None
    for entry in sorted(origin_sys_dir.iterdir()):
        if (
            entry.is_file()
            and entry.suffix.lower() in PRIMARY_EXTS
            and game_base(entry.stem) == base
        ):
            return entry
    return None


def _resolve_online(
    system: str,
    base: str,
    origin_sys_dir: Path,
    platform_index: dict[str, str | None],
) -> tuple[str | None, str]:
    """online 回退:读内部序列号 → redump 查标题 → 离线库再照。

    返回 (db_id, detail):db_id 为解出的 id;None=未解出;"__ambiguous__"=多候选。
    detail 是供报告的说明文字。
    """
    primary = _find_origin_primary(origin_sys_dir, base)
    if primary is None:
        return None, "无原始镜像可读"
    serial = read_serial(system, primary)
    if not serial:
        return None, "读不到内部序列号"
    title = lookup_title(system, serial)
    if not title:
        return None, f"serial {serial}:redump 无命中"
    found = platform_index.get(normalize(search_name(title)), "__missing__")
    if found == "__missing__":
        return None, f'serial {serial} → "{title}":离线库仍查不到'
    if found is None:
        return "__ambiguous__", f'serial {serial} → "{title}":多候选'
    return found, f'serial {serial} → "{title}"'


def _rename_system(
    system: str,
    out_dir: Path,
    origin_dir: Path,
    index: dict[str, dict[str, str | None]],
    index_file: dict[str, str],
    online: bool,
    report: RenameReport,
) -> None:
    sys_dir = out_dir / system
    if not sys_dir.is_dir():
        return
    platform_index = index.get(system, {})
    origin_sys_dir = origin_dir / system

    # 按去盘号基名把 chd 分组。
    groups: dict[str, list[Path]] = {}
    for chd in sorted(sys_dir.glob("*.chd")):
        groups.setdefault(game_base(chd.stem), []).append(chd)

    for base, discs in groups.items():
        label = f"{system}/{base}"
        if base.isdigit():
            report.skipped_already_id.append(label)
            continue

        # 确定搜索名:索引优先,否则从文件名清理。
        name = index_file.get(base) or search_name(base)
        db_id = platform_index.get(normalize(name), "__missing__")
        recovered_detail: str | None = None
        if db_id == "__missing__":
            # 文件名查不到:跳过前先试 online 回退(默认开,可 --no-online 关)。
            if not online:
                report.not_found.append(f"{label}  (搜索名: {name})")
                continue
            resolved, detail = _resolve_online(
                system, base, origin_sys_dir, platform_index
            )
            if resolved == "__ambiguous__":
                report.ambiguous.append(f"{label}  ({detail})")
                continue
            if resolved is None:
                report.not_found.append(f"{label}  (搜索名: {name};online: {detail})")
                continue
            db_id = resolved
            recovered_detail = detail
        elif db_id is None:
            report.ambiguous.append(f"{label}  (搜索名: {name})")
            continue

        discs.sort(key=lambda p: disc_number(p.stem))
        has_disc = any(DISC_RE.search(p.stem) for p in discs)

        new_discs: list[Path] = []
        conflict = False
        for chd in discs:
            if has_disc:
                target = sys_dir / f"{db_id} (Disc {disc_number(chd.stem)}).chd"
            else:
                target = sys_dir / f"{db_id}.chd"
            if target.exists() and target != chd:
                report.skipped_exists.append(f"{system}/{target.name}")
                conflict = True
                break
            new_discs.append(target)
        if conflict:
            continue

        for chd, target in zip(discs, new_discs):
            chd.rename(target)

        # 多盘:把 <base>.m3u 改名为 <id>.m3u 并重写内容。
        if has_disc:
            m3u = sys_dir / f"{base}.m3u"
            new_m3u = sys_dir / f"{db_id}.m3u"
            if m3u.exists():
                m3u.unlink()
            new_m3u.write_text(
                "".join(f"{t.name}\n" for t in new_discs), encoding="utf-8"
            )

        report.renamed.append(f"{label} → {db_id}")
        if recovered_detail:
            report.recovered.append(f"{label} → {db_id}  ({recovered_detail})")


def run_rename(
    base_dir: Path,
    system: str | None = None,
    index_path: Path | None = None,
    online: bool = True,
) -> RenameReport:
    """执行 rename。system 为 None 时处理所有可查询平台。

    online=True(默认)时,文件名查不到的游戏会读内部序列号并去 redump 回退查标题。
    """
    base = base_dir.resolve()
    out_dir = base / "out"
    origin_dir = base / "origin-roms"
    if not out_dir.is_dir():
        raise FileNotFoundError(f"找不到 {out_dir};请先运行 `batoroms merge`。")

    if system is not None and system not in SYSTEM_TO_LAUNCHBOX:
        raise ValueError(
            f"平台 `{system}` 不支持查询:{', '.join(SYSTEM_TO_LAUNCHBOX)}"
        )

    platforms = load_index()["platforms"]
    index_file = parse_index_file(index_path) if index_path else {}
    systems = [system] if system else list(SYSTEM_TO_LAUNCHBOX)

    report = RenameReport()
    for sys_name in systems:
        _rename_system(
            sys_name, out_dir, origin_dir, platforms, index_file, online, report
        )
    report.print_summary()
    return report
