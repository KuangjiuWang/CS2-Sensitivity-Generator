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
3. 复制指令到 CS2 开发者控制台，或把 CFG 片段合并到现有 `autoexec.cfg`。也可保存新文件到 Steam 游戏目录下的 `game/csgo/cfg/`。
4. 开镜倍率单独填写，初始值为 `1.000`。训练只测无开镜状态。

### 检测鼠标 DPI

点 DPI 输入框旁的「检测 DPI」。在鼠标垫旁用尺子标出 10 cm 或其他已知距离，并在弹窗填写同一数值。把鼠标放在起点，按空格开始，保持朝向沿水平方向滑到终点。停稳后再按空格，点「填入 DPI」应用测得的值。仍可直接手填 DPI。

测量以相对移动的横向净计数乘以 2.54，再除以实际滑动的厘米数。该结果是当前设置和表面下的实测估值。滑动距离、偏离直线和鼠标转动都会影响误差。测量期间只移动待测鼠标，尽量使用较长的标定距离。[Microsoft RAWMOUSE 说明](https://learn.microsoft.com/windows/win32/api/winuser/ns-winuser-rawmouse)

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

- **悬停拉枪**用相邻原始输入之间的投影线段判定首次穿过目标。定位耗时从生成目标算起，过冲记录命中后 180 ms 内沿首段瞄准方向越过目标远侧边界的最大角距。结果取完整观测的平均值。
- **动态跟枪**用单个持续存在的目标练习横移和反向瞄准。目标高度与前向深度固定，交替出现长横移与短反向。加速、减速和短停是本项目的训练设置。Aimlabs 公开资料说明了 Strafe Track CS2 的目标行为及创作工具的加减速、最高速度和转向设置，未列出该任务的具体数值。[Aimlabs 的 CS2 训练说明](https://aimlabs.com/articles/aimlabs/train-micros-and-flicking-in-counter-strike-2-with-the-aim-basics-routine/) · [Aimlabs 创作工具说明](https://aimlabs.com/articles/aimlabs/we-have-updated-the-aimlabs-creators-studio/)
- 目标的线速度上限取自 CS2 的 `m_flMaxSpeed`。AK-47 为 215 u/s，M4A4 和 M4A1-S 为 225 u/s，AWP 未开镜为 200 u/s、开镜为 100 u/s，持刀为 250 u/s。这里的开镜指**跟枪目标持 AWP 时的移动状态**。项目仍用你的无开镜视角测算灵敏度。[CS2 游戏文件镜像](https://github.com/SteamTracking/GameTracking-CS2/blob/master/game/csgo/pak01_dir/scripts/weapons.vdata)
- 目标以横向位移 `x` 和前向深度 `d` 投影，视角为 `atan(x/d)`。全速穿过正前方时的角速度为 `v/d` 弧度每秒。默认 AK-47、600 u 对应约 20.5°/秒，同一移速下 400 u 对应约 30.8°/秒。可调距离为 300–1600 u，圆靶角直径为 0.5°–5.0°，默认 1.6°。圆靶直径同时设置画面大小和命中范围。
- 命中时长采用单调时钟积分。只在每次起步至少 200 ms 后的匀速段统计滞后与超前。准星沿运动方向落后或领先约 1° 时分别记为滞后或超前，该阈值独立于圆靶大小。
- 两项完成后，过冲每度将输入灵敏度下调 4 个百分点，最多下调 8 个百分点。跟枪按 `0.10 × (滞后率 − 超前率)` 修正，合计修正限制在 ±12%。过冲需要至少 3 个完整观测。跟枪需要至少 2.5 秒且四分之一场次的方向有效，命中时长还需达到 10%。样本不足的单项不参与修正。该规则提供一次有界的起始建议，可结合练习结果复测。
- 倒计时和评分从 `perf_counter` 的单调时间差计算，Qt 精确定时器驱动刷新。UI 卡顿时，剩余时间按实际流逝校正。

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
