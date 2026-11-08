"""gamelist:为 out/<system>/ 里改名后的 chd/m3u 生成 / 合并 EmulationStation 的 gamelist.xml。

- 单盘 `<id>.chd` → 可见条目;多盘 `<id>.m3u` → 可见条目,各盘 `<id> (Disc N).chd` → `<hidden>true</hidden>`。
- 名字按文件名里的 `<id>` 从离线库反查;查不到(非 id 或不在库)→ 跳过并记报告。
- 已有 gamelist.xml 则按 path 合并:更新/新增我们的条目,保留其它条目。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from batoroms.db import load_index
from batoroms.names import disc_number, game_base
from batoroms.systems import SYSTEM_TO_LAUNCHBOX


@dataclass
class GamelistReport:
    written: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print(
            f"\n小结:写入可见条目 {len(self.written)} 个,隐藏各盘 {len(self.hidden)} 个,"
            f"跳过(查不到名字) {len(self.skipped)} 个。"
        )
        if self.skipped:
            print("  跳过(基名不是 id 或不在库):")
            for it in self.skipped:
                print(f"    - {it}")


def _rel_key(path_text: str) -> str:
    """把 <path> 文本归一化成比较键:去掉前导 ./。"""
    return path_text[2:] if path_text.startswith("./") else path_text


def _collect_entries(
    sys_dir: Path, names: dict[str, str], report: GamelistReport
) -> dict[str, tuple[str, bool]]:
    """返回 {相对path: (游戏名, 是否隐藏)}。"""
    m3u_ids = {p.stem for p in sys_dir.glob("*.m3u") if p.stem.isdigit()}
    entries: dict[str, tuple[str, bool]] = {}

    for m3u in sorted(sys_dir.glob("*.m3u")):
        if m3u.stem in names:
            entries[f"./{m3u.name}"] = (names[m3u.stem], False)
        elif m3u.stem.isdigit():
            report.skipped.append(f"{sys_dir.name}/{m3u.name}")

    for chd in sorted(sys_dir.glob("*.chd")):
        base = game_base(chd.stem)
        if not base.isdigit() or base not in names:
            report.skipped.append(f"{sys_dir.name}/{chd.name}")
            continue
        if base in m3u_ids:
            name = f"{names[base]} (Disc {disc_number(chd.stem)})"
            entries[f"./{chd.name}"] = (name, True)
            report.hidden.append(f"{sys_dir.name}/{chd.name}")
        else:
            entries[f"./{chd.name}"] = (names[base], False)
            report.written.append(f"{sys_dir.name}/{chd.name}")

    return entries


def _upsert(root: ET.Element, rel_path: str, name: str, hidden: bool) -> None:
    """在 gameList 里按 path 更新或新增一个 <game>。"""
    game = None
    for g in root.findall("game"):
        p = g.findtext("path") or ""
        if _rel_key(p) == _rel_key(rel_path):
            game = g
            break
    if game is None:
        game = ET.SubElement(root, "game")
        ET.SubElement(game, "path").text = rel_path

    def set_child(tag: str, value: str) -> None:
        el = game.find(tag)
        if el is None:
            el = ET.SubElement(game, tag)
        el.text = value

    set_child("name", name)
    set_child("hidden", "true" if hidden else "false")


def _write_system(
    system: str, out_dir: Path, names: dict[str, str], report: GamelistReport
) -> None:
    sys_dir = out_dir / system
    if not sys_dir.is_dir():
        return

    entries = _collect_entries(sys_dir, names, report)
    if not entries:
        return

    gl_path = sys_dir / "gamelist.xml"
    if gl_path.is_file():
        tree = ET.parse(gl_path)
        root = tree.getroot()
    else:
        root = ET.Element("gameList")
        tree = ET.ElementTree(root)

    for rel_path, (name, hidden) in entries.items():
        _upsert(root, rel_path, name, hidden)

    ET.indent(tree, space="  ")
    tree.write(gl_path, encoding="utf-8", xml_declaration=True)


def run_gamelist(base_dir: Path, system: str | None = None) -> GamelistReport:
    """生成 / 合并 gamelist.xml。system 为 None 时处理所有可查询平台。"""
    base = base_dir.resolve()
    out_dir = base / "out"
    if not out_dir.is_dir():
        raise FileNotFoundError(f"找不到 {out_dir};请先运行 `batoroms merge` 与 `rename`。")

    if system is not None and system not in SYSTEM_TO_LAUNCHBOX:
        raise ValueError(f"平台 `{system}` 不支持:{', '.join(SYSTEM_TO_LAUNCHBOX)}")

    names = load_index()["names"]
    systems = [system] if system else list(SYSTEM_TO_LAUNCHBOX)

    report = GamelistReport()
    for sys_name in systems:
        _write_system(sys_name, out_dir, names, report)
    report.print_summary()
    return report
