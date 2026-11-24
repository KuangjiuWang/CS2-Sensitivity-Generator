# CS2 Sensitivity Generator

面向 Windows 和 macOS 的桌面灵敏度计算器。输入当前 CS2 灵敏度，再通过全屏训练和同项盲测得出建议。也可以用 DPI、鼠标垫行程与发力习惯计算起点。导出三位小数的灵敏度、eDPI、cm/360°，可复制控制台指令、复制 CFG 或保存为 `autoexec.cfg`。

## 运行与发布

### Windows

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

将本目录内容提交到 GitHub，确保保留隐藏的 `.github` 目录。推送新版本标签，或在 `main` 上提交新的 `release/version.txt`，会构建并验证 Windows 和两种 macOS 版本，再把它们与源码一起发布到同一个 GitHub Release。发布说明位于 `release/notes.md`。

```text
git tag v1.0.0
git push origin v1.0.0
```

### macOS

构建流程以 macOS 15 为目标，分别生成 Apple 芯片（arm64）和 Intel（x86_64）版本。训练优先使用实体鼠标的原始输入。触控板或收不到原始位移的设备可用 macOS 兼容输入开始训练，测试场会显示当前模式。兼容输入受系统指针设置影响，建议在拟用于 CS2 的实体鼠标上复测推荐值。DPI 检测需要能发送原始位移的实体鼠标。Valve 的 CS2 原生版支持 Windows 和 SteamOS/Linux。macOS 上可独立运行本训练器，再把导出的 CFG 用于运行 CS2 的环境。[Apple GCMouseInput](https://developer.apple.com/documentation/gamecontroller/gcmouseinput) · [CS2 系统要求](https://store.steampowered.com/app/730/CounterStrike_2/#sysreq_app_730)

在项目根目录创建环境并从源码启动。Apple 芯片上使用 arm64 Python，Intel 上使用 x86_64 Python。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/main.py
```

在同一个环境中运行 `bash scripts/build-macos.sh`，生成 `dist/CS2-Sensitivity-Generator.app` 和对应架构的 ZIP。本地打包流程使用 PyInstaller 默认签名行为，未进行 Apple 公证。GitHub Actions 的「macOS Build」可以手动运行，两个安装包分别保存在该次运行的 Artifacts 中。

## 使用方法

1. 在 CS2 的「设置 → 键盘和鼠标」查看鼠标灵敏度，或在开发者控制台输入 `sensitivity` 查看当前值。在软件里分别填写鼠标实际 DPI 和「CS2 步枪灵敏度」。例如 `800 × 1.150` 要分开填 `800` 和 `1.150`。如果没有合适的起点，填写鼠标垫有效宽度和发力习惯，再点「用物理建议填入灵敏度」。
2. 选择和 CS2 一致的画面比例。想快速拿到建议，选一个项目测 15、30 或 60 秒。想综合六种项目，点「一键测试六项」。想实测三档灵敏度，再选「开始六项 A/B/C 盲测」。全屏后先移动鼠标开始 3 秒倒计时，左键击中目标，按 Esc 可退出。失焦会取消当轮。
3. 在「推荐与导出」查看当前值、建议值与调整理由。普通训练和一键六项允许保留当前值，调整幅度最多 3%。点「应用建议到当前步枪灵敏度」即可在软件里试用，右侧换算表会随输入框更新。
4. 把「仅复制灵敏度 CFG」得到的指令粘贴到 CS2 控制台，即可在游戏内应用。要同时设置准星，可复制完整配置或保存 `autoexec.cfg`，放到 Steam 游戏目录的 `game/csgo/cfg/`。已有配置文件时可把生成的片段合并进去。

### CS2 灵敏度是什么

`sensitivity` 是游戏内鼠标转向速度的倍数。同样的鼠标位移下，`1.150` 的转角是 `1.000` 的 1.15 倍。DPI 决定鼠标每移动一英寸产生多少计数，CS2 则用 `水平转角 = 原始计数 × 0.022 × sensitivity` 把计数换成角度。以 `800 DPI × 1.150` 为例，eDPI 是 `920`，水平转完一圈约需 `45.18 cm`。

### 换算到其他游戏

「跨游戏腰射换算」按相同的鼠标 DPI 匹配**水平转身距离（cm/360°）**，使用当前输入框里的 CS2 值。先在目标游戏里找到对应的鼠标选项，再填表中的数。以 `800 DPI × 1.150` 为例：

| 游戏 | 游戏内设置 | 示例 |
| --- | --- | ---: |
| 无畏契约（VALORANT） | 常规 → 鼠标 → 瞄准灵敏度（Sensitivity: Aim） | 0.361 |
| 战地 6 | 鼠标与键盘 → 步兵 → 步兵鼠标瞄准灵敏度 | 约 13 |
| PUBG: BATTLEGROUNDS | 控制 → 鼠标 → 常规灵敏度，第一人称 FOV 90° | 约 35 |
| Apex Legends | 鼠标／键盘 → 鼠标灵敏度 | 1.15 |

无畏契约用 `CS2 灵敏度 × 0.022 ÷ 0.07`，Apex 的默认水平系数与 CS2 相同。战地 6 使用公开的实测模型估算步兵滑块，PUBG 常规灵敏度为对数滑块，换算随第一人称 FOV 变化，可在表下填写 PUBG 实际使用的 FOV。战地 6 和 PUBG 显示四舍五入后的整数。精确目标超出游戏设置范围时会提示「超出范围」。[Aimlabs 换算口径](https://support.aimlabs.com/hc/en-us/articles/38493112353815-PC-Sensitivity-Guide) · [战地 6 官方设置指南](https://help.ea.com/en/articles/battlefield/battlefield-6/pc-and-controller-settings-guide/) · [战地 6 实测模型](https://sensitivitymatch.com/mouse-sensitivity-converter/battlefield-6/) · [PUBG 实测换算](https://github.com/Lokx-x/pubg-sensitivity-calculator/blob/main/PUBG_Sensitivity_Calculator_Manual_EN_v1_0.md)

在目标游戏训练场中关闭鼠标加速，保持腰射，选一个固定地标，缓慢横移鼠标转一圈并量距离。鼠标垫不够长时可量 180°，目标距离是表上 `cm/360°` 的一半。游戏 FOV、武器开镜、分辨率拉伸都会影响屏幕上的移动观感，ADS、倍镜和载具需在各游戏单独调整。

### 检测鼠标 DPI

点 DPI 输入框旁的「检测 DPI」。在鼠标垫旁用尺子标出 10 cm 或其他已知距离，并在弹窗填写同一数值。把鼠标放在起点，按空格开始，保持朝向沿水平方向滑到终点。停稳后再按空格，点「填入 DPI」应用测得的值。仍可直接手填 DPI。

测量以相对移动的横向净计数乘以 2.54，再除以实际滑动的厘米数。该结果是当前设置和表面下的实测估值。滑动距离、偏离直线和鼠标转动都会影响误差。测量期间只移动待测鼠标，尽量使用较长的标定距离。[Microsoft RAWMOUSE 说明](https://learn.microsoft.com/windows/win32/api/winuser/ns-winuser-rawmouse)

Mac 版从第一只有效移动的实体鼠标读取整次测量。按空格结束时先计入已接收的位移，所用鼠标断开后该次测量作废。

### CS2 准星设置

在「测试准星」选择「准星设置／导入分享码」。可选样式 0–9，其中样式 1 为动态圆形，样式 4 为静态十字，样式 9 为静态象限。长度和厚度使用整数像素，均可填 1。准星尺寸按所填游戏画面高度和当前测试视口的物理像素高度同比缩放。输入游戏里设置准星时的分辨率高度，例如 1280×960 对应 960 px。可调整中心点、T 形、透明度和描边模式，编辑器会按样式显示相应选项。[Valve 像素单位说明](https://www.counter-strike.net/newsentry/674006995886408819) · [CS2 设置面板游戏文件](https://github.com/SteamTracking/GameTracking-CS2/blob/694f81f05cfcd1994ea9ef6baa31d4583dc1d63b/game/csgo/pak01_dir/panorama/scripts/settingsmenu_crosshair.js)

可从 CS2 的「准星／瞄准镜」设置复制新版 `CS` 分享码，粘贴后点「导入」和「应用」。测试场使用无开镜、未射击状态的准星外观。动态展开提供示意预览，游戏中的武器散布、射击后坐力和开镜效果仍由 CS2 引擎决定。[Valve 分享码更新](https://www.counter-strike.net/newsentry/675133527946166402) · [新版分享码结构](https://github.com/akiver/csgo-sharecode/blob/main/doc/code_layout.md#crosshair-cs2-v1)

### 职业选手预设

在「选手准星预设」预览并应用外观，独立在「选手灵敏度预设」应用步枪灵敏度。可自由组合两位选手的配置。默认用你填写或检测出的鼠标 DPI 换算灵敏度，公式为 `选手 DPI × 选手灵敏度 ÷ 我的 DPI`，保留三位小数。也可使用选手原始 DPI 和灵敏度，鼠标硬件 DPI 需自行调到对应数值。

预设可离线使用，资料于 2026-11-21 从 ProSettings 核对。每位选手附页面链接及页面标示的更新时间。coldzera、GeT_RiGhT、olofmeister、NEO 的页面记录为旧版非像素参数，练习准星根据当时记录的分辨率近似换算。使用新版像素资料的选手直接采用原始参数。[ProSettings 准星数据库](https://prosettings.net/tools/cs2-crosshair-database/) · [旧版静态准星像素换算参考](https://github.com/JDD310/CS2-Crosshair-Converter#2-old-units--pixels)

## 物理距离与视场角

| 发力习惯 | 舒适挥动占有效宽度 | 对应转身 |
| --- | ---: | ---: |
| 手臂流 | 90% | 270° |
| 手腕流 | 42% | 180° |
| 混合流 | 67% | 225° |

`cm/360 = 舒适挥动距离 × 360 ÷ 转身角度`，`sensitivity = 360 × 2.54 ÷ (DPI × cm/360 × 0.022)`，`eDPI = DPI × sensitivity`。导出区的 eDPI 和 cm/360° 从三位小数的实际导出值计算。发力比例为可审查的默认假设，实际 DPI 与标称 DPI 的偏差会反映到实际物理距离。

Windows 通过 `WM_INPUT` 读取相对计数，并启用 Per-Monitor DPI Awareness V2。macOS 优先通过 `GCMouse` 读取原始相对位移，使用 Qt Cocoa 的 Retina 缩放。如果只有 `NSEvent` 收到移动，就用它的相对位移进入兼容模式。Mac 版确认收到移动后才锁定指针，本次全屏测试使用同一种输入来源。全屏画布选择主界面所在显示器，退出或失焦时恢复指针。若进入全屏后 12 秒仍未收到相对移动，程序会退出当轮并显示提示。[Apple 鼠标输入与光标处理](https://github.com/apple/game-porting-toolkit/blob/main/game-porting-skills/skills/setting-up-macos-window/references/mouse-and-cursor.md)

横向转角为 `dx × sensitivity × 0.022`，纵向按 CS2 默认俯仰比例计算。准星固定在视口中心，虚拟相机旋转后，将目标相对于相机的横纵坐标除以深度，再以对应半视场角的正切映射到视口。无开镜垂直 FOV 为 73.74°，水平 FOV 为：

| 预设 | 水平 FOV | 输出 |
| --- | ---: | --- |
| 16:9 原生 | 106.26° | 居中保持 16:9 |
| 4:3 拉伸 | 90.00° | 将 4:3 投影铺满显示器 |
| 16:10 | 100.39° | 居中保持 16:10 |

同一灵敏度下，每计数的转角与分辨率、Windows 指针速度、增强指针精确度以及 DPI 缩放无关。屏幕位移随视口尺寸和拉伸比例变化，这正是投影的一部分。4:3 预设匹配游戏的拉伸模式，16:10 预设保持比例。输入角度与标准无开镜 FOV 模型可以数值复现。端到端手感还取决于实际 DPI、游戏内轴向设置、显示缩放方式、刷新率和渲染延迟，需要在本机 CS2 中核对。

## 误差修正

### 训练顺序

项目顺序按用户提供的演示视频保留。背景为原创低对比度场景，分别取深灰、冷蓝灰、暖色天光和中性灰。球径依据视频画面中的相对尺寸估算，使用角直径以适配分辨率和视场角。各项目自动设定球径。

| 顺序 | 视频中的项目名 | 目标生成与球径 |
| --- | --- | --- |
| 1 | 多段直线追枪 | 点中一个固定金球就移除一个。五球清空后，从整个出靶区重抽位置，避开上一组球位。球径 1.76°。 |
| 2 | VT sky Dots Micro Csgo | 窄走廊内两颗球独立分段变速横移，偶尔短停。命中后补靶，球径 1.34°。 |
| 3 | 六目标终极 | 六个静止细球，命中后补靶并保留最小间距，球径 0.92°。 |
| 4 | Wide wide wall 6 targets | 六颗较大的静止球覆盖 104° 横向范围，球径 2.04°。 |
| 5 | VT Phaseshot Wide Small | 左右独立生成，每组接续两个近邻小球，球径依次约 1.92°、1.25°、0.75°。 |
| 6 | VCT NA-YAY | 五颗球各自分段变速、短停、变向，并小幅改变高度。命中后补靶，球径 1.16°。 |

训练时只显示场景、目标、准星及计分。16 方向数据在结束后查看。

Mac 版按输入事件的时间处理位移与点击，结果和本地历史会标注原始输入或兼容输入。使用中的原始输入设备断开时，当轮取消。

参考资料：[Sixshot 官方榜单](https://aimlabs.com/leaderboards?taskId=sixshot&weaponId=9mm) · [Wide Wide Wall 创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=2530722232) · [Aimlabs Phaseshot 指南](https://aimlabs.com/articles/aimlabs-academy/fine-tune-your-precision-in-valorant-to-hit-more-headshots/) · [Aimlabs VCT 任务列表](https://aimlabs.com/articles/aimlabs/the-10-most-popular-aimlabs-tasks-in-november/)

训练场从平台原生输入同时读取原始移动和左键按下。命中按点击当时的准星位置判定。点偏记一次射击，可再次瞄准。第六项的移动小靶仅在命中后刷新。第一项额外按到达目标的轨迹直达率计分，训练时省去轨迹线。

### 普通训练建议

结果旁会列出支持调高或调低的具体方向、有效样本数和方向覆盖范围。方向少于 3 个有效样本时标为样本不足，未覆盖方向也计入这个数。推荐依据只统计用于判断灵敏度的有效样本，因此这个数可能与「16 方向轨迹分析」里按所有射击统计的样本数不同。保留当前值时会说明原因，例如有效样本少于 6 个、多个方向的偏差不够一致，或者调整小于显示精度。

「推荐与导出」里的「推荐说明」会解释三种测算方式、保留当前值的条件和如何应用建议。

完成一轮普通训练后，只用本轮数据给出建议。固定靶优先看首段位移，移动靶看开枪瞬间的瞄准偏差。至少需要 6 个有效样本。过冲或偏短同时达到有效样本和参与方向数的 60%，且获至少两个方向支持时，才建议调低或调高。移动靶有足够跟随样本时，速度差越大，微调越小。建议幅度最多 3%，不足时保留当前值。

推荐值旁的 ↑ 表示调高，↓ 表示调低，百分比按实际导出值计算。点击应用可更新软件里的步枪灵敏度，也能复制 `sensitivity` 指令。

### 一键测试六项

点击「一键测试六项」后，按原顺序以当前步枪灵敏度完成全部项目，每项使用所选时长。每项完成后保存成绩，全部结束后显示各项建议和综合值，并列出建议调高、调低和保持的项目数。至少两项支持同一方向，且占有方向建议的项目至少三分之二时，取这些建议的中位值，综合调整最多 3%。证据不足或方向冲突时保留当前值。按 Esc 可取消，已完成的项目仍保留。

### 六项盲测 A/B/C

以当前值和两档候选进行初筛。每档按固定顺序完成六项，每项 15 秒。同阶段，同项目使用相同种子。初筛结束后，有合格候选时，候选与当前值交换先后顺序，再各测完整六项，复核使用新种子。

按同项目成对比较成绩，取差值中位数，防止单项高分主导推荐。基础分结合单位时间得分和准确率。双方各有至少 6 个有效瞄准样本时，20% 权重用于静态瞄准偏差或移动靶的短时跟随位移误差。每轮至少 4 项可比较，候选至少赢 3 项，准确率下降的中位数不能超过 5 个百分点。初筛中位差至少 1 分，复核至少 2 分，两轮合计中位差至少 3 分，才推荐实测过的候选值。普通训练和一键六项仍使用 3% 微调上限。

揭晓时会显示候选档的可比较项数、领先项数、配对中位分差和准确率变化。保留当前值时会列出未通过的门槛，复核结果也会显示两阶段共同有效项目数和合计中位分差。

评估维度参考 [Aimlabs Sensitivity Finder 官方说明](https://aimlabs.com/articles/aimlabs/aimlabs-mouselabs-explained-smarter-sensitivity-finder-better-results/)，评分和阈值由本项目设定。

### 16 方向点靶分析

点击类训练完成后可打开 16 方向报告。方向由上次射击时的视角与本次所选目标的位置决定；点偏时按最接近准星的可投影目标归因。报告给出启动反应、移动后定位、轨迹直达率及横偏。少于 3 个样本的方向会标记；轨迹分析沿用当前项目的生成规则。历史保留旧版悬停和旧版单靶点击数据，统计口径不同。

### 本地历史

每轮完成后将 DPI、灵敏度、准星及可用的 16 方向统计保存到系统本地应用数据目录的 `practice-history.json`，同时记住当前配置。盲测完成后按训练项目分别保存初筛三档和已完成的复核两档。历史面板可选择任意两轮，按方向对比命中率、反应、定位、过冲、直达率和横偏。点击右上角「清除所有历史」后需确认，确认后仍保留当前配置。

## 工程结构

- `src/core/` 包含 Win32 与 macOS 原生输入、摄像机和数值模型、遥测统计。
- `src/ui/` 包含参数与导出界面、全屏测试场。
- `tests/` 覆盖物理换算、视场角、投影、跨目标判定和统计。
- `scripts/` 和 `build.spec` 提供 Windows 本地构建流程，`.github/workflows/release.yml` 统一发布各平台版本。
- `scripts/build-macos.sh` 和 `.github/workflows/macos.yml` 提供 macOS 构建流程。

## 协议与参考

本项目代码使用 MIT。PySide6 Essentials 使用 Qt for Python 提供的 LGPLv3 条款，PyInstaller 使用带 bootloader 例外的 GPL。第三方许可与源码信息见 [THIRD_PARTY.md](THIRD_PARTY.md)。

- [Microsoft Win32 Raw Input](https://learn.microsoft.com/en-us/windows/win32/inputdev/using-raw-input)
- [Microsoft Per-Monitor DPI Awareness](https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process)
- [Valve Source SDK 视场角实现](https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/client/viewrender.cpp)
