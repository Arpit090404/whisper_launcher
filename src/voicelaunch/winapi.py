import ctypes


def harden_overlay(hwnd: int) -> None:
    if not hasattr(ctypes, "windll"): return
    u=ctypes.windll.user32; u.GetWindowLongPtrW.restype=ctypes.c_ssize_t; style=u.GetWindowLongPtrW(hwnd,-20); u.SetWindowLongPtrW(hwnd,-20,style|0x80|0x08000000|0x20|0x80000)
