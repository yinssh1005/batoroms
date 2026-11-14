# batoroms — Batocera ROM 整理 CLI

把杂乱的游戏镜像整理成 Batocera 能直接识别、命名统一、UI 显示正确游戏名的 ROM 库。
流水线:**合并为 CHD → 按游戏名统一命名**。文件改成人类可读的游戏名后,封面
交给 [skraper](#封面抓取skraper) 按文件名抓取。详见
[`goal-and-requirements.md`](goal-and-requirements.md) 与 [`architecture.md`](architecture.md)。

支持的平台分两类:**光盘类**(用 chdman 合并成 CHD:psx、ps2、megacd、saturn、
dreamcast、pcenginecd、neogeocd、3do、amigacd32、naomi、atomiswave、pcfx、fmtowns、
cdi、psp)与**卡带类**(单文件 ROM,只拷贝 + 改名:nes、snes、megadrive、n64、
gamecube)。

## 下载使用(Windows)

从 [Releases](../../releases) 下载最新的 `batoroms.exe` 即可,**不依赖 Python / 虚拟环境**,
`chdman.exe` 已一并打进去。拷到任意 Windows 机器直接运行:

```powershell
.\batoroms.exe --help
.\batoroms.exe init     # 创建 origin-roms/ 与 out/ 目录骨架
```

典型流程:把镜像/ROM 放进 `origin-roms/<平台>/`,然后一键跑完流水线。Dreamcast 的
`.gdi` + track(`.bin`/`.raw`/`.iso`)可以每张盘打成一个 zip 直接放进 `origin-roms/dreamcast/`,
merge 会自动解压并合并成 `<zip名>.chd`(多盘用 `游戏名 (Disc 1).zip` 这样的命名):

```powershell
.\batoroms.exe run                   # 处理所有平台
.\batoroms.exe run --system psx      # 只处理指定平台
.\batoroms.exe run --force           # 已存在的产物也重建
```

`run` 会依次执行 `merge`(光盘合并 CHD、卡带拷贝 ROM 到 `out/`)→ `rename`
(按游戏名改名),离线库未下载时自动先跑 `update-db`。文件名取自 LaunchBox 离线库
的规范游戏名;查不到时先读镜像序列号走 redump.org 回退,再查不到则用清理后的
文件名。

各子命令也可单独调用,用 `--help` 查看:

```powershell
.\batoroms.exe merge --help
.\batoroms.exe rename --help
.\batoroms.exe update-db --help
.\batoroms.exe gamelist --help    # 可选:按文件名生成 gamelist.xml(不再进 run)
```

> `gamelist` 子命令仍保留,但封面改用 skraper 后 `run` 不再自动生成。如果你不用
> skraper、只想让 Batocera UI 显示游戏名,可单独跑 `batoroms gamelist` 按文件名生成。

## 封面抓取:skraper

本工具只负责把文件整理成**游戏名命名**;封面/截图等媒体交给免费的第三方刮削器
[**Skraper**](https://www.skraper.net/)(基于 ScreenScraper)。它跑在你的电脑上,按 `out/<平台>/`
里的文件名(也就是游戏名)搜索并下载封面,按 Batocera / EmulationStation 的媒体目录摆好、
写进 `gamelist.xml`——这正是本工具改用游戏名作文件名的原因:skraper 的文件名匹配比数字 ID 或
CHD 哈希稳得多。

大致用法:

1. 先用本工具跑完 `run`,得到 `out/<平台>/` 下以游戏名命名的 CHD / ROM。
2. 到 <https://www.skraper.net/> 下载 Skraper(Windows,免费;刮削需一个免费的
   [ScreenScraper](https://www.screenscraper.fr/) 账号,配额更高)。
3. 在 Skraper 里把 ROM 目录指向本工具的 `out/`(或拷进 Batocera 后指向 Batocera 的
   `roms/`),选 EmulationStation / Batocera 输出格式,开始刮削。
4. 把 `out/`(含封面与 skraper 生成的 `gamelist.xml`)整包拷进 Batocera 即可。

> skraper 是独立工具,本项目不集成也不代下载;联网刮削同样发生在电脑端,Batocera 端零联网不变。

### 希望更准的名字时:`--index`

查不到游戏名时,`rename` 会回退到**清理后的文件名**(去掉区域/版本/盘号标签)
给文件命名,并在小结的「按文件名回退命名」里列出——skraper 通常仍能按这个名字命中。
如果你想让某些游戏用更准的规范名,写一个索引文件,
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
