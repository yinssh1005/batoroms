---
id: batocera-rom-cli-architecture
type: architecture-design
status: active
title: Batocera ROM 整理 CLI — 架构
parent: batocera-rom-cli
---

# Batocera ROM 整理 CLI — 架构

把 [batocera-rom-cli](goal-and-requirements.md) 的三步流水线落成一个 Python CLI 的结构设计:
各阶段的职责、数据如何从 `origin-roms/` 流到 `out/`、以及几个贯穿全局的约束。

## Drivers

- **电脑端一次做完,Batocera 零联网**:所有查询/生成都在用户电脑上完成(代理可配),
  Batocera 只拷贝、只显示。
- **批量不被卡住**:整理一整批游戏时,疑难件(匹配不到、多候选)不能打断流程。
- **可重跑、不毁原件**:原始镜像只读,成品另写到 `out/`,任何一步可单独重跑。

## Decisions

### 管线与命令

单一 Python 包,提供一条流水线命令加若干分步子命令(都作用于按系统分好的目录):

- `init` — 创建输入/输出目录骨架:`origin-roms/` 下为每个**光盘类平台**建子目录、`out/`
  先建空(平台子目录后续按需生成);幂等,已存在的目录跳过不删。用户把镜像放进去。
- `run` — 一键顺序跑完 merge → rename → gamelist。
- `merge` / `rename` / `gamelist` — 分步子命令,便于调试或单独重跑某一步。

分步子命令之间通过 `out/` 下的文件(及一份进度/映射记录)衔接,而非进程内传参,这样任意一步
都能独立重跑。

### 目录与数据流

```
origin-roms/<system>/   原始镜像(只读输入),按 Batocera system 目录分类
        │  merge   (chdman createcd / createdvd)
        ▼
out/<system>/<id>.chd   成品:每盘一个 chd,文件名=数字游戏 ID
              <id>.m3u   多盘游戏额外生成,串起同一游戏各盘
              gamelist.xml   把 <id>.chd / <id>.m3u 映射到正确游戏名
```

- `origin-roms/<system>/` 子目录由 `init` 预先建好;`out/` 的平台子目录在产出成品时按需创建。
- 原始镜像只读;所有产物写到 `out/<system>/`。
- **平台范围**:本工具只服务 chdman 适用的光盘(CD/DVD)类平台,卡带类不在范围内;GameCube/Wii
  用 Dolphin 的 RVZ、不支持 CHD,也排除。当前光盘平台集合(14 个)维护在系统注册表模块
  `batoroms/systems.py` 的 `DISC_SYSTEMS` 中,短名用 Batocera `es_systems.yml` 官方叫法:psx,
  ps2, megacd, saturn, dreamcast, pcenginecd, neogeocd, 3do, amigacd32, naomi, atomiswave,
  pcfx, fmtowns, cdi。

### 系统(平台)识别

从 `origin-roms/<system>/` 的目录名按 Batocera 的 system 约定推断平台(如 `psx`/`ps2`/
`dreamcast`)。平台决定两件事:chdman 用 `createcd` 还是 `createdvd`、以及在 LaunchBox 库里按哪个
平台名过滤。推断不出时报错提示。平台清单与各类映射统一落在系统注册表模块 `batoroms/systems.py`
(`DISC_SYSTEMS` 短名列表、`DVD_SYSTEMS={ps2}` 与 `chdman_mode()` 返回 createcd/createdvd;
system→LaunchBox 平台名映射随 rename 功能补入)。

### 游戏文件分组

扫描某个 `<system>` 目录,把属于同一个游戏的镜像文件归成一组:

- `.cue` + 它引用的 `.bin`(可多条 track)→ 一组;
- 独立的 `.iso` → 一组;`.gdi` + 其 track 文件 → 一组;
- 文件名含盘号标记(如 `(Disc 1)` / `Disc 2` / `CD1`)的,按去盘号后的基名归为同一个**多盘
  游戏**,每盘各自合并成一个 chd,再生成一个 `.m3u`(按盘号排序、只列实际生成的盘)供
  模拟器自动换盘。
- **不支持的格式**:`.cdi`(DiscJuggler)chdman 无法直接读,**跳过并在报告提示先转 gdi/cue**。

### 合并为 CHD(`merge`)

对每个主文件调用随包分发的 `chdman`(`batoroms/vendor/chdman/`,非 Windows 回退 PATH):CD 类
平台用 `createcd`,DVD 类(仅 ps2)用 `createdvd`。输出到 `out/<system>/`,**文件名沿用源主文件
基名**(改成 `<id>.chd` 是后续 rename 步的事)。已存在同名 chd/m3u 则跳过,`--force` 重建;
单个游戏失败或跳过不中断整批,结束打印报告。

### ID / 名字查询(LaunchBox 离线库)

- 数据源是 LaunchBox Games DB 的离线全库(`Metadata.zip`):首次使用时下载并缓存到本地,
  解析出 (平台, 游戏名, 数字 DatabaseID)。缓存位置与更新策略在模块设计阶段定。
- **游戏名来源**:默认从文件名提取(去扩展名、区域/版本标签、盘号标记);若用户提供索引
  文件(`.txt`,每行 `文件名<分隔>游戏名`),则**以索引为权威**覆盖文件名推断。
- 在"当前平台"范围内按游戏名匹配,取其 DatabaseID 作为 `<id>`。
- **疑难处理**:能唯一确定的自动采用;**多个候选或匹配不到的一律跳过**,记进报告,不阻塞流程。
  全部跑完后输出一份清单(哪些成功、哪些跳过及原因)供用户回头手动处理。

### gamelist.xml 生成

为 `out/<system>/` 里改名后的 `<id>.chd`(多盘则为 `<id>.m3u`)生成 / 更新 EmulationStation 格式
的 `gamelist.xml`,写入 `<path>` 与正确的 `<name>`。**第一版只写游戏名,不写封面**(封面见目标
文档的 Non-Goals)。具体字段集在模块设计阶段定。

## Invariants

- **原始镜像只读**:`origin-roms/` 下的文件永不被修改或删除;所有产物只写 `out/`。
- **文件名即 ID**:`out/` 中每个成品的主名是数字游戏 ID;游戏名只存在于 `gamelist.xml`,
  不进文件名。
- **不依赖 Batocera 联网**:名字(及以后封面)一律由本工具写进 `gamelist.xml`,不靠 Batocera
  自带刮削——理由见目标文档。
- **疑难件跳过而非中断**:任何单个游戏的失败都不终止整批处理,最终以报告呈现。

## Out of scope

- 封面 / 其它媒体抓取(第一版 Non-Goal,后续版本接入,可能切换到含封面的数据源)。
- 对 Batocera 自带刮削器的任何集成或触发。
- 多账号/凭据管理(第一版数据源零凭据)。
