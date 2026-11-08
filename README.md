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
  `amigacd32`、`naomi`、`atomiswave`、`pcfx`、`fmtowns`、`cdi`、`gamecube`、`wii`)。
- `out/`：放整理后的成品(先建空,平台子目录后续按需生成)。

命令幂等:已存在的目录会跳过,不会删除任何内容。
