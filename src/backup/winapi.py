import ctypes


def harden_overlay(hwnd: int) -> None:
    if not hasattr(ctypes, "windll"): return
    u=ctypes.windll.user32; u.GetWindowLongPtrW.restype=ctypes.c_ssize_t; style=u.GetWindowLongPtrW(hwnd,-20); u.SetWindowLongPtrW(hwnd,-20,style|0x80|0x08000000|0x20|0x80000)


def enable_acrylic(hwnd: int, color: int = 0xD929292B) -> None:
    """Request tinted acrylic blur, with DWM acrylic as a fallback."""
    if not hasattr(ctypes, "windll"):
        return
    try:
        class AccentPolicy(ctypes.Structure):
            _fields_ = [("state", ctypes.c_int), ("flags", ctypes.c_int),
                       ("gradient_color", ctypes.c_uint), ("animation_id", ctypes.c_int)]

        class WindowCompositionAttributeData(ctypes.Structure):
            _fields_ = [("attribute", ctypes.c_int), ("data", ctypes.c_void_p), ("size", ctypes.c_size_t)]

        policy = AccentPolicy(4, 0, color, 0)  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        data = WindowCompositionAttributeData(19, ctypes.addressof(policy), ctypes.sizeof(policy))
        accent = ctypes.windll.user32.SetWindowCompositionAttribute
        accent.argtypes = (ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData))
        accent.restype = ctypes.c_int
        if accent(hwnd, ctypes.byref(data)):
            return
    except (AttributeError, OSError):
        pass
    try:
        # Windows 11 22H2+: transient backdrop is Desktop Acrylic.
        backdrop = ctypes.c_int(3)  # DWMSBT_TRANSIENTWINDOW
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        dwm.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint)
        dwm.restype = ctypes.c_long
        dark_mode = ctypes.c_int(1)
        dwm(hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))
        if dwm(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop)) == 0:
            corners = ctypes.c_int(2)  # DWMWCP_ROUND
            dwm(hwnd, 33, ctypes.byref(corners), ctypes.sizeof(corners))
    except (AttributeError, OSError):
        pass
