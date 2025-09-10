#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mouse-follows-focus for Windows.

Behavior:
- Detects when the foreground (active) window changes.
- After a short stabilizing delay, checks whether the mouse is already inside
  the new window's rectangle.
- If not, moves the cursor to the center of the new active window.

Notes:
- Pure ctypes; no external packages.
- DPI-aware so coordinates align with modern displays.
- Skips minimized/hidden windows.
- Ctrl+C to exit.
"""

import time
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shcore = None

# ----- DPI awareness (best-effort) -----
# Try Per-Monitor V2; fall back to system aware if unavailable.
# This prevents coordinate mismatches on HiDPI displays.
try:
    # Windows 10+: SetProcessDpiAwarenessContext(-4) = PER_MONITOR_AWARE_V2
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    if not user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
        raise OSError
except Exception:
    try:
        # Windows 8.1 API: SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE=2)
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.restype = ctypes.c_int  # HRESULT
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness(2)
    except Exception:
        # Vista+: SetProcessDPIAware() as weakest fallback
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

# ----- Win32 structures -----
class RECT(ctypes.Structure):
    _fields_ = [('left',   wintypes.LONG),
                ('top',    wintypes.LONG),
                ('right',  wintypes.LONG),
                ('bottom', wintypes.LONG)]

class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG),
                ('y', wintypes.LONG)]

# ----- Win32 function prototypes -----
user32.GetForegroundWindow.restype = wintypes.HWND

user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]

user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]

user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]

user32.GetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]

user32.SetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]

user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

# Optional: filter out tool windows (owned popups) if desired.
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
try:
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _has_getwindowlong = True
except Exception:
    _has_getwindowlong = False

def hwnd_is_candidate(hwnd: int) -> bool:
    if not hwnd:
        return False
    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.IsIconic(hwnd):
        return False
    if _has_getwindowlong:
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & WS_EX_TOOLWINDOW:
            return False
    r = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return False
    # Discard zero-area or negative rectangles
    width = r.right - r.left
    height = r.bottom - r.top
    if width <= 0 or height <= 0:
        return False
    return True

def get_window_rect(hwnd: int):
    r = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return (r.left, r.top, r.right, r.bottom)

def get_cursor_pos():
    p = POINT()
    if not user32.GetCursorPos(ctypes.byref(p)):
        return None
    return (p.x, p.y)

def point_in_rect(x, y, rect):
    left, top, right, bottom = rect
    return (left <= x <= right) and (top <= y <= bottom)

def rect_center(rect):
    left, top, right, bottom = rect
    cx = left + (right - left) // 2
    cy = top + (bottom - top) // 2
    return (cx, cy)

def move_cursor(x, y):
    user32.SetCursorPos(int(x), int(y))

def main():
    last_hwnd = None
    # Polling interval for foreground changes
    poll_interval = 0.03  # 30 ms
    # Stabilizing delay after change (mirrors the original 150 ms)
    settle_delay = 0.150

    try:
        while True:
            hwnd = user32.GetForegroundWindow()

            if hwnd and hwnd != last_hwnd:
                last_hwnd = hwnd

                if hwnd_is_candidate(hwnd):
                    time.sleep(settle_delay)  # let window finish animating/resizing

                    rect = get_window_rect(hwnd)
                    cur = get_cursor_pos()
                    if rect and cur:
                        x, y = cur
                        if not point_in_rect(x, y, rect):
                            cx, cy = rect_center(rect)
                            # Re-check geometry in case it changed during settle delay
                            rect2 = get_window_rect(hwnd) or rect
                            cx, cy = rect_center(rect2)
                            move_cursor(cx, cy)

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
