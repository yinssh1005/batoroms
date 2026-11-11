"""gamelist:为 out/<system>/ 里改名后的产物生成 / 合并 EmulationStation 的 gamelist.xml。

封面已改用 skraper(按游戏名文件名抓),所以 `run` 不再自动跑这步;本子命令保留,供需要手动
生成游戏名列表的人使用。文件名此时已是游戏名,显示名**直接取文件主名**,不再按 id 反查离线库。

- 单盘 `<名>.chd` / 卡带 ROM → 可见条目;多盘 `<名>.m3u` → 可见条目,各盘 `<名> (Disc N).chd`
  → `<hidden>true</hidden>`,UI 只显一个游戏。
- 已有 gamelist.xml 则按 path 合并:更新/新增我们的条目,保留其它条目。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from batoroms.names import game_base
from batoroms.systems import ALL_SYSTEMS, CART_EXTS, is_cart


@dataclass
class GamelistReport:
    written: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print(
            f"\n小结:写入可见条目 {len(self.written)} 个,隐藏各盘 {len(self.hidden)} 个。"
        )


def _rel_key(path_text: str) -> str:
    """把 <path> 文本归一化成比较键:去掉前导 ./。"""
    return path_text[2:] if path_text.startswith("./") else path_text


def _collect_entries(
    sys_dir: Path, cart: bool, report: GamelistReport
) -> dict[str, tuple[str, bool]]:
    """返回 {相对path: (游戏名, 是否隐藏)}。显示名直接取文件主名(已是游戏名)。"""
    entries: dict[str, tuple[str, bool]] = {}

    if cart:
        exts = CART_EXTS.get(sys_dir.name, frozenset())
        for rom in sorted(sys_dir.iterdir()):
            if rom.is_file() and rom.suffix.lower() in exts:
                entries[f"./{rom.name}"] = (rom.stem, False)
                report.written.append(f"{sys_dir.name}/{rom.name}")
        return entries

    # 光盘:多盘用 m3u 的基名区分隐藏各盘。
    m3u_bases = {game_base(p.stem) for p in sys_dir.glob("*.m3u")}

    for m3u in sorted(sys_dir.glob("*.m3u")):
        entries[f"./{m3u.name}"] = (m3u.stem, False)
        report.written.append(f"{sys_dir.name}/{m3u.name}")

    for chd in sorted(sys_dir.glob("*.chd")):
        if game_base(chd.stem) in m3u_bases:
            entries[f"./{chd.name}"] = (chd.stem, True)
            report.hidden.append(f"{sys_dir.name}/{chd.name}")
        else:
            entries[f"./{chd.name}"] = (chd.stem, False)
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


def _write_system(system: str, out_dir: Path, report: GamelistReport) -> None:
    sys_dir = out_dir / system
    if not sys_dir.is_dir():
        return

    entries = _collect_entries(sys_dir, is_cart(system), report)
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
    """生成 / 合并 gamelist.xml。system 为 None 时处理所有平台。"""
    base = base_dir.resolve()
    out_dir = base / "out"
    if not out_dir.is_dir():
        raise FileNotFoundError(f"找不到 {out_dir};请先运行 `batoroms merge` 与 `rename`。")

    if system is not None and system not in ALL_SYSTEMS:
        raise ValueError(f"平台 `{system}` 不支持:{', '.join(ALL_SYSTEMS)}")

    systems = [system] if system else list(ALL_SYSTEMS)

    report = GamelistReport()
    for sys_name in systems:
        _write_system(sys_name, out_dir, report)
    report.print_summary()
    return report
