# CS2 Sensitivity Generator

Windows 桌面灵敏度计算器。输入当前 CS2 灵敏度，再通过全屏训练和同项盲测得出建议。也可以用 DPI、鼠标垫行程与发力习惯计算起点。导出三位小数的灵敏度、eDPI、cm/360°，可复制控制台指令、复制 CFG 或保存为 `autoexec.cfg`。

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
2. 选择与 CS2 一致的画面比例和训练项目。进入深色全屏训练场后，移动鼠标开始 3 秒倒计时。单项练习可选 15、30 或 60 秒。六项均使用左键判定。第一项清空一组固定球后自动刷新下一组。Esc 退出，失焦取消当轮。
3. 在「推荐与导出」分别复制灵敏度 CFG、准星 CFG，或复制两者的完整配置。可以将片段合并到现有 `autoexec.cfg`，也可以保存新文件到 Steam 游戏目录的 `game/csgo/cfg/`。
4. 推荐与灵敏度导出只使用 CS2 的 `sensitivity`。盲测结论会显示当前值和推荐值，应用后更新软件输入框，在 CS2 中使用导出的命令生效。

### 检测鼠标 DPI

点 DPI 输入框旁的「检测 DPI」。在鼠标垫旁用尺子标出 10 cm 或其他已知距离，并在弹窗填写同一数值。把鼠标放在起点，按空格开始，保持朝向沿水平方向滑到终点。停稳后再按空格，点「填入 DPI」应用测得的值。仍可直接手填 DPI。

测量以相对移动的横向净计数乘以 2.54，再除以实际滑动的厘米数。该结果是当前设置和表面下的实测估值。滑动距离、偏离直线和鼠标转动都会影响误差。测量期间只移动待测鼠标，尽量使用较长的标定距离。[Microsoft RAWMOUSE 说明](https://learn.microsoft.com/windows/win32/api/winuser/ns-winuser-rawmouse)

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

测试窗口通过 Win32 窗口过程接收 `WM_INPUT`，从前台鼠标读取相对计数。屏幕光标位置不参与计算。程序启动时启用 Per-Monitor DPI Awareness V2，全屏画布选择主界面所在显示器，隐藏光标并将它临时限制在画布范围，结束或失焦时释放限制。测试期间请只移动使用所填 DPI 的鼠标。若进入全屏后 12 秒仍未收到相对移动，程序会退出当轮并显示提示。

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

参考资料：[Sixshot 官方榜单](https://aimlabs.com/leaderboards?taskId=sixshot&weaponId=9mm) · [Wide Wide Wall 创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=2530722232) · [Aimlabs Phaseshot 指南](https://aimlabs.com/articles/aimlabs-academy/fine-tune-your-precision-in-valorant-to-hit-more-headshots/) · [Aimlabs VCT 任务列表](https://aimlabs.com/articles/aimlabs/the-10-most-popular-aimlabs-tasks-in-november/)

Win32 Raw Input 同时读取原始移动和左键按下。命中按点击当时的准星位置判定。点偏记一次射击，可再次瞄准；第六项的移动小靶仅在命中后刷新。第一项额外按到达目标的轨迹直达率计分，训练时省去轨迹线。

### 普通训练建议

「推荐与导出」里的「推荐说明」会解释三种测算方式、保留当前值的条件和如何应用建议。

完成一轮普通训练后，只用本轮数据给出建议。固定靶优先看首段位移，移动靶看开枪瞬间的瞄准偏差。至少需要 6 个有效样本。过冲或偏短达到有效样本的 60%，并覆盖至少两个方向时，才建议调低或调高。建议幅度最多 3%，不足时保留当前值。

推荐值旁的 ↑ 表示调高，↓ 表示调低，百分比按实际导出值计算。点击应用可更新软件里的步枪灵敏度，也能复制 `sensitivity` 指令。

### 一键测试六项

点击「一键测试六项」后，按原顺序以当前步枪灵敏度完成全部项目，每项使用所选时长。每项完成后保存成绩，全部结束后显示各项建议和综合值。至少两项支持同一方向，且占有方向建议的项目至少三分之二时，取这些建议的中位值，综合调整最多 3%。证据不足或方向冲突时保留当前值。按 Esc 可取消，已完成的项目仍保留。

### 同项盲测 A/B/C

从选中的训练项目开始。每档 15 秒，默认以当前灵敏度 ±5% 作三档初筛。同轮各档共用随机种子；点靶项目各个靶位共享对应的随机序列，命中时间会影响换靶时刻。有领先候选时反转它与当前值的出场顺序，用新的种子复核。

盲测综合分结合单位时间得分和射击准确率。每档至少点中 6 靶。候选准确率最多下降 5 个百分点。初筛领先至少 1 分、复核领先至少 2 分、两轮平均领先至少 3 分时才建议试用。

### 16 方向点靶分析

点击类训练完成后可打开 16 方向报告。方向由上次射击时的视角与本次所选目标的位置决定；点偏时按最接近准星的可投影目标归因。报告给出启动反应、移动后定位、轨迹直达率及横偏。少于 3 个样本的方向会标记；轨迹分析沿用当前项目的生成规则。历史保留旧版悬停和旧版单靶点击数据，统计口径不同。

### 本地历史

每轮完成后将 DPI、灵敏度、准星及可用的 16 方向统计保存到 Windows 本地应用数据目录的 `practice-history.json`，同时记住当前配置。盲测完成后按训练项目分别保存初筛三档和已完成的复核两档。历史面板可选择任意两轮，按方向对比命中率、反应、定位、过冲、直达率和横偏。点击右上角「清除所有历史」后需确认，确认后仍保留当前配置。

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
