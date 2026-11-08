"""batoroms 命令行入口。

子命令分发;本版本实现 `init`,其余流水线子命令(run/merge/rename/gamelist)留待后续。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from batoroms import __version__
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
