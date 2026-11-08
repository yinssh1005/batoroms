#!/usr/bin/env bash
# 把 batoroms 打包成单文件可执行程序 dist/batoroms.exe(Windows Git Bash)。
# 用法:在项目根目录执行  ./build.sh
# 产物:dist/batoroms.exe —— 不依赖 Python/虚拟环境,可直接分发运行。
#
# 注意:仓库自带的是 chdman.exe(Windows),故本脚本面向 Windows 目标。
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=python3

if [ ! -d .venv ]; then
    echo "创建虚拟环境 .venv …"
    "$PY" -m venv .venv
fi

if [ -x .venv/bin/python ]; then
    VENV_PY=.venv/bin/python        # Linux / macOS
else
    VENV_PY=.venv/Scripts/python    # Windows (Git Bash)
fi

echo "安装构建依赖(pyinstaller + batoroms)…"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install pyinstaller
"$VENV_PY" -m pip install -e .

echo "清理旧产物 …"
rm -rf build dist

echo "打包 …"
"$VENV_PY" -m PyInstaller --clean --noconfirm batoroms.spec

echo ""
echo "完成。可执行文件:dist/batoroms.exe"
echo "试运行:  ./dist/batoroms.exe --help"
