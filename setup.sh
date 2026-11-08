#!/usr/bin/env bash
# 一键建立虚拟环境并以 editable 方式安装 batoroms(类 Unix / Git Bash)。
# 用法:在项目根目录执行  ./setup.sh
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

if [ ! -d .venv ]; then
    echo "创建虚拟环境 .venv …"
    "$PY" -m venv .venv
fi

if [ -x .venv/bin/python ]; then
    VENV_PY=.venv/bin/python        # Linux / macOS
else
    VENV_PY=.venv/Scripts/python    # Windows (Git Bash)
fi

echo "安装 batoroms(editable)…"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -e .

echo ""
echo "完成。启用环境后即可使用 batoroms 命令:"
echo "    source .venv/bin/activate      # Windows Git Bash: source .venv/Scripts/activate"
echo "    batoroms init"
