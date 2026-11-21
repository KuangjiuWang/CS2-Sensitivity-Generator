# CS2 Sensitivity Generator

Windows 桌面灵敏度计算器。输入当前 CS2 灵敏度，再通过全屏悬停拉枪与动态跟枪得出修正建议。也可以用 DPI、鼠标垫行程与发力习惯计算起点。导出三位小数的灵敏度、eDPI、cm/360°，可复制控制台指令、复制 CFG 或保存为 `autoexec.cfg`。

## 运行与发布

- 预构建版本适用于 Windows 10 1809 及以上或 Windows 11（x64）。[Qt 平台支持](https://doc.qt.io/qt-6.12/windows.html)
- 直接运行 `CS2-Sensitivity-Generator.exe` 即可，无需单独安装 Python。
- 从源码启动需要 Python 3.11+。CI 使用 Python 3.12 x64。以下命令在项目根目录执行。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\main.py
```

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cmd /c scripts\build.bat
```

本地脚本安装依赖、运行测试并生成 `dist\CS2-Sensitivity-Generator.exe`。也可在已安装依赖的环境中直接运行 `python -m PyInstaller --clean --noconfirm build.spec`。构建配置生成单文件、无控制台窗口程序。

将本目录内容提交到 GitHub，确保保留隐藏的 `.github` 目录。推送版本标签即可触发 Windows x64 构建、单元测试、EXE 启动验证与 GitHub Release 上传。

```text
git tag v1.0.0
git push origin v1.0.0
```

## 使用方法

1. 输入当前 DPI 和游戏内 `sensitivity`。例如在 DPI 填 `800`，在当前 CS2 灵敏度填 `1.150`，即 920 eDPI、约 45.18 cm/360°。如果需要从鼠标垫行程估算起点，填写有效宽度和发力习惯，再按「用物理建议填入灵敏度」。两项测试都使用输入框中的数值。
2. 选择和游戏一致的画面比例，完成悬停拉枪和动态跟枪。全屏后移动鼠标，出现「已收到鼠标输入」即开始 3 秒准备倒计时。每项可选 15、30 或 60 秒。拉枪时准星擦过目标即算命中。跟枪时，目标横移或停住都应尽量保持准星在目标内。可单独选择目标移速、距离和圆靶直径。Esc 可退出，失焦取消当轮，已完成的结果予以保留。
3. 在「推荐与导出」分别复制灵敏度 CFG、准星 CFG，或复制两者的完整配置。可以将片段合并到现有 `autoexec.cfg`，也可以保存新文件到 Steam 游戏目录的 `game/csgo/cfg/`。
4. 开镜倍率单独填写，初始值为 `1.000`。训练只测无开镜状态。

### 检测鼠标 DPI

点 DPI 输入框旁的「检测 DPI」。在鼠标垫旁用尺子标出 10 cm 或其他已知距离，并在弹窗填写同一数值。把鼠标放在起点，按空格开始，保持朝向沿水平方向滑到终点。停稳后再按空格，点「填入 DPI」应用测得的值。仍可直接手填 DPI。

测量以相对移动的横向净计数乘以 2.54，再除以实际滑动的厘米数。该结果是当前设置和表面下的实测估值。滑动距离、偏离直线和鼠标转动都会影响误差。测量期间只移动待测鼠标，尽量使用较长的标定距离。[Microsoft RAWMOUSE 说明](https://learn.microsoft.com/windows/win32/api/winuser/ns-winuser-rawmouse)

### CS2 准星设置

在「测试准星」选择「准星设置／导入分享码」。可选样式 0–9，其中样式 1 为动态圆形，样式 4 为静态十字，样式 9 为静态象限。长度和厚度使用整数像素，均可填 1。准星尺寸按所填游戏画面高度和当前测试视口的物理像素高度同比缩放。输入游戏里设置准星时的分辨率高度，例如 1280×960 对应 960 px。可调整中心点、T 形、透明度和描边模式，编辑器会按样式显示相应选项。[Valve 像素单位说明](https://www.counter-strike.net/newsentry/674006995886408819) · [CS2 设置面板游戏文件](https://github.com/SteamTracking/GameTracking-CS2/blob/694f81f05cfcd1994ea9ef6baa31d4583dc1d63b/game/csgo/pak01_dir/panorama/scripts/settingsmenu_crosshair.js)

可从 CS2 的「准星／瞄准镜」设置复制新版 `CS` 分享码，粘贴后点「导入」和「应用」。测试场使用无开镜、未射击状态的准星外观。动态展开提供示意预览，游戏中的武器散布、射击后坐力和开镜效果仍由 CS2 引擎决定。[Valve 分享码更新](https://www.counter-strike.net/newsentry/675133527946166402) · [新版分享码结构](https://github.com/akiver/csgo-sharecode/blob/main/doc/code_layout.md#crosshair-cs2-v1)

### 职业选手预设

在「选手准星预设」预览并应用外观，独立在「选手灵敏度预设」应用灵敏度和开镜倍率。可自由组合两位选手的配置。默认用你填写或检测出的鼠标 DPI 换算灵敏度，公式为 `选手 DPI × 选手灵敏度 ÷ 我的 DPI`，保留三位小数。也可使用选手原始 DPI 和灵敏度，鼠标硬件 DPI 需自行调到对应数值。

预设可离线使用，资料于 2026-11-21 从 ProSettings 核对。每位选手附页面链接及页面标示的更新时间。coldzera、GeT_RiGhT、olofmeister、NEO 的页面记录为旧版非像素参数，练习准星根据当时记录的分辨率近似换算。使用新版像素资料的选手直接采用原始参数。[ProSettings 准星数据库](https://prosettings.net/tools/cs2-crosshair-database/) · [旧版静态准星像素换算参考](https://github.com/JDD310/CS2-Crosshair-Converter#2-old-units--pixels)

## 物理距离与视场角

| 发力习惯 | 舒适挥动占有效宽度 | 对应转身 |
| --- | ---: | ---: |
| 手臂流 | 90% | 270° |
| 手腕流 | 42% | 180° |
| 混合流 | 67% | 225° |

`cm/360 = 舒适挥动距离 × 360 ÷ 转身角度`，`sensitivity = 360 × 2.54 ÷ (DPI × cm/360 × 0.022)`，`eDPI = DPI × sensitivity`。导出区的 eDPI 和 cm/360° 从三位小数的实际导出值计算。发力比例为可审查的默认假设，实际 DPI 与标称 DPI 的偏差会反映到实际物理距离。

测试窗口通过 Win32 窗口过程接收 `WM_INPUT`，从前台鼠标读取相对计数。屏幕光标位置不参与计算。程序启动时启用 Per-Monitor DPI Awareness V2，全屏画布选择主界面所在显示器，隐藏光标并将它临时限制在画布范围，结束或失焦时释放限制。测试期间请只移动使用所填 DPI 的鼠标。若进入全屏后 12 秒仍未收到相对移动，程序会退出当轮并显示提示。

横向转角为 `dx × sensitivity × 0.022`，纵向按 CS2 默认俯仰比例计算。准星固定在视口中心，虚拟相机旋转后，将目标相对于相机的横纵坐标除以深度，再以对应半视场角的正切映射到视口。无开镜垂直 FOV 为 73.74°，水平 FOV 为：

| 预设 | 水平 FOV | 输出 |
| --- | ---: | --- |
| 16:9 原生 | 106.26° | 居中保持 16:9 |
| 4:3 拉伸 | 90.00° | 将 4:3 投影铺满显示器 |
| 16:10 | 100.39° | 居中保持 16:10 |

同一灵敏度下，每计数的转角与分辨率、Windows 指针速度、增强指针精确度以及 DPI 缩放无关。屏幕位移随视口尺寸和拉伸比例变化，这正是投影的一部分。4:3 预设匹配游戏的拉伸模式，16:10 预设保持比例。输入角度与标准无开镜 FOV 模型可以数值复现。端到端手感还取决于实际 DPI、游戏内轴向设置、显示缩放方式、刷新率和渲染延迟，需要在本机 CS2 中核对。

## 误差修正

- **悬停拉枪**用相邻原始输入之间的投影线段判定首次穿过目标。定位耗时从生成目标算起，过冲记录命中后 180 ms 内沿起点到目标的方向越过目标远侧边界的最大角距。过冲仅取完整观测的平均值。
- **动态跟枪**用单个持续存在的目标练习横移和反向瞄准。目标高度与前向深度固定，交替出现长横移与短反向。加速、减速和短停是本项目的训练设置。Aimlabs 公开资料说明了 Strafe Track CS2 的目标行为及创作工具的加减速、最高速度和转向设置，未列出该任务的具体数值。[Aimlabs 的 CS2 训练说明](https://aimlabs.com/articles/aimlabs/train-micros-and-flicking-in-counter-strike-2-with-the-aim-basics-routine/) · [Aimlabs 创作工具说明](https://aimlabs.com/articles/aimlabs/we-have-updated-the-aimlabs-creators-studio/)
- 目标的线速度上限取自 CS2 的 `m_flMaxSpeed`。AK-47 为 215 u/s，M4A4 和 M4A1-S 为 225 u/s，AWP 未开镜为 200 u/s、开镜为 100 u/s，持刀为 250 u/s。这里的开镜指**跟枪目标持 AWP 时的移动状态**。项目仍用你的无开镜视角测算灵敏度。[CS2 游戏文件镜像](https://github.com/SteamTracking/GameTracking-CS2/blob/master/game/csgo/pak01_dir/scripts/weapons.vdata)
- 目标以横向位移 `x` 和前向深度 `d` 投影，视角为 `atan(x/d)`。全速穿过正前方时的角速度为 `v/d` 弧度每秒。默认 AK-47、600 u 对应约 20.5°/秒，同一移速下 400 u 对应约 30.8°/秒。可调距离为 300–1600 u，圆靶角直径为 0.5°–5.0°，默认 1.6°。圆靶直径同时设置画面大小和命中范围。
- 命中时长采用单调时钟积分。只在每次起步至少 200 ms 后的匀速段统计滞后与超前。准星沿运动方向落后或领先约 1° 时分别记为滞后或超前，该阈值独立于圆靶大小。
- 单档训练报告拉枪、过冲和跟枪数据。灵敏度建议由下面的盲测产生。未完成匹配当前设置的盲测时，CFG 沿用当前灵敏度。
- 倒计时和评分从 `perf_counter` 的单调时间差计算，Qt 精确定时器驱动刷新。UI 卡顿时，剩余时间按实际流逝校正。

### 盲测 A/B/C

以当前灵敏度为中间值，默认生成 ±5% 两个候选，支持自定义 0.5%–25%。Aimlabs 公开说明会结合拉枪误差和跟枪表现，随训练数据积累更新建议。本项目参考这些公开指标，采用下面两轮受控对比。[Aimlabs Sensitivity Finder 官方说明](https://aimlabs.com/articles/aimlabs/aimlabs-mouselabs-explained-smarter-sensitivity-finder-better-results/)

1. **初筛**。三档随机分配 A、B、C。每档使用同一张 16 方向目标表，各有 8 个近角（6°–12°）和远角（16°–28°）目标，每个目标 1.75 秒。各档另外运行 15 秒同一跟枪路线。没有候选领先至少 1 分且通过命中门槛时，保留当前值并结束。
2. **复核**。领先候选与当前值使用 D、E 两个新代号，相对出场顺序反转。交换各方向的近远角距离并重抽顺序和角度，跟枪换用倒序路点。两档在复核内共享场景。复核领先至少 2 分、两轮平均领先至少 3 分且两轮都通过命中门槛，才建议试用领先候选。最终统一揭晓，按 Esc 可取消整组。

拉枪和跟枪各计 50 分。拉枪命中项 35 分，已观测的平均过冲最多扣除该项的四分之一。移动后定位项 15 分，按命中次数与移动耗时计算，未命中得零。跟枪命中时长占 35 分，另有 15 分按准星离目标中心的距离连续计分，距离达到 4 倍靶半径时该样本得零。启动反应和跟枪滞后继续作为诊断指标。每档每轮须完成 16 个拉枪目标和 15 秒跟枪，拉枪至少命中 6 个且跟枪命中时长至少 10%。候选的拉枪最多比当前值少命中 1 个，跟枪最多下降 5 个百分点。这些阈值是实用判定规则。

### 16 方向轨迹与拉枪分析

完成拉枪后，从结果区打开「16 方向轨迹分析」。以每次目标生成时的准星为原点，按目标方向将一周分成 16 个等宽的 22.5° 扇区。每组 16 个目标打乱顺序，各方向出现一次。短测试可能只覆盖部分方向，报告会标注覆盖数和每个方向的次数。

- 每个方向显示命中次数、命中率、启动反应、移动后定位、过冲、直达率和横偏。启动反应从目标出现计到视角首次移动 0.35°，移动后定位从该时刻计到首次命中。跟枪分别统计目标起步或反向后的顺向响应，以及从响应到首次连续命中 80 ms 的起点。
- 少于 3 个目标的方向会标记为样本不足。点「一键补测样本不足方向」时只生成这些方向缺少的目标，完成后追加至当前报告。普通拉枪测试结束时尚未给足 2.5 秒的未命中目标不计入分母。
- 直达率是起点到首次命中点的直线距离除以实际轨迹长度。横偏是命中前离理想瞄准直线最大的横向偏差，再对该方向的命中样本取平均。路径和偏差在以原始视角为基准的局部角坐标中计算。
- 左侧选中方向可查看该方向最近六条轨迹，青线表示命中前路径，黄绿线表示命中后。图形抽样绘制，指标按检测到的原始移动计算。
- 「清除本次测试数据」会清空界面上的本次拉枪、跟枪及盲测结果，DPI 等参数和已保存的历史继续沿用。

### 本地历史

每轮完成后将 DPI、灵敏度、准星及可用的 16 方向统计保存到 Windows 本地应用数据目录的 `practice-history.json`，同时记住当前配置。盲测完成后分别保存初筛三档和已完成的复核两档。历史面板可选择任意两轮，按方向对比命中率、反应、定位、过冲、直达率和横偏。点击右上角「清除所有历史」后需确认，确认后仍保留当前配置。

## 工程结构

- `src/core/` 包含 Win32 输入、摄像机和数值模型、遥测统计。
- `src/ui/` 包含参数与导出界面、全屏测试场。
- `tests/` 覆盖物理换算、视场角、投影、跨目标判定和统计。
- `scripts/`、`build.spec` 和 `.github/workflows/release.yml` 提供 Windows 构建发布流程。

## 协议与参考

本项目代码使用 MIT。PySide6 Essentials 使用 Qt for Python 提供的 LGPLv3 条款，PyInstaller 使用带 bootloader 例外的 GPL。第三方许可与源码信息见 [THIRD_PARTY.md](THIRD_PARTY.md)。

- [Microsoft Win32 Raw Input](https://learn.microsoft.com/en-us/windows/win32/inputdev/using-raw-input)
- [Microsoft Per-Monitor DPI Awareness](https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process)
- [Valve Source SDK 视场角实现](https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/client/viewrender.cpp)
