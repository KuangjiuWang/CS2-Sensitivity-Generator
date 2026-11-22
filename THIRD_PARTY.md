# 第三方许可

项目源码依照仓库中的 MIT LICENSE 发布。独立应用包含以下运行时与打包组件。

| 组件 | 版本与发布来源 | 许可证与对应源码 |
| --- | --- | --- |
| PySide6 Essentials、Shiboken6 与随轮包提供的 Qt | [PySide6 Essentials 6.12.0](https://pypi.org/project/PySide6-Essentials/6.12.0/)、[Shiboken6 6.12.0](https://pypi.org/project/shiboken6/6.12.0/) | [Qt for Python 许可说明](https://doc.qt.io/qtforpython-6/licenses.html)、[LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html)、[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html)、[Qt for Python 源码](https://code.qt.io/cgit/pyside/pyside-setup.git/)、[Qt 源码发行目录](https://download.qt.io/official_releases/qt/6.12/) |
| Python | [Python 3.12 源码发行目录](https://www.python.org/ftp/python/) | [Python Software Foundation 许可证](https://docs.python.org/3.12/license.html) |
| PyInstaller bootloader | [PyInstaller 6.22.3 源码](https://pypi.org/project/pyinstaller/6.22.3/) | [GPL 与 bootloader 分发例外](https://pyinstaller.org/en/stable/license.html) |
| PyObjC（macOS） | [GameController 绑定及依赖](https://pypi.org/project/pyobjc-framework-GameController/) | [PyObjC 源码与许可](https://github.com/ronaldoussoren/pyobjc) |

接收者可替换 Qt/PySide6 运行库，使用项目源码和对应平台的构建脚本重新构建。也可直接使用替换后的运行库启动项目源码。
