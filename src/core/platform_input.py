"""Select the native relative-input backend for the current desktop."""
import sys

if sys.platform == "win32":
    from core.raw_input import RawMouseInput, enable_high_dpi
elif sys.platform == "darwin":
    from core.mac_input import RawMouseInput

    def enable_high_dpi() -> None:
        """Qt handles Retina scaling through its Cocoa backend."""
else:
    def enable_high_dpi() -> None:
        raise OSError("此应用需要 Windows 或 macOS。")
