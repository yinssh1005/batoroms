# 一键建立虚拟环境并以 editable 方式安装 batoroms(Windows PowerShell)。
# 用法:在项目根目录执行  ./setup.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境 .venv …"
    python -m venv .venv
}

$py = Join-Path $root ".venv\Scripts\python.exe"
Write-Host "安装 batoroms(editable)…"
& $py -m pip install --upgrade pip
& $py -m pip install -e .

Write-Host ""
Write-Host "完成。启用环境后即可使用 batoroms 命令:"
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "    batoroms init"
