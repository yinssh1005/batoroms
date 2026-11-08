# batoroms — Batocera ROM 整理 CLI

把杂乱的游戏镜像整理成 Batocera 能直接识别、命名统一、UI 显示正确游戏名的 ROM 库。工具跑在
电脑端(代理可配),整理好再把文件拷进 Batocera。

规划中的流水线:**合并为 CHD → 按游戏 ID 统一命名 → 生成 gamelist.xml**。详见
[`goal-and-requirements.md`](goal-and-requirements.md) 与 [`architecture.md`](architecture.md)。

## 环境要求

- Python ≥ 3.10
- 仓库自带 `chdman/chdman.exe`(Windows),供后续合并步骤使用。

## 安装

一键建立虚拟环境并以 editable 方式安装:

```powershell
# Windows PowerShell
./setup.ps1
```

```bash
# 类 Unix / Git Bash
./setup.sh
```

然后启用虚拟环境:

```powershell
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
```

```bash
source .venv/bin/activate        # Linux / macOS
source .venv/Scripts/activate    # Windows Git Bash
```

未安装也可直接运行:`python -m batoroms <command>`。

## 用法

### `init` — 创建目录骨架

```bash
batoroms init            # 在当前目录创建
batoroms init -C <目录>  # 在指定目录创建
```

会创建:

- `origin-roms/`：放原始镜像(只读输入),其下为每个光盘类平台建好子目录
  (`psx`、`ps2`、`megacd`、`saturn`、`dreamcast`、`pcenginecd`、`neogeocd`、`3do`、
  `amigacd32`、`naomi`、`atomiswave`、`pcfx`、`fmtowns`、`cdi`)。
- `out/`：放整理后的成品(先建空,平台子目录后续按需生成)。

命令幂等:已存在的目录会跳过,不会删除任何内容。

### `merge` — 合并为 CHD

把 `origin-roms/<平台>/` 里每个游戏的镜像(`.cue`+bin / `.iso` / `.gdi`)合并成 `.chd` 写到
`out/<平台>/`。多盘游戏每盘一个 chd 并生成 `.m3u` 供自动换盘。

```bash
batoroms merge                 # 处理所有平台
batoroms merge --system psx    # 只处理指定平台
batoroms merge --force         # 已存在的 chd 也重建
```

注:`.cdi`(DiscJuggler)chdman 不支持,会跳过并提示先转成 gdi/cue。

### `update-db` — 下载离线库

下载 LaunchBox 离线元数据库并蒸馏成本地查询索引(缓存在 `~/.batoroms/launchbox/`)。
rename 之前先跑一次;需联网(自动遵循 `HTTP(S)_PROXY` 代理)。

```bash
batoroms update-db
```

### `rename` — 按游戏 ID 改名

按游戏名在离线库查出 LaunchBox 游戏 ID,把 `out/<平台>/` 里的 chd 改名为 `<id>.chd`
(多盘 `<id> (Disc N).chd` + `<id>.m3u`)。游戏名默认从文件名推断(去掉区域/版本标签)。

```bash
batoroms rename                      # 处理所有平台
batoroms rename --system psx         # 只处理指定平台
batoroms rename --index games.txt    # 用索引指定游戏名
```

查不到或多候选的游戏会跳过并列在报告里;用 `--index` 给它们指定游戏名。索引文件
每行 `基名 | 游戏名`(`#` 开头为注释),例如:

```
Single Game (USA) | Crash Bandicoot
```

### `gamelist` — 生成 gamelist.xml

按文件名里的 `<id>` 从离线库反查游戏名,为 `out/<平台>/` 生成 / 合并 `gamelist.xml`,
让 Batocera UI 显示正确游戏名。多盘游戏只显示一个条目(各盘自动隐藏)。

```bash
batoroms gamelist                # 处理所有平台
batoroms gamelist --system psx   # 只处理指定平台
```

已有 `gamelist.xml` 会被合并(保留其它条目);名字查不到的文件会跳过。
