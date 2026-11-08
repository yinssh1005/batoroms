# batoroms — Batocera ROM 整理 CLI

把杂乱的游戏镜像整理成 Batocera 能直接识别、命名统一、UI 显示正确游戏名的 ROM 库。
流水线:**合并为 CHD → 按游戏 ID 统一命名 → 生成 gamelist.xml**。详见
[`goal-and-requirements.md`](goal-and-requirements.md) 与 [`architecture.md`](architecture.md)。

## 下载使用(Windows)

从 [Releases](../../releases) 下载最新的 `batoroms.exe` 即可,**不依赖 Python / 虚拟环境**,
`chdman.exe` 已一并打进去。拷到任意 Windows 机器直接运行:

```powershell
.\batoroms.exe --help
.\batoroms.exe init     # 创建 origin-roms/ 与 out/ 目录骨架
```

典型流程:把镜像放进 `origin-roms/<平台>/`,然后一键跑完整流水线:

```powershell
.\batoroms.exe run                   # 处理所有平台
.\batoroms.exe run --system psx      # 只处理指定平台
.\batoroms.exe run --force           # 已存在的 chd 也重建
```

`run` 会依次执行 `merge`(合并 CHD)→ `rename`(按游戏 ID 改名)→ `gamelist`
(生成 gamelist.xml),离线库未下载时自动先跑 `update-db`。各子命令也可单独调用,
用 `--help` 查看:

```powershell
.\batoroms.exe merge --help
.\batoroms.exe rename --help
.\batoroms.exe gamelist --help
.\batoroms.exe update-db --help
```

### 查不到名字时:`--index`

有些镜像的文件名推断不出游戏名,`rename` 会在小结的
「查不到(请用 `--index` 指定游戏名)」里列出。这时写一个索引文件,
每行 `基名 | 游戏名`(`基名` 就是报告里列出的那个名字,`游戏名` 用能在
离线库命中的名字,别名也可),再传给 `rename`:

```powershell
.\batoroms.exe rename --index index.txt
```

仓库根目录的 [`index.txt`](index.txt) 收录了这类需要手工指定的游戏,
可直接取用或补充(欢迎 PR)。

## 本地构建

需要 Python ≥ 3.10。在项目根目录执行构建脚本(内部用 PyInstaller,会把
`chdman.exe` 一并打进去):

```powershell
# Windows PowerShell
./build.ps1
```

```bash
# Windows Git Bash
./build.sh
```

产物为 `dist/batoroms.exe`。构建配置见 [`batoroms.spec`](batoroms.spec)。

开发时如需 editable 安装,可用 `./setup.ps1` / `./setup.sh` 建立虚拟环境,
之后用 `python -m batoroms <command>` 运行。
