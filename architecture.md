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

- **电脑端一次做完,Batocera 零联网**:所有查询/改名都在用户电脑上完成(代理可配),
  封面交给电脑端的 skraper。Batocera 只拷贝、只显示。
- **批量不被卡住**:整理一整批游戏时,疑难件(匹配不到、多候选)不能打断流程。
- **可重跑、不毁原件**:原始镜像只读,成品另写到 `out/`,任何一步可单独重跑。

## Decisions

### 管线与命令

单一 Python 包,提供一条流水线命令加若干分步子命令(都作用于按系统分好的目录):

- `init` — 创建输入/输出目录骨架:`origin-roms/` 下为每个平台(光盘类 + 卡带类)建子目录、
  `out/` 先建空(平台子目录后续按需生成);幂等,已存在的目录跳过不删。用户把镜像/ROM 放进去。
- `run` — 一键流水线:索引缺失/过旧时自动先 `update-db`,再顺序跑 merge → rename
  (参数 `--system`/`--index`/`--force` 分发到各步)。封面由 skraper 另外抓,所以 `run` **不**再跑 gamelist。
- `merge` / `rename` — 分步子命令,便于调试或单独重跑某一步。
- `gamelist` — 可选子命令(按文件主名生成 gamelist.xml),不进 `run`;给不用 skraper 的场景备用。

分步子命令之间通过 `out/` 下的文件(及一份进度/映射记录)衔接,而非进程内传参,这样任意一步
都能独立重跑。

### 目录与数据流

```
origin-roms/<system>/   原始镜像/ROM(只读输入),按 Batocera system 目录分类
        │  merge   (光盘:chdman createcd/createdvd;卡带:原样拷贝)
        ▼
out/<system>/<游戏名>.chd    光盘成品:每盘一个 chd,文件名=游戏名
              <游戏名>.m3u    多盘游戏额外生成,串起同一游戏各盘
              <游戏名>.<ext>  卡带成品:单文件 ROM 原扩展名,文件主名=游戏名
        │  skraper(外部工具,按文件名抓封面)
        ▼
out/<system>/gamelist.xml + media/   封面等媒体(由 skraper 生成)
```

- `origin-roms/<system>/` 子目录由 `init` 预先建好;`out/` 的平台子目录在产出成品时按需创建。
- 原始镜像/ROM 只读;所有产物写到 `out/<system>/`(卡带通过拷贝产生一份副本,以保持原始只读)。
- **平台范围**:分两类,统一维护在系统注册表 `batoroms/systems.py`,短名用 Batocera `es_systems.yml`
  官方叫法(即 `roms/<system>/` 目录名)。
  - **光盘类**(`DISC_SYSTEMS`,15 个):psx, ps2, megacd, saturn, dreamcast, pcenginecd,
    neogeocd, 3do, amigacd32, naomi, atomiswave, pcfx, fmtowns, cdi, psp——chdman 合并成 CHD。
    PSP 的 UMD 镜像(.iso)走 createdvd;`.cso`/`.pbp` chdman 无法直读,跳过并提示先转 iso。
  - **卡带类**(`CART_SYSTEMS`):nes, snes, megadrive, n64, gamecube——单文件 ROM,chdman 不适用,
    merge 只把 `CART_EXTS` 匹配的 ROM 原样拷贝到 `out/`,由 rename 按游戏名改名。gamecube 用
    RVZ/ISO(不走 CHD),归入卡带类处理。`ALL_SYSTEMS = DISC_SYSTEMS + CART_SYSTEMS`。

### 系统(平台)识别

从 `origin-roms/<system>/` 的目录名按 Batocera 的 system 约定推断平台(如 `psx`/`nes`/
`dreamcast`)。平台决定几件事:是光盘类(chdman `createcd`/`createdvd`)还是卡带类(原样拷贝)、
以及在 LaunchBox 库里按哪个平台名过滤。平台清单与各类映射统一落在系统注册表模块 `batoroms/systems.py`
(`DISC_SYSTEMS`/`CART_SYSTEMS`/`ALL_SYSTEMS` 短名列表、`CART_EXTS` 各卡带平台 ROM 扩展名、
`DVD_SYSTEMS={ps2, psp}`、`ZIP_SYSTEMS={dreamcast}` 与 `chdman_mode()`、`is_cart()`;system→LaunchBox 平台名映射 `SYSTEM_TO_LAUNCHBOX`)。

### 游戏文件分组

扫描某个 `<system>` 目录,把属于同一个游戏的镜像文件归成一组:

- `.cue` + 它引用的 `.bin`(可多条 track)→ 一组;
- 独立的 `.iso` → 一组;`.gdi` + 其 track 文件 → 一组;
- **zip 打包**(仅 `ZIP_SYSTEMS`,即 dreamcast):一个 `.zip` = 一张盘,作为主文件参与分组,游戏名与盘号取
  **zip 主名**(包内 gdi 常叫 `disc.gdi` 这类无意义名字)。包内(可含子目录)须恰有一个主文件:优先
  `.gdi`/`.cue`,都没有才看 `.iso`(这样 gdi 引用的 `.iso` 数据轨不会被当成主文件);没有或多个记失败。
  选择规则由 `disc_meta.zip_primary_member()` 独家定义,merge 与序列号读取共用。其它平台的 zip 不碰
  (naomi/atomiswave 的 zip 是 MAME romset,不是光盘包)。只用标准库 `zipfile`,不支持 7z/rar。
- 文件名含盘号标记(如 `(Disc 1)` / `Disc 2` / `CD1`)的,按去盘号后的基名归为同一个**多盘
  游戏**,每盘各自合并成一个 chd,再生成一个 `.m3u`(按盘号排序、只列实际生成的盘)供
  模拟器自动换盘。
- **不支持的格式**:`.cdi`(DiscJuggler)chdman 无法直接读,**跳过并在报告提示先转 gdi/cue**;
  PSP 的 `.cso` / `.pbp` 同样 chdman 无法直读,**跳过并提示先转 iso**(只合并 `.iso`)。

### 准备产物到 out/(`merge`)

- **光盘平台**:对每个主文件调用随包分发的 `chdman`(`batoroms/vendor/chdman/`,非 Windows 回退
  PATH):CD 类用 `createcd`,DVD 类(ps2 与 psp)用 `createdvd`。输出到 `out/<system>/`,**文件名
  沿用源主文件基名**(改成游戏名是后续 rename 步的事)。
  - zip 主文件:产物已存在且无 `--force` 时不解压直接跳过;否则解压到
    `out/<system>/.batoroms-tmp/<zip主名>/`(与产物同盘,不把 GB 级镜像塞进系统盘 TEMP),对包内主文件
    跑 chdman,输出 `out/<system>/<zip主名>.chd`,无论成败都删掉临时目录。origin 里的 zip 保持只读。
- **卡带平台**:chdman 不适用,把 `CART_EXTS` 匹配的单文件 ROM 用 `shutil.copy2` **原样拷贝**到
  `out/<system>/`(保 origin 只读),不生成 m3u。大镜像(n64/gamecube)会在 out/ 产生一份拷贝(
  占磁盘);v1 接受,后续可加硬链接/移动选项。

已存在同名产物则跳过,`--force` 重建/覆盖;单个游戏失败或跳过不中断整批,结束打印报告。
merge 的 `--system` 校验与默认集合为 `ALL_SYSTEMS`。

### ID / 名字查询(LaunchBox 离线库:`update-db` + `rename`)

- **数据源与缓存**:LaunchBox Games DB 的 `Metadata.zip`(`gamesdb.launchbox-app.com/Metadata.zip`)。
  `batoroms update-db` 显式下载(`urllib`,带浏览器 UA 避 403,自动走 `HTTP(S)_PROXY`),
  流式(`iterparse`)解析 `Metadata.xml` 蒸馏成紧凑索引 `~/.batoroms/launchbox/index.json`(version 2):
  `{"platforms": {短名: {归一化名: id}}, "names": {id: 规范名}}`,只含 15 平台、并入 LaunchBox
  别名;同名多 id 记为冲突。`platforms` 供 rename 查 id,`names` 供 rename 取规范名作文件名。
  读取时校验 version,缺失/过旧提示先跑 update-db。平台名映射在 `systems.py` 的 `SYSTEM_TO_LAUNCHBOX`
  (含卡带平台:nes/snes/megadrive/n64/gamecube)。
- **搜索名来源**:默认从文件名提取(去扩展名、区域/版本标签、盘号标记)并归一化;若用户提供
  索引文件(`.txt`,每行 `基名 | 游戏名`,`#` 注释),则**以索引为权威**覆盖。
- **改名(用游戏名,不再是 ID)**:按归一化名在当前平台匹配到 DatabaseID 后,取 `names[id]`
  规范名作文件主名(经 `names.safe_filename()` 过滤 Windows 非法字符、冒号转 " - ")。光盘:
  单盘 `<名>.chd`,多盘 `<名> (Disc N).chd` + 重写 `<名>.m3u`;卡带:保留原扩展名 `<名>.<ext>`,无 m3u。
- **查不到→文件名回退**:DB 与 online 都查不到时,回退用**清理后的搜索名**命名(报告列在
  「按文件名回退命名」),skraper 仍能按名字命中。
- **疑难处理**:**多候选冲突、目标已存在的一律跳过**记报告;目标名已等于当前名的记为幂等
  跳过。结束打印小结。
- **online 回退(内部序列号→redump)**:文件名/索引在离线库查不到时(仅光盘平台),回退前先读
  该游戏**原始镜像的内部序列号**,拿去 redump.org 查正式标题,再用标题回到离线库取 id。默认
  开启,`rename --no-online`(及 `run --no-online`)关闭。卡带平台不读序列号,直接走文件名回退。
  - 读序列号:`batoroms/disc_meta.py` 从 `origin-roms/<system>/` 的生镜像(.cue→.bin /
    .iso / .gdi→track;`ZIP_SYSTEMS` 还包括 .zip,不解压、直接在包内读主文件与 track 头部)
    按去盘号基名找回主文件后解析;psx/ps2 解析 ISO9660 取 `SYSTEM.CNF`
    的 BOOT 序列号,saturn/dreamcast/megacd 读 IP.BIN / MD 头的产品号,psp 读 ISO9660 根目录
    `UMD_DATA.BIN` 首字段 gamecode;其余平台与解析失败
    返回 None(交回常规跳过)。支持清单见 `disc_meta.SERIAL_SYSTEMS`。
  - 查标题:`batoroms/online.py` 走 `redump.org/discs/system/<code>/quicksearch/<serial>/`
    (`urllib`+浏览器 UA,自动走 `HTTP(S)_PROXY`,带超时;失败/无命中返回 None)。短名→
    redump system 代码映射在 `systems.py` 的 `SYSTEM_TO_REDUMP`。
  - 结果:救回的游戏按 `names[id]` 规范名改名,报告单列“online 回退救回”;回退各阶段失败最终
    落到文件名回退。联网只发生在电脑端(与 update-db 一致),Batocera 端零联网不变。

### 封面抓取(skraper,外部工具)

文件改成游戏名后,封面/截图等媒体交给电脑端的第三方刮削器 [Skraper](https://www.skraper.net/)
(基于 ScreenScraper):它按 `out/<system>/` 里的文件名(即游戏名)搜索下载封面、按 Batocera
媒体目录摆好并写进 `gamelist.xml`。这正是本工具改用游戏名作文件名的原因(文件名匹配比数字
ID / CHD 哈希稳)。skraper 是独立工具,本项目不集成也不代下载;联网刮削同样在电脑端。

### gamelist.xml 生成(`gamelist`,可选子命令)

不进 `run` 流水线;保留给不用 skraper、只想让 Batocera UI 显示游戏名的场景。文件名此时已是
游戏名,所以显示名**直接取文件主名**(不再按 id 反查离线库)。扫描 `out/<system>/` 生成 / 合并
EmulationStation 格式的 `gamelist.xml`(`<path>` 用 `./` 相对)。
- 单盘 `<名>.chd` / 卡带 ROM → 可见条目;多盘 `<名>.m3u` → 可见条目,各盘 `<名> (Disc N).chd`
  → `<hidden>true</hidden>`,UI 只显一个游戏。
- **合并**:已有 `gamelist.xml` 则按 path 更新/新增我们的 `<game>`,保留其它条目。

## Invariants

- **原始镜像只读**:`origin-roms/` 下的文件永不被修改或删除;所有产物只写 `out/`。
- **文件名即游戏名**:`out/` 中每个成品的主名是人类可读的游戏名(经 safe_filename 过滤),这正是
  skraper 能按名字抓封面的前提。
- **不依赖 Batocera 联网**:改名与(电脑端 skraper 的)封面都在电脑端做好,Batocera 只显示、
  零联网——理由见目标文档。
- **疑难件跳过而非中断**:任何单个游戏的失败都不终止整批处理,最终以报告呈现。

## Out of scope

- 封面 / 其它媒体抓取**本身**:由外部工具 skraper 在电脑端完成,本项目不集成、不触发、不代下载。
- 对 Batocera 自带刮削器的任何集成或触发。
- 多账号/凭据管理(本工具数据源零凭据;skraper 的 ScreenScraper 账号由用户在 skraper 里自配)。
- 卡带大镜像拷贝的磁盘优化(硬链接/移动):v1 用普通拷贝,待后续。
