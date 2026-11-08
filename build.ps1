# 把 batoroms 打包成单文件可执行程序 dist\batoroms.exe(Windows PowerShell)。
# 用法:在项目根目录执行  ./build.ps1
# 产物:dist\batoroms.exe —— 不依赖 Python/虚拟环境,可直接分发运行。
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境 .venv …"
    python -m venv .venv
}

$py = Join-Path $root ".venv\Scripts\python.exe"
Write-Host "安装构建依赖(pyinstaller + batoroms)…"
& $py -m pip install --upgrade pip
& $py -m pip install pyinstaller
& $py -m pip install -e .

Write-Host "清理旧产物 …"
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }

Write-Host "打包 …"
& $py -m PyInstaller --clean --noconfirm batoroms.spec

Write-Host ""
Write-Host "完成。可执行文件:dist\batoroms.exe"
Write-Host "试运行:  .\dist\batoroms.exe --help"
