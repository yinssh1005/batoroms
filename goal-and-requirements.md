---
id: batocera-rom-cli
type: goal-and-requirements
status: active
title: Batocera ROM 整理 CLI
---

# Batocera ROM 整理 CLI

> 一条命令把杂乱的游戏镜像整理成 Batocera 能直接识别、命名统一、UI 显示正确游戏名的 ROM 库。

## Overview

一个面向个人使用、跑在电脑（Windows）上的命令行工具,把本地散乱的游戏镜像(如 `.cue` + `.bin`、
`.iso`、`.gdi`)整理成 Batocera 游戏系统期望的样子,整理完整包拷进 Batocera 即可。它串起三件事:
用自带的 `chdman` 把一个游戏的多个镜像文件合并压缩成单个 `.chd`;查出该游戏的数字游戏 ID 与
正确游戏名,把文件统一改名为 `<游戏ID>.chd`;再生成 Batocera 的 `gamelist.xml`,让 UI 里显示正确
的游戏名,而不依赖 Batocera 自身联网刮削。

替代的是手动一个个跑 chdman 批处理、逐一上网查游戏、手动改名、再折腾 Batocera 刮削的繁琐流程。

## Problem

把一批下载来的游戏镜像搬进 Batocera 时,当前只能手动完成一连串重复劳动:对每个游戏分别调
chdman 合并成 chd、上网逐一查确认是哪个游戏、手动把文件改成统一命名。游戏一多就极其枯燥且
容易出错。

而且有个两难:一旦把文件改成整洁的数字 ID 名(用户想要的),Batocera 自带的刮削器反而更难认出
游戏——它很多时候按文件名匹配,纯数字名字识别不了;哈希匹配对 CHD 又不稳;Batocera 那台机器
还没有原生代理支持,联网刮削本身就费劲。缺的是一个在电脑端把"合并 → 统一命名 → 让 Batocera
正确显示"这条流水线一次做完的工具,Batocera 端只负责显示、零联网。

## Capabilities

最小可用的第一版围绕这条流水线:

1. **合并为 CHD** — 对指定目录下属于同一个游戏的镜像文件,调用自带的 `chdman`
   (`createcd` / `createdvd`,依系统而定)合并压缩成单个 `.chd` 文件。
2. **统一命名为游戏 ID** — 查出游戏的数字 ID 与正确游戏名,把文件改名为 `<游戏ID>.chd`。
   游戏名有两种来源:从合并后的文件名推断,或用户提供的索引文件(`.txt`,每行是文件名与对应
   游戏名)。数据源用 LaunchBox Games DB 的离线全库(见 Tech Notes)。
3. **生成 gamelist.xml** — 为改名后的 `<游戏ID>.chd` 生成 / 更新 Batocera 的 `gamelist.xml`,
   把正确的游戏名挂上去,使 Batocera UI 直接显示正确名字,全程不依赖 Batocera 联网刮削。
   第一版只写游戏名,**暂不含封面**。

## Non-Goals

- **第一版不抓取封面** — 抓取游戏封面并按 Batocera 媒体目录存放,留待后续版本。那时由本工具
  (在电脑端,代理可配)负责下载并写进 `gamelist.xml`,仍不依赖 Batocera 自身刮削。
- **不依赖 Batocera 自带刮削器** — 这是一个明确决定:因为文件改成数字 ID 名后 Batocera 的
  文件名匹配会失效、CHD 的哈希匹配不稳、且 Batocera 无原生代理。所以游戏名(及以后的封面)
  一律由本工具在电脑端查好、写进 `gamelist.xml`,Batocera 只负责显示。
- **不内置任何第三方凭据** — 第一版数据源 LaunchBox DB 零凭据即可用;若以后接入 ScreenScraper
  等需凭据的源,由用户自行申请并通过配置提供,不硬编码。

## Tech Notes

- **语言 / 运行时**:Python。用 `subprocess` 调 `chdman`、下载 / 解析离线库、处理文件改名与
  生成 XML 都顺手,跨平台且依赖少。
- **运行位置**:跑在用户电脑(Windows)上,而非 Batocera 机器里——网络代理随便配(系统代理 /
  `HTTPS_PROXY` 环境变量),绕开 Batocera 无原生代理的限制;整理完再把文件拷进 Batocera。
- **chdman**:仓库内已自带 `chdman.exe`(见 `chdman/`)。CD 镜像用 `chdman createcd -i x.cue -o x.chd`,
  DVD 类系统(如 PS2)用 `createdvd`。
- **ID / 名字数据源**:LaunchBox Games DB 的离线全库(官方每日更新的 `Metadata.zip`,约 190MB,
  含每个游戏的数字 DatabaseID 与游戏名)。下载一次后本地按游戏名匹配,零凭据、不受每日配额
  限制。*（后续版本可把数据源做成可切换,接入 ScreenScraper 取更全的封面/区域版本。）*
- **gamelist.xml**:按 Batocera / EmulationStation 的 `gamelist.xml` 格式生成,把 `<游戏ID>.chd`
  映射到正确游戏名(具体字段与路径规则在 architecture 阶段敲定)。
