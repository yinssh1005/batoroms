"""batoroms 命令行入口。

子命令分发;本版本实现 `init`,其余流水线子命令(run/merge/rename/gamelist)留待后续。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from batoroms import __version__
from batoroms.gamelist import run_gamelist
from batoroms.merge import run_merge
from batoroms.rename import run_rename
from batoroms.systems import DISC_SYSTEMS


def cmd_init(args: argparse.Namespace) -> int:
    """在目标目录下创建 origin-roms/ 与 out/ 目录骨架。

    - origin-roms/<system>/:为每个光盘类平台建子目录(输入)。
    - out/:先建空,平台子目录由后续 run/merge 按需生成。

    幂等:已存在的目录跳过,不报错、不删除任何已有内容。
    """
    base = Path(args.directory).resolve()

    created: list[str] = []
    existed: list[str] = []

    def ensure(path: Path) -> None:
        rel = path.relative_to(base).as_posix()
        if path.exists():
            existed.append(rel)
        else:
            created.append(rel)
        path.mkdir(parents=True, exist_ok=True)

    print(f"在 {base} 下初始化目录骨架…")

    origin = base / "origin-roms"
    out = base / "out"
    ensure(origin)
    ensure(out)
    for system in DISC_SYSTEMS:
        ensure(origin / system)

    print(f"  新建 {len(created)} 个,已存在 {len(existed)} 个。")
    if created:
        print("  新建:")
        for rel in created:
            print(f"    + {rel}")
    if existed:
        print("  已存在(跳过):")
        for rel in existed:
            print(f"    = {rel}")

    print("完成。把光盘镜像放进对应的 origin-roms/<平台>/ 目录即可。")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    """把 origin-roms/<system>/ 下的镜像合并成 .chd 写到 out/<system>/。"""
    try:
        run_merge(Path(args.directory), system=args.system, force=args.force)
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误:{exc}")
        return 1
    return 0


def cmd_update_db(args: argparse.Namespace) -> int:
    """下载 / 更新 LaunchBox 离线库并蒸馏索引。"""
    from batoroms.db import update_db

    update_db()
    return 0


def cmd_rename(args: argparse.Namespace) -> int:
    """按离线库查 ID,把 out/<system>/ 里的 chd 改名为 <id>.chd。"""
    index_path = Path(args.index) if args.index else None
    try:
        run_rename(
            Path(args.directory),
            system=args.system,
            index_path=index_path,
            online=not args.no_online,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误:{exc}")
        return 1
    return 0


def cmd_gamelist(args: argparse.Namespace) -> int:
    """为 out/<system>/ 生成 / 合并 gamelist.xml。"""
    try:
        run_gamelist(Path(args.directory), system=args.system)
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误:{exc}")
        return 1
    return 0


def _ensure_index() -> None:
    """离线库索引缺失或过旧时自动下载/蒸馏。"""
    from batoroms.db import load_index, update_db

    try:
        load_index()
    except (FileNotFoundError, ValueError):
        print("未找到可用的离线库索引,先自动运行 update-db…")
        update_db()


def cmd_run(args: argparse.Namespace) -> int:
    """一键顺序跑完 merge → rename → gamelist。"""
    base = Path(args.directory)
    index_path = Path(args.index) if args.index else None
    try:
        _ensure_index()
        print("\n== merge ==")
        run_merge(base, system=args.system, force=args.force)
        print("\n== rename ==")
        run_rename(
            base, system=args.system, index_path=index_path, online=not args.no_online
        )
        print("\n== gamelist ==")
        run_gamelist(base, system=args.system)
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误:{exc}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="batoroms",
        description="Batocera ROM 整理 CLI。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    init_parser = subparsers.add_parser(
        "init",
        help="创建 origin-roms/ 与 out/ 目录骨架",
        description="在目标目录下创建 origin-roms/(含各光盘平台子目录)与 out/。",
    )
    init_parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="在此目录下创建骨架(默认:当前目录)",
    )
    init_parser.set_defaults(func=cmd_init)

    merge_parser = subparsers.add_parser(
        "merge",
        help="把 origin-roms 下的镜像合并成 CHD 到 out",
        description="扫描 origin-roms/<平台>/,将每个游戏的镜像合并成 .chd 写到 out/<平台>/。",
    )
    merge_parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="项目目录(含 origin-roms/、out/;默认:当前目录)",
    )
    merge_parser.add_argument(
        "--system",
        default=None,
        help="只处理指定平台(如 psx);缺省处理所有已识别平台",
    )
    merge_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="已存在的 chd/m3u 也重新生成",
    )
    merge_parser.set_defaults(func=cmd_merge)

    subparsers.add_parser(
        "update-db",
        help="下载 / 更新 LaunchBox 离线库",
        description="下载 LaunchBox Metadata.zip 并蒸馏成本地查询索引。",
    ).set_defaults(func=cmd_update_db)

    rename_parser = subparsers.add_parser(
        "rename",
        help="按离线库查 ID 把 out 里的 chd 改名为 <id>.chd",
        description="按游戏名查 LaunchBox 游戏 ID,把 out/<平台>/ 里的 chd 改名为 <id>.chd。",
    )
    rename_parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="项目目录(含 out/;默认:当前目录)",
    )
    rename_parser.add_argument(
        "--system",
        default=None,
        help="只处理指定平台(如 psx);缺省处理所有可查询平台",
    )
    rename_parser.add_argument(
        "--index",
        default=None,
        help="索引文件(每行 `基名 | 游戏名`),指定后优先于文件名推断",
    )
    rename_parser.add_argument(
        "--no-online",
        action="store_true",
        help="关闭 online 回退(默认开):文件名查不到时不读序列号、不联网查 redump",
    )
    rename_parser.set_defaults(func=cmd_rename)

    gamelist_parser = subparsers.add_parser(
        "gamelist",
        help="为 out 里的 chd/m3u 生成 / 合并 gamelist.xml",
        description="按 id 反查游戏名,为 out/<平台>/ 生成 / 合并 EmulationStation 的 gamelist.xml。",
    )
    gamelist_parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="项目目录(含 out/;默认:当前目录)",
    )
    gamelist_parser.add_argument(
        "--system",
        default=None,
        help="只处理指定平台(如 psx);缺省处理所有可查询平台",
    )
    gamelist_parser.set_defaults(func=cmd_gamelist)

    run_parser = subparsers.add_parser(
        "run",
        help="一键跑完 merge → rename → gamelist",
        description="一键流水线:按需 update-db,然后顺序跑 merge → rename → gamelist。",
    )
    run_parser.add_argument(
        "-C",
        "--directory",
        default=".",
        help="项目目录(含 origin-roms/、out/;默认:当前目录)",
    )
    run_parser.add_argument(
        "--system",
        default=None,
        help="只处理指定平台(如 psx);缺省处理所有已识别平台",
    )
    run_parser.add_argument(
        "--index",
        default=None,
        help="索引文件(每行 `基名 | 游戏名`),传给 rename 步",
    )
    run_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="传给 merge:已存在的 chd 也重建",
    )
    run_parser.add_argument(
        "--no-online",
        action="store_true",
        help="传给 rename:关闭 online 回退(默认开)",
    )
    run_parser.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
