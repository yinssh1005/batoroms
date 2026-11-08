"""LaunchBox 离线库:下载 Metadata.zip 并蒸馏成紧凑索引,供 rename 查 ID。

缓存在 `~/.batoroms/launchbox/`:
- `Metadata.zip` 下载的原始包;
- `index.json` 蒸馏后的查询索引 `{平台短名: {归一化名: id|null}}`(null 表示同名多 ID 冲突)。
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from batoroms.names import normalize
from batoroms.systems import SYSTEM_TO_LAUNCHBOX

METADATA_URL = "https://gamesdb.launchbox-app.com/Metadata.zip"
CACHE_DIR = Path.home() / ".batoroms" / "launchbox"
ZIP_PATH = CACHE_DIR / "Metadata.zip"
INDEX_PATH = CACHE_DIR / "index.json"


def _download(url: str, dest: Path) -> None:
    """下载到 dest(urllib 自动遵循 HTTP(S)_PROXY 代理)。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    # 带浏览器 UA,否则 LaunchBox 服务器会 403。
    req = Request(url, headers={"User-Agent": "batoroms/0.1 (+https://batocera.org)"})
    with urlopen(req) as resp, tmp.open("wb") as out:  # noqa: S310 (固定可信 URL)
        total = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            total += len(chunk)
            print(f"\r  已下载 {total / 1e6:.1f} MB …", end="", flush=True)
    print()
    tmp.replace(dest)


INDEX_VERSION = 2


def _distill(xml_path: Path) -> dict:
    """流式解析 Metadata.xml,蒸馏成索引(只含目标平台)。

    返回 {"version", "platforms": {短名: {归一化名: id|None}}, "names": {id: 规范名}}。
    """
    # LaunchBox Platform 字符串 → 我们的短名。
    lb_to_short: dict[str, str] = {}
    for short, lb_names in SYSTEM_TO_LAUNCHBOX.items():
        for lb in lb_names:
            lb_to_short[lb] = short

    # 过程中记 名→id集合,以便识别同名多 id 冲突。
    acc: dict[str, dict[str, set[str]]] = {short: {} for short in SYSTEM_TO_LAUNCHBOX}
    # DatabaseID → 短名,用于把别名归到正确平台。
    id_to_short: dict[str, str] = {}
    # DatabaseID → 规范游戏名(取 <Game> 的 Name,供 gamelist 反查)。
    names: dict[str, str] = {}

    def add(short: str, name: str, db_id: str) -> None:
        key = normalize(name)
        if not key:
            return
        acc[short].setdefault(key, set()).add(db_id)

    for _event, elem in ET.iterparse(str(xml_path), events=("end",)):
        tag = elem.tag
        if tag == "Game":
            platform = (elem.findtext("Platform") or "").strip()
            short = lb_to_short.get(platform)
            db_id = (elem.findtext("DatabaseID") or "").strip()
            name = (elem.findtext("Name") or "").strip()
            if short and db_id and name:
                add(short, name, db_id)
                id_to_short[db_id] = short
                names[db_id] = name
            elem.clear()
        elif tag == "GameAlternateName":
            db_id = (elem.findtext("DatabaseID") or "").strip()
            name = (elem.findtext("AlternateName") or "").strip()
            short = id_to_short.get(db_id)
            if short and db_id and name:
                add(short, name, db_id)
            elem.clear()

    # 收敛:同名唯一 → id;多 id → None(冲突,查询时跳过)。
    platforms: dict[str, dict[str, str | None]] = {}
    for short, by_name in acc.items():
        platforms[short] = {
            key: (next(iter(ids)) if len(ids) == 1 else None)
            for key, ids in by_name.items()
        }
    return {"version": INDEX_VERSION, "platforms": platforms, "names": names}


def update_db() -> Path:
    """下载并蒸馏离线库,返回 index.json 路径。"""
    print(f"下载 LaunchBox 离线库到 {ZIP_PATH} …")
    _download(METADATA_URL, ZIP_PATH)

    print("解压并蒸馏索引(首次较慢)…")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extract("Metadata.xml", CACHE_DIR)
    xml_path = CACHE_DIR / "Metadata.xml"

    index = _distill(xml_path)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    xml_path.unlink(missing_ok=True)  # 蒸馏完不再需要 500MB 的 xml。

    total = sum(len(v) for v in index["platforms"].values())
    print(
        f"完成。索引写入 {INDEX_PATH}"
        f"(共 {total} 条名称,{len(index['names'])} 个游戏)。"
    )
    return INDEX_PATH


def load_index() -> dict:
    """读取蒸馏索引;不存在或格式过旧则提示重跑 update-db。"""
    if not INDEX_PATH.is_file():
        raise FileNotFoundError(
            f"未找到离线库索引({INDEX_PATH});请先运行 `batoroms update-db`。"
        )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or index.get("version") != INDEX_VERSION:
        raise ValueError("离线库索引格式已更新,请重跑 `batoroms update-db`。")
    return index
