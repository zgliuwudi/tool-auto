#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会议预约保存成功后的收尾动作：
1. 在会议列表里找到刚创建的会议卡片，点击右侧「分享」图标；
2. 在弹出的「邀请其他人加入」对话框中点击「复制会议信息」；
3. 校验剪贴板中已包含会议链接。

实现方式：截取 WPS 会议窗口，通过蓝色「入会」按钮定位卡片，
分享图标位于入会按钮上方固定偏移处；「复制会议信息」按钮
按颜色（独特蓝色矩形）检测后点击。

用法：
    python copy_meeting_info.py            # 分享并复制
    python copy_meeting_info.py --dry-run  # 只定位打印坐标，不点击
"""

import argparse
import ctypes
import ctypes.wintypes
import os
import sys
import time

import cv2
import numpy as np
from PIL import ImageGrab

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import click_reserve_meeting as crm  # noqa: E402

user32 = crm.user32
kernel32 = crm.kernel32

CF_UNICODETEXT = 13

# 「入会」按钮 → 「分享」图标的偏移（窗口像素，1080p 实测）
SHARE_OFFSET = (11, -79)
# 「复制会议信息」按钮的最小尺寸（宽, 高），用于区分其它蓝色元素
COPY_BTN_MIN_W, COPY_BTN_MIN_H = 60, 24


def grab_window_bgr():
    """截取 WPS 会议窗口，返回 (BGR 图, win_left, win_top)。"""
    found = crm.find_wps_meeting_window(crm.find_wps_meeting_pids())
    if not found:
        print("[错误] 未找到 WPS 会议窗口")
        sys.exit(2)
    _, _hwnd, _title = found
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(_hwnd, ctypes.byref(rect))
    img = np.array(ImageGrab.grab())
    win = cv2.cvtColor(img[rect.top:rect.bottom, rect.left:rect.right],
                       cv2.COLOR_RGB2BGR)
    return win, rect.left, rect.top


def find_blue_regions(win, min_area=200):
    """找窗口内的蓝色区块，返回 [(cx, cy, w, h), ...] 按 y 再 x 排序。"""
    b, g, r = [x.astype(int) for x in cv2.split(win)]
    mask = ((b > 150) & (b - r > 60) & (b - g > 40)).astype("uint8") * 255
    n, _lab, st, _cen = cv2.connectedComponentsWithStats(mask, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a >= min_area:
            out.append((int(x + w / 2), int(y + h / 2), int(w), int(h)))
    out.sort(key=lambda v: (v[1], v[0]))
    return out


def get_clipboard_text():
    """读取剪贴板文本，失败返回空字符串。"""
    # 64 位下必须显式声明句柄类型，否则默认按 32 位 int 截断
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not user32.OpenClipboard(None):
        return ""
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def main():
    parser = argparse.ArgumentParser(description="分享会议并复制会议信息")
    parser.add_argument("--dry-run", action="store_true", help="只定位不点击")
    args = parser.parse_args()

    crm.ensure_wps_meeting()
    time.sleep(0.5)

    # ---- 第 1 步：定位会议卡片右侧「分享」图标 ----
    win, wx, wy = grab_window_bgr()
    blues = find_blue_regions(win)
    join_btn = None
    for cx, cy, w, h in blues:
        # 「入会」按钮：小蓝色矩形
        if 40 <= w <= 120 and 18 <= h <= 45 and cy < win.shape[0] * 0.5:
            join_btn = (cx, cy, w, h)
    if join_btn is None:
        print("[错误] 未找到「入会」按钮（会议列表可能为空）")
        sys.exit(3)
    jx, jy, _w, _h = join_btn
    sx, sy = jx + SHARE_OFFSET[0], jy + SHARE_OFFSET[1]
    print("[定位] 入会按钮 (%d,%d) -> 分享图标 (%d,%d)" % (jx, jy, sx, sy))

    if args.dry_run:
        print("[dry-run] 分享图标屏幕坐标: (%d, %d)" % (wx + sx, wy + sy))
        return

    crm.click_at(wx + sx, wy + sy)
    print("[成功] 已点击「分享」图标。")
    time.sleep(1.0)

    # ---- 第 2 步：在弹窗中点击「复制会议信息」 ----
    copy_btn = None
    for _ in range(10):
        win, wx, wy = grab_window_bgr()
        for cx, cy, w, h in find_blue_regions(win):
            if w >= COPY_BTN_MIN_W and h >= COPY_BTN_MIN_H:
                copy_btn = (cx, cy, w, h)
                break
        if copy_btn:
            break
        time.sleep(0.8)

    if copy_btn is None:
        print("[错误] 未找到「复制会议信息」按钮，请确认邀请弹窗已打开")
        sys.exit(4)

    cx, cy, _w, _h = copy_btn
    print("[定位] 复制会议信息按钮 (%d,%d)" % (cx, cy))
    crm.click_at(wx + cx, wy + cy)
    print("[成功] 已点击「复制会议信息」。")
    time.sleep(0.8)

    # ---- 第 3 步：校验剪贴板 ----
    text = get_clipboard_text()
    if text and ("meeting" in text or "WPS" in text or "会议" in text):
        print("[成功] 会议信息已复制到剪贴板（%d 字符）" % len(text))
    else:
        print("[警告] 剪贴板校验未通过，请手动确认是否复制成功")


if __name__ == "__main__":
    main()
