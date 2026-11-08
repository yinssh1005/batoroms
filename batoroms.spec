# PyInstaller 构建配置 — 把 batoroms CLI 打成单文件 exe(Windows)。
#
# 用法(由 build.ps1 / build.sh 调用,也可手动):
#     pyinstaller batoroms.spec
# 产物:dist/batoroms.exe
#
# 关键点:把 batoroms/vendor 原样放进包目录,运行时 importlib.resources
# 的 `resources.files("batoroms").joinpath("vendor/chdman/chdman.exe")` 才能定位到。

a = Analysis(
    ["batoroms/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[("batoroms/vendor", "batoroms/vendor")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="batoroms",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
