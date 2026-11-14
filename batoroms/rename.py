"""rename:把 out/<system>/ 里的产物改成**游戏名**作文件名,并更新多盘 m3u。

- 命名来源:LaunchBox 离线库命中 → 该游戏规范名;离线库查不到则读内部序列号去 redump 回退
  (默认开,可 --no-online 关),救回后同样取规范名;仍查不到 → 回退到清理后的文件名
  (去掉区域/版本/盘号标签),让 skraper 仍能按名字命中。
- 光盘:处理 out 里所有游戏文件(`.chd`/`.cdi`/`.cso`/`.pbp`),保留各自扩展名;
  单盘 `<名>.<ext>`,多盘 `<名> (Disc N).<ext>` + `<名>.m3u`。卡带:保留原扩展名,只改主名,无 m3u。
- 游戏名经 safe_filename 过滤非法字符;多候选/目标已存在/已是该名 → 跳过并记报告,不中断。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from batoroms.db import load_index
from batoroms.disc_meta import read_serial
from batoroms.names import (
    DISC_RE,
    disc_number,
    game_base,
    normalize,
    safe_filename,
    search_name,
)
from batoroms.online import lookup_title
from batoroms.systems import CART_EXTS, SYSTEM_TO_LAUNCHBOX, is_cart

PRIMARY_EXTS = (".cue", ".gdi", ".iso")

# out 里需要改名的光盘游戏文件扩展名:chdman 成品 `.chd`,
# 以及 merge 原样带过来的 `.cdi`/`.cso`/`.pbp`。(`.m3u` 为播放列表,由 rename 重建,不列在内。)
DISC_OUT_EXTS = (".chd", ".cdi", ".cso", ".pbp")


@dataclass
class RenameReport:
    renamed: list[str] = field(default_factory=list)
    recovered: list[str] = field(default_factory=list)
    fallback_named: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    skipped_exists: list[str] = field(default_factory=list)
    skipped_already: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print(
            f"\n小结:改名 {len(self.renamed)} 个游戏(其中 online 回退救回 {len(self.recovered)} 个,"
            f"按文件名回退命名 {len(self.fallback_named)} 个),"
            f"多候选跳过 {len(self.ambiguous)} 个,目标已存在 {len(self.skipped_exists)} 个,"
            f"已是该名跳过 {len(self.skipped_already)} 个。"
        )
        for title, items in (
            ("online 回退救回", self.recovered),
            ("按文件名回退命名(未在库中确认)", self.fallback_named),
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


def _products(sys_dir: Path, cart: bool) -> list[Path]:
    """列出某平台 out/ 下的游戏文件:光盘为 .chd/.cdi/.cso/.pbp,卡带为该平台的 ROM 扩展名。"""
    exts = CART_EXTS.get(sys_dir.name, frozenset()) if cart else DISC_OUT_EXTS
    return [
        p
        for p in sorted(sys_dir.iterdir())
        if p.is_file() and p.suffix.lower() in exts
    ]


def _rename_system(
    system: str,
    out_dir: Path,
    origin_dir: Path,
    platforms: dict[str, dict[str, str | None]],
    names: dict[str, str],
    index_file: dict[str, str],
    online: bool,
    report: RenameReport,
) -> None:
    sys_dir = out_dir / system
    if not sys_dir.is_dir():
        return
    platform_index = platforms.get(system, {})
    origin_sys_dir = origin_dir / system
    cart = is_cart(system)

    # 按去盘号基名把产物分组。
    groups: dict[str, list[Path]] = {}
    for prod in _products(sys_dir, cart):
        groups.setdefault(game_base(prod.stem), []).append(prod)

    for base, files in groups.items():
        label = f"{system}/{base}"

        # 确定搜索名:索引优先,否则从文件名清理。
        name = index_file.get(base) or search_name(base)
        db_id = platform_index.get(normalize(name), "__missing__")

        display: str
        recovered_detail: str | None = None
        fallback = False

        if db_id == "__missing__":
            # 文件名查不到:光盘且 online 开时先试序列号→redump 回退。
            resolved: str | None = None
            detail = ""
            if online and not cart:
                resolved, detail = _resolve_online(
                    system, base, origin_sys_dir, platform_index
                )
                if resolved == "__ambiguous__":
                    report.ambiguous.append(f"{label}  ({detail})")
                    continue
            if resolved and resolved != "__ambiguous__":
                display = names.get(resolved, name)
                recovered_detail = detail
            else:
                # 仍查不到:回退到清理后的文件名(skraper 仍能按名字命中)。
                display = name
                fallback = True
        elif db_id is None:
            report.ambiguous.append(f"{label}  (搜索名: {name})")
            continue
        else:
            display = names.get(db_id, name)

        safe = safe_filename(display) or safe_filename(base) or base
        files.sort(key=lambda p: disc_number(p.stem))
        has_disc = (not cart) and any(DISC_RE.search(p.stem) for p in files)

        # 计算每个文件的目标名(保留原扩展名)。
        new_paths: list[Path] = []
        conflict = False
        for prod in files:
            ext = prod.suffix
            if has_disc:
                target = sys_dir / f"{safe} (Disc {disc_number(prod.stem)}){ext}"
            else:
                target = sys_dir / f"{safe}{ext}"
            if target.exists() and target != prod:
                report.skipped_exists.append(f"{system}/{target.name}")
                conflict = True
                break
            new_paths.append(target)
        if conflict:
            continue

        # 文件是否已全部就位。即使就位,多盘 m3u 也可能还没生成,故先补齐 m3u 再判是否跳过。
        already = all(src == dst for src, dst in zip(files, new_paths))

        for prod, target in zip(files, new_paths):
            if prod != target:
                prod.rename(target)

        # 多盘光盘:把 <base>.m3u 改名为 <名>.m3u 并按需重写内容(缺失或过时才写)。
        if has_disc:
            old_m3u = sys_dir / f"{base}.m3u"
            new_m3u = sys_dir / f"{safe}.m3u"
            if old_m3u.exists() and old_m3u != new_m3u:
                old_m3u.unlink()
            content = "".join(f"{t.name}\n" for t in new_paths)
            if not new_m3u.exists() or new_m3u.read_text(encoding="utf-8") != content:
                new_m3u.write_text(content, encoding="utf-8")

        # 文件已全部就位 → 幂等跳过(m3u 已在上方补齐)。
        if already:
            report.skipped_already.append(f"{label} → {safe}")
            continue

        report.renamed.append(f"{label} → {safe}")
        if recovered_detail:
            report.recovered.append(f"{label} → {safe}  ({recovered_detail})")
        if fallback:
            report.fallback_named.append(f"{label} → {safe}")


def run_rename(
    base_dir: Path,
    system: str | None = None,
    index_path: Path | None = None,
    online: bool = True,
) -> RenameReport:
    """执行 rename。system 为 None 时处理所有可查询平台。

    online=True(默认)时,文件名查不到的光盘游戏会读内部序列号并去 redump 回退查标题。
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

    index = load_index()
    platforms = index["platforms"]
    names = index["names"]
    index_file = parse_index_file(index_path) if index_path else {}
    systems = [system] if system else list(SYSTEM_TO_LAUNCHBOX)

    report = RenameReport()
    for sys_name in systems:
        _rename_system(
            sys_name, out_dir, origin_dir, platforms, names, index_file, online, report
        )
    report.print_summary()
    return report
