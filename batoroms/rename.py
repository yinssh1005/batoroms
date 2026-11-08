"""rename:按 LaunchBox 离线库把 out/<system>/ 里的 chd 改成 <id>.chd,并更新多盘 m3u。

- 搜索名:默认从 chd 文件名去掉区域/版本标签与盘号;索引 .txt(`基名 | 游戏名`)若提供则优先。
- 单盘 → `<id>.chd`;多盘 → `<id> (Disc N).chd` + `<id>.m3u`(内容更新为新盘名)。
- 多候选/查不到/目标已存在/基名已是纯数字 → 跳过并记报告,不中断。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from batoroms.db import load_index
from batoroms.names import DISC_RE, disc_number, game_base, normalize, search_name
from batoroms.systems import SYSTEM_TO_LAUNCHBOX


@dataclass
class RenameReport:
    renamed: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    skipped_exists: list[str] = field(default_factory=list)
    skipped_already_id: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print(
            f"\n小结:改名 {len(self.renamed)} 个游戏,查不到 {len(self.not_found)} 个,"
            f"多候选跳过 {len(self.ambiguous)} 个,目标已存在 {len(self.skipped_exists)} 个,"
            f"已是 id 跳过 {len(self.skipped_already_id)} 个。"
        )
        for title, items in (
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


def _rename_system(
    system: str,
    out_dir: Path,
    index: dict[str, dict[str, str | None]],
    index_file: dict[str, str],
    report: RenameReport,
) -> None:
    sys_dir = out_dir / system
    if not sys_dir.is_dir():
        return
    platform_index = index.get(system, {})

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
        if db_id == "__missing__":
            report.not_found.append(f"{label}  (搜索名: {name})")
            continue
        if db_id is None:
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


def run_rename(
    base_dir: Path, system: str | None = None, index_path: Path | None = None
) -> RenameReport:
    """执行 rename。system 为 None 时处理所有可查询平台。"""
    base = base_dir.resolve()
    out_dir = base / "out"
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
        _rename_system(sys_name, out_dir, platforms, index_file, report)
    report.print_summary()
    return report
