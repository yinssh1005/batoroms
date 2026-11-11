---
id: batocera-rom-cli
type: goal-and-requirements
status: active
title: Batocera ROM 整理 CLI
---

# Batocera ROM 整理 CLI

> 一条命令把杂乱的游戏镜像整理成 Batocera 能直接识别、命名统一、UI 显示正确游戏名的 ROM 库。

## Overview

一个面向个人使用、跑在电脑（Windows）上的命令行工具,把本地散乱的游戏镜像/ROM(如 `.cue` + `.bin`、
`.iso`、`.gdi`,以及卡带类单文件 ROM)整理成 Batocera 游戏系统期望的样子,整理完整包拷进 Batocera
即可。它串起两件事:用自带的 `chdman` 把一个光盘游戏的多个镜像文件合并压缩成单个 `.chd`(卡带类
单文件 ROM 则原样拷贝);查出该游戏的**正确游戏名**,把文件统一改名为 `<游戏名>.chd` / `<游戏名>.<ext>`。
封面等媒体交给电脑端的第三方刮削器 [Skraper](https://www.skraper.net/) 按游戏名文件名抓取,
不依赖 Batocera 自身联网刮削。

替代的是手动一个个跑 chdman 批处理、逐一上网查游戏、手动改名的繁琐流程。

## Problem

把一批下载来的游戏镜像搬进 Batocera 时,当前只能手动完成一连串重复劳动:对每个游戏分别调
chdman 合并成 chd、上网逐一查确认是哪个游戏、手动把文件改成统一命名。游戏一多就极其枯燥且
容易出错。

Batocera 自带的刮削器在这台机器上跑很费劲:哈希匹配对 CHD 不稳、且 Batocera 无原生代理支持,
联网刮削本身就难。更稳的做法是在电脑端把文件整理成**游戏名命名**,再用电脑端的刮削器
(skraper)按文件名抓封面——文件名匹配比哈希稳得多。缺的是一个在电脑端把"合并/拷贝 → 按游戏名
统一命名"这几步一次做完的工具,封面交给 skraper,Batocera 端只负责显示、零联网。

## Capabilities

流水线围绕两步:

1. **准备产物到 `out/`** — 光盘平台:对属于同一个游戏的镜像文件调用自带的 `chdman`
   (`createcd` / `createdvd`,依系统而定)合并压缩成单个 `.chd`;卡带平台(单文件 ROM):
   `chdman` 不适用,把 ROM 原样拷贝到 `out/`(保持原始只读)。
2. **统一命名为游戏名** — 查出游戏的正确游戏名,把文件改名为 `<游戏名>.chd`(卡带保留原扩展名
   `<游戏名>.<ext>`)。名字来源优先 LaunchBox Games DB 离线全库的规范名;文件名/索引查不到时
   读镜像内部序列号去联网(redump)回退找正式标题(默认开,可关);仍查不到则回退到**清理后的
   文件名**(去掉区域/版本/盘号标签),让 skraper 仍能按名字命中。用户也可用索引文件(`.txt`,
   每行 `基名 | 游戏名`)覆盖。数据源与回退见 Tech Notes。

封面/媒体由电脑端的 [Skraper](https://www.skraper.net/) 按 `out/` 里的游戏名文件名抓取并写进
`gamelist.xml`。本工具保留一个可选的 `gamelist` 子命令(按文件主名生成游戏名列表),但不进 `run`
流水线、也不抓封面。

## Non-Goals

- **不内置封面抓取** — 封面/媒体由电脑端的第三方刮削器 [Skraper](https://www.skraper.net/)
  负责(按游戏名文件名搜索下载、按 Batocera 媒体目录存放、写进 `gamelist.xml`)。本工具只把文件
  整理成游戏名命名,好让 skraper 的文件名匹配稳定命中;不集成、不代下载 skraper。
- **不依赖 Batocera 自带刮削器** — 文件虽改成人类可读的游戏名(不再是数字 ID),刮削仍放在电脑端
  (skraper,代理可配),因为 Batocera 无原生代理、联网刮削费劲;Batocera 端零联网,只负责显示。
- **不内置任何第三方凭据** — 本工具数据源 LaunchBox DB 零凭据即可用;skraper 用的 ScreenScraper
  账号由用户自行在 skraper 里配置,不由本工具硬编码。

## Tech Notes

- **语言 / 运行时**:Python。用 `subprocess` 调 `chdman`、下载 / 解析离线库、处理文件改名与
  生成 XML 都顺手,跨平台且依赖少。
- **运行位置**:跑在用户电脑(Windows)上,而非 Batocera 机器里——网络代理随便配(系统代理 /
  `HTTPS_PROXY` 环境变量),绕开 Batocera 无原生代理的限制;整理完再把文件拷进 Batocera。
- **chdman**:随包分发,位于 `batoroms/vendor/chdman/`。CD 类平台用 `chdman createcd`,DVD 类(PS2
  与 PSP 的 UMD 镜像)用 `createdvd`。PSP 的 .iso 压成 CHD(PPSSPP 1.17+ 与 Batocera 均可读),
  其压缩格式 `.cso` / `.pbp` chdman 无法直读,跳过并提示先转 iso。工具只服务 chdman 适用的光盘
  平台;GameCube/Wii 用 Dolphin 的 RVZ,不支持 CHD,故不在范围内。
- **名字数据源**:LaunchBox Games DB 的离线全库(官方每日更新的 `Metadata.zip`,约 190MB,
  含每个游戏的 DatabaseID 与规范游戏名)。下载一次后本地按游戏名匹配取出规范名用作文件名,
  零凭据、不受每日配额限制。*(后续可把数据源做成可切换。)*
- **联网回退数据源**:当文件名与索引都在离线库查不到时,读镜像内部序列号(psx/ps2 的
  `SYSTEM.CNF`、sega 系的 IP.BIN/MD 头)去 redump.org 按序列号查正式标题,再回离线库取 id。
  redump 零凭据;联网只在电脑端发生(代理可配),默认开启,`--no-online` 可关。
- **平台范围**:光盘类(用 chdman 合并成 CHD)与卡带类(单文件 ROM,原样拷贝后改名:nes、snes、
  megadrive、n64、gamecube)。gamecube 用 RVZ/ISO,不走 CHD,归卡带类处理(只拷贝+改名)。
- **gamelist.xml**(可选子命令):按 Batocera / EmulationStation 格式,把 `out/` 里以游戏名命名的
  产物直接按文件主名写进 `gamelist.xml`。默认流程不用它(交给 skraper);保留给不想用 skraper、
  只想让 UI 显示游戏名的场景。
