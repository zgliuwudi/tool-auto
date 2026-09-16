#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在「WPS 会议」窗口上定位「预约会议」按钮（图标+文字），并模拟鼠标左键单击。

流程：
  1. 设为 DPI 感知，保证截图像素坐标与鼠标坐标一致。
  2. 若 WPS 会议未运行则先启动，并把它激活到最上层。
  3. 全屏截图，用提供的模板图做多尺度模板匹配，找到「预约会议」按钮。
  4. 把鼠标移动到按钮中心并单击（默认真实点击，可用 --dry-run 只定位不点击）。

用法：
  python click_reserve_meeting.py              # 定位并单击
  python click_reserve_meeting.py --dry-run    # 只定位，输出坐标与得分，保存调试图
  python click_reserve_meeting.py --threshold 0.6
"""

import argparse
import ctypes
import os
import sys
import time

# ---- 关键：设为 DPI 感知，必须在导入/使用 GUI 之前执行 ----
def set_dpi_awareness():
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


set_dpi_awareness()

import numpy as np  # noqa: E402
import cv2  # noqa: E402
from PIL import ImageGrab  # noqa: E402

try:
    import pyautogui  # noqa: E402
except ImportError:  # 未安装 pyautogui 时用 ctypes 兜底
    pyautogui = None

# 找不到按钮时的最长轮询时间（秒）
POLL_TIMEOUT = 25

# 默认模板图：用户提供的「预约会议」按钮截图
DEFAULT_TEMPLATE = "meeting_button.png"  # 相对工作目录（exe/项目根目录）

def res_path(name):
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)

DEFAULT_TEMPLATE = res_path("meeting_button.png")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

# WPS 会议的真实进程名（窗口标题再像也不算，必须进程名一致）
WPS_EXE_NAMES = ("wpsmeeting.exe", "kmeeting.exe")
# 明确排除的窗口类名（cmd / PowerShell / Windows Terminal）
CONSOLE_CLASSES = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow")


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_map():
    """返回 {pid: 进程文件名}，用 CreateToolhelp32Snapshot 枚举。"""
    result = {}
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE or snap == 0:
        return result
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            result[entry.th32ProcessID] = entry.szExeFile
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return result


def find_wps_meeting_pids(procs=None):
    """在系统进程里找 WPS 会议 / kmeeting 的 pid 列表。"""
    procs = procs if procs is not None else process_map()
    return sorted(pid for pid, name in procs.items() if name.lower() in WPS_EXE_NAMES)


def window_pid(hwnd):
    pid = ctypes.c_uint32()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def list_visible_windows():
    """返回 [(hwnd, title), ...]，仅包含可见、有标题、非控制台的窗口。"""
    windows = []

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if window_class(hwnd) in CONSOLE_CLASSES:
            return True
        # 命令行窗口的标题通常是 "... - python xxx.py"，一律跳过
        if window_pid(hwnd) == os.getpid():
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        t = title.lower()
        if not title or ".py" in t or "cmd.exe" in t or "powershell" in t:
            return True
        windows.append((hwnd, title))
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return windows


def find_wps_meeting_window(wps_pids=None):
    """挑出 WPS 会议主窗口：以进程名判定优先，标题仅作为兜底。"""
    pids = set(wps_pids if wps_pids is not None else find_wps_meeting_pids())
    best = None  # (priority, hwnd, title)
    for hwnd, title in list_visible_windows():
        priority = 0
        if window_pid(hwnd) in pids:
            priority = 100  # 进程名就是 WPS 会议，最可靠
        else:
            t = title.lower()
            # 兜底标题匹配：必须同时具备品牌词与会议词，避免误伤含 "meeting" 的其它窗口
            if ("wps" in t or "金山" in title) and ("会议" in title or "meeting" in t):
                priority = 10
            if "腾讯" in title:  # 排除腾讯会议
                priority -= 50
        if priority > 0 and (best is None or priority > best[0]):
            best = (priority, hwnd, title)
    return best


def activate_window(hwnd):
    """把窗口还原并置前。"""
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        # 某些情况下 SetForegroundWindow 会被拒绝，用 AttachThreadInput 兜底
        try:
            fg = user32.GetForegroundWindow()
            tid_fg = user32.GetWindowThreadProcessId(fg, None)
            tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
            user32.AttachThreadInput(tid_me, tid_fg, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(tid_me, tid_fg, False)
        except Exception:
            pass


def _launch_via_launcher():
    """调用 open_wps_meeting.py 启动 WPS 会议。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import open_wps_meeting as launcher
        target = launcher.resolve_target()
        if not target:
            print("[错误] 找不到 WPS 会议程序，请先手动安装/打开。")
            sys.exit(2)
        print("[信息] 启动目标: %s" % target)
        launcher.launch(target)
        return True
    except SystemExit:
        raise
    except Exception as e:
        print("[错误] 启动 WPS 会议失败: %s" % e)
        sys.exit(2)


SW_RESTORE, SW_SHOW = 9, 5


def find_hidden_wps_window(pids):
    """在 WPS 进程的全部窗口（含不可见）中找主窗口并恢复显示。"""
    pids = set(pids)
    found = []

    def _cb(hwnd, _lparam):
        if window_pid(hwnd) in pids and window_class(hwnd) == "Chrome_WidgetWin_1":
            if user32.GetWindowTextLengthW(hwnd) > 0:
                found.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return found


def ensure_wps_meeting():
    """确保 WPS 会议已运行并处于前台，返回 (hwnd, title)。

    判定依据是进程名（wpsmeeting.exe / kmeeting.exe），而不是窗口标题，
    避免把 cmd/PowerShell 这类标题里恰好含 "meeting" 的窗口当成目标。
    """
    pids = find_wps_meeting_pids()
    if pids:
        print("[信息] WPS 会议进程已在运行，pid=%s" % pids)
    else:
        print("[信息] 未发现 WPS 会议进程，尝试启动 ...")
        _launch_via_launcher()
        # 等进程起来
        for _ in range(30):
            time.sleep(1)
            pids = find_wps_meeting_pids()
            if pids:
                print("[信息] 进程已启动，pid=%s" % pids)
                break
        if not pids:
            print("[错误] 进程未起来，请检查 WPS 会议是否能正常手动打开。")
            sys.exit(2)

    # 等主窗口出现（进程在托盘时可能暂时没有可见窗口）
    found = None
    for _ in range(20):
        found = find_wps_meeting_window(pids)
        if found:
            break
        time.sleep(1)

    if not found:
        # 进程活着但窗口不可见（最小化到托盘）：先直接恢复主窗口
        print("[信息] 进程在运行却没有可见窗口，尝试恢复主窗口 ...")
        for hwnd in find_hidden_wps_window(find_wps_meeting_pids()):
            if not user32.IsWindowVisible(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.3)
                user32.ShowWindow(hwnd, SW_SHOW)
                print("[信息] 已恢复窗口 hwnd=%s" % hwnd)
        time.sleep(1.0)
        for _ in range(10):
            found = find_wps_meeting_window(find_wps_meeting_pids())
            if found:
                break
            time.sleep(1)
        if not found:
            print("[信息] 恢复无效，再次唤起界面 ...")
            _launch_via_launcher()
            for _ in range(20):
                time.sleep(1)
                found = find_wps_meeting_window(find_wps_meeting_pids())
                if found:
                    break

    if not found:
        print("[错误] 仍未发现 WPS 会议窗口，请确认托盘里有 WPS 会议图标。")
        sys.exit(2)

    _, hwnd, title = found
    print("[信息] 找到窗口: 《%s》 (hwnd=%s, pid=%s)" % (title, hwnd, window_pid(hwnd)))
    activate_window(hwnd)
    time.sleep(0.8)  # 等待窗口置前完成
    return title


def grab_screen():
    """抓取主屏截图，返回 RGB 的 numpy 数组。"""
    img = ImageGrab.grab()  # 主屏
    return np.array(img)  # RGB


def match_template_multiscale(screen_bgr, tmpl_bgr, scales):
    """多尺度模板匹配，返回 (score, x, y, w, h, scale) 或 None。"""
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    tmpl_gray = cv2.cvtColor(tmpl_bgr, cv2.COLOR_BGR2GRAY)
    sh, sw = screen_gray.shape[:2]

    best = None
    for s in scales:
        if s == 1.0:
            t = tmpl_gray
        else:
            interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_CUBIC
            t = cv2.resize(tmpl_gray, None, fx=s, fy=s, interpolation=interp)
        th, tw = t.shape[:2]
        if th >= sh or tw >= sw:
            continue
        res = cv2.matchTemplate(screen_gray, t, cv2.TM_CCOEFF_NORMED)
        _minv, maxv, _minl, maxl = cv2.minMaxLoc(res)
        if best is None or maxv > best[0]:
            best = (maxv, maxl[0], maxl[1], tw, th, s)
    return best


def _click_via_win32(x, y):
    """不依赖 pyautogui 时，直接用 Win32 API 移动鼠标并左键单击。"""
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_ABSOLUTE = 0x8000

    x, y = int(x), int(y)
    user32.SetCursorPos(x, y)
    # 补一个绝对移动事件，部分自绘界面需要真实的鼠标移动消息
    ax = int(x * 65535 / max(user32.GetSystemMetrics(0) - 1, 1))
    ay = int(y * 65535 / max(user32.GetSystemMetrics(1) - 1, 1))
    user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, ax, ay, 0, 0)
    time.sleep(0.15)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def click_at(x, y):
    """把鼠标移到 (x, y) 并左键单击。"""
    if pyautogui is not None:
        pyautogui.moveTo(int(x), int(y), duration=0.25)
        time.sleep(0.1)
        pyautogui.click()
    else:
        _click_via_win32(x, y)


def main():
    parser = argparse.ArgumentParser(description="定位并点击 WPS 会议的「预约会议」按钮")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="模板图片路径")
    parser.add_argument("--threshold", type=float, default=0.70, help="匹配阈值(0-1)，默认 0.70")
    parser.add_argument("--dry-run", action="store_true", help="只定位，不点击")
    parser.add_argument("--debug", action="store_true", help="保存带标记框的调试图")
    args = parser.parse_args()

    if not os.path.exists(args.template):
        print("[错误] 模板图片不存在: %s" % args.template)
        sys.exit(2)

    tmpl = cv2.imread(args.template, cv2.IMREAD_COLOR)
    if tmpl is None:
        print("[错误] 无法读取模板图片。")
        sys.exit(2)
    print("[信息] 模板尺寸: %dx%d" % (tmpl.shape[1], tmpl.shape[0]))

    ensure_wps_meeting()

    # 多尺度：0.5 ~ 1.6
    scales = [round(0.5 + 0.1 * i, 1) for i in range(12)]

    # 轮询：窗口刚启动时界面可能还没渲染完，重截直到匹配到满意结果
    deadline = time.time() + POLL_TIMEOUT
    attempt = 0
    best_screen = None
    result = None
    while True:
        attempt += 1
        found = find_wps_meeting_window()
        if found:
            activate_window(found[1])  # 每次重试都确保窗口在最前
            time.sleep(0.4)
        screen = grab_screen()
        screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
        if attempt == 1:
            print("[信息] 屏幕尺寸: %dx%d" % (screen.shape[1], screen.shape[0]))

        result = match_template_multiscale(screen_bgr, tmpl, scales)
        if result is not None:
            best_screen = screen_bgr
            if result[0] >= args.threshold:
                break
        print("[信息] 第 %d 次定位：%s" % (
            attempt,
            "得分=%.3f" % result[0] if result else "未匹配",
        ))
        if time.time() >= deadline:
            break
        time.sleep(1.5)

    if result is None:
        print("[错误] 模板匹配失败：屏幕上找不到「预约会议」按钮区域。")
        sys.exit(3)

    score, x, y, w, h, scale = result
    cx, cy = x + w / 2.0, y + h / 2.0
    print("[结果] 匹配得分=%.3f  缩放=%.1f  位置=(%d,%d) 尺寸=%dx%d  中心=(%.0f,%.0f)"
          % (score, scale, x, y, w, h, cx, cy))

    if args.debug and best_screen is not None:
        dbg = best_screen.copy()
        cv2.rectangle(dbg, (x, y), (x + w, y + h), (0, 0, 255), 3)
        cv2.circle(dbg, (int(cx), int(cy)), 8, (0, 255, 0), -1)
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_match.png")
        cv2.imwrite(out, dbg)
        print("[信息] 调试图已保存: %s" % out)

    if score < args.threshold:
        print("[警告] 得分 %.3f 低于阈值 %.2f，未点击。" % (score, args.threshold))
        sys.exit(4)

    if args.dry_run:
        print("[信息] --dry-run：仅定位，不点击。")
        return

    click_at(cx, cy)
    print("[成功] 已在 (%.0f,%.0f) 模拟左键单击「预约会议」。" % (cx, cy))
    print("[提示] WPS 会议基于 Chrome 内核，预约表单多以页面内弹层呈现，不一定会生成新窗口。")
    print("       请目视主窗口确认「添加主题/时间/会议室」表单是否出现；")
    print("       如需继续自动填表，可对目标输入框截图，按同样的模板匹配方式继续串接。")


if __name__ == "__main__":
    main()
