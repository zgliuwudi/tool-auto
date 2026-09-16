#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在已经弹出的 WPS 会议「预约会议」表单上自动填写内容并点击保存。

填写内容从同级目录的 meeting_config.json 读取：
    {
      "subject": "周例会",
      "start_time": "2026/10/01 09:30",
      "end_time": "2026/10/01 11:30"
    }

实现方式：
1. 用整张表单截图（form_template.png）在屏幕上做模板匹配，定位表单左上角。
2. 按相对偏移量点击各个输入框/按钮。
3. 通过剪贴板 + Ctrl+V 填入中文和日期时间。
4. 最后点击右上角「保存」。

用法：
    python fill_meeting_form.py              # 填写并保存
    python fill_meeting_form.py --dry-run    # 只定位表单并打印各字段坐标
"""

import argparse
import ctypes
import ctypes.wintypes
import json
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np
from PIL import ImageGrab

# 复用 click_reserve_meeting.py 里的窗口激活/点击/截图/匹配函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import click_reserve_meeting as crm  # noqa: E402

user32 = crm.user32
kernel32 = crm.kernel32

# 参考图尺寸（form_template.png 的实际像素）
FORM_TEMPLATE_W, FORM_TEMPLATE_H = 1080, 607

# 各字段在 form_template.png（表单区域 1080x607）中的相对中心坐标（x, y）
# 按实际界面红框标定，若界面改版需重新截图并调整
FIELD_OFFSETS = {
    "subject": (100, 58),      # 「添加主题」输入框
    "start_date": (49, 101),   # 开始日期 2026/10/01
    "start_time": (159, 101),  # 开始时间 09:30
    "end_date": (251, 101),    # 结束日期 2026/10/01
    "end_time": (361, 101),    # 结束时间 11:30
    "save": (416, 61),         # 右上角「保存」按钮中心
}

# 「保存」按钮锚点模板（save_button.png）在 form_template.png 中的位置：
# 按钮实际区域 (385, 47, 63, 29)，锚点模板从窗口截图裁剪、按钮左上在模板内偏移 (8, 8)
SAVE_BTN_IN_FORM = (385, 47)
SAVE_BTN_IN_TPL = (8, 8)
ANCHOR_TEMPLATE = crm.res_path("save_button.png")

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
VK_CONTROL = 0x11
VK_A = 0x41
VK_ESCAPE = 0x1B
VK_V = 0x56


def set_clipboard_text(text):
    """把文本放到 Windows 剪贴板，供 Ctrl+V 粘贴。"""
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(None):
        return False
    user32.EmptyClipboard()
    data = text.encode("utf-16-le") + b"\x00\x00"
    size = len(data)
    hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
    if not hglobal:
        user32.CloseClipboard()
        return False
    ptr = kernel32.GlobalLock(hglobal)
    if not ptr:
        user32.CloseClipboard()
        return False
    ctypes.memmove(ptr, data, size)
    kernel32.GlobalUnlock(hglobal)
    user32.SetClipboardData(CF_UNICODETEXT, hglobal)
    user32.CloseClipboard()
    return True


def send_key_down(vk):
    user32.keybd_event(vk, 0, 0, 0)


def send_key_up(vk):
    user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP = 2


def send_combo(main_vk):
    """发送 Ctrl+main_vk。"""
    send_key_down(VK_CONTROL)
    time.sleep(0.05)
    send_key_down(main_vk)
    time.sleep(0.05)
    send_key_up(main_vk)
    time.sleep(0.05)
    send_key_up(VK_CONTROL)
    time.sleep(0.05)


def fill_field(x, y, text, dry_run=False):
    """点击 (x,y) 后全选并粘贴 text，最后按 ESC 关掉可能弹出的下拉面板。"""
    print("[填写] 字段坐标 (%.0f, %.0f) -> %s" % (x, y, repr(text)))
    if dry_run:
        return
    crm.click_at(x, y)
    time.sleep(0.25)
    # 第一次点击可能只用于关闭上一个字段的下拉面板，再点一次确保聚焦
    crm.click_at(x, y)
    time.sleep(0.4)
    send_combo(VK_A)
    time.sleep(0.1)
    if not set_clipboard_text(text):
        print("[错误] 剪贴板写入失败")
        sys.exit(5)
    send_combo(VK_V)
    time.sleep(0.3)
    # 关闭日期/时间选择下拉，避免遮挡下一个字段
    send_key_down(VK_ESCAPE)
    time.sleep(0.05)
    send_key_up(VK_ESCAPE)
    time.sleep(0.3)


def locate_form_on_screen(template_path, threshold=0.75):
    """用「保存」按钮锚点模板在 WPS 会议窗口内定位表单。

    整张表单模板匹配在灰底白表单上得分极低（<0.3），不可靠；
    蓝色「保存」按钮颜色独特，窗口内匹配得分接近 1.0。

    返回 (score, form_x, form_y, w, h, scale)，坐标为屏幕坐标、表单左上角。
    """
    anchor = cv2.imread(ANCHOR_TEMPLATE, cv2.IMREAD_COLOR)
    if anchor is None:
        print("[错误] 无法读取锚点模板: %s" % ANCHOR_TEMPLATE)
        sys.exit(2)

    found = crm.find_wps_meeting_window(crm.find_wps_meeting_pids())
    if not found:
        return None
    _, hwnd, _ = found
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))

    screen = np.array(ImageGrab.grab())
    win = cv2.cvtColor(
        screen[rect.top:rect.bottom, rect.left:rect.right], cv2.COLOR_RGB2BGR
    )

    scales = [round(0.6 + 0.1 * i, 1) for i in range(12)]
    result = crm.match_template_multiscale(win, anchor, scales)
    if result is None:
        return None
    score, bx, by, _bw, _bh, scale = result
    if score < threshold:
        return (score, 0, 0, 0, 0, scale)

    # 锚点模板内按钮左上偏移 (8,8)，按钮在表单中的位置 (385,47)
    form_x = rect.left + bx + SAVE_BTN_IN_TPL[0] - SAVE_BTN_IN_FORM[0] * scale
    form_y = rect.top + by + SAVE_BTN_IN_TPL[1] - SAVE_BTN_IN_FORM[1] * scale
    return (
        score,
        int(round(form_x)),
        int(round(form_y)),
        int(FORM_TEMPLATE_W * scale),
        int(FORM_TEMPLATE_H * scale),
        scale,
    )


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    required = ["subject", "start_time", "end_time"]
    for k in required:
        if k not in cfg:
            print("[错误] 配置文件缺少字段: %s" % k)
            sys.exit(2)
    return cfg


def parse_datetime(s):
    try:
        return datetime.strptime(s, "%Y/%m/%d %H:%M")
    except ValueError:
        print("[错误] 时间格式错误，请使用: 2026/10/01 09:30")
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="自动填写 WPS 会议预约表单")
    parser.add_argument("--config", default="meeting_config.json", help="配置文件路径")
    parser.add_argument("--template", default=crm.res_path("form_template.png"), help="表单整体模板图")
    parser.add_argument("--threshold", type=float, default=0.9, help="锚点匹配阈值")
    parser.add_argument("--dry-run", action="store_true", help="只定位表单和字段，不点击")
    args = parser.parse_args()

    if not os.path.exists(args.template):
        print("[错误] 找不到表单模板图: %s" % args.template)
        sys.exit(2)
    if not os.path.exists(args.config):
        print("[错误] 找不到配置文件: %s" % args.config)
        sys.exit(2)

    cfg = load_config(args.config)
    start_dt = parse_datetime(cfg["start_time"])
    end_dt = parse_datetime(cfg["end_time"])

    print("[信息] 主题: %s" % cfg["subject"])
    print("[信息] 开始: %s" % cfg["start_time"])
    print("[信息] 结束: %s" % cfg["end_time"])

    # 激活 WPS 会议窗口，确保在最前
    crm.ensure_wps_meeting()
    time.sleep(0.5)

    # 定位表单
    deadline = time.time() + 15
    result = None
    while time.time() < deadline:
        result = locate_form_on_screen(args.template, threshold=args.threshold)
        if result and result[0] >= args.threshold:
            break
        if result:
            print("[信息] 表单匹配得分 %.3f，继续等待 ..." % result[0])
        else:
            print("[信息] 未找到表单，继续等待 ...")
        time.sleep(1.5)

    if not result or result[0] < args.threshold:
        print("[错误] 无法在屏幕上定位「预约会议」表单，请确认表单已打开。")
        sys.exit(3)

    score, fx, fy, fw, fh, scale = result
    print("[结果] 表单定位成功: 得分=%.3f 缩放=%.2f 位置=(%d,%d) 尺寸=%dx%d"
          % (score, scale, fx, fy, fw, fh))

    def field_pos(offset):
        ox, oy = offset
        return fx + ox * scale, fy + oy * scale

    if args.dry_run:
        print("[信息] --dry-run，仅输出字段坐标：")
        for name, off in FIELD_OFFSETS.items():
            x, y = field_pos(off)
            print("    %s -> (%.0f, %.0f)" % (name, x, y))
        return

    # 填写主题
    sx, sy = field_pos(FIELD_OFFSETS["subject"])
    fill_field(sx, sy, cfg["subject"])

    # 填写开始时间
    sx, sy = field_pos(FIELD_OFFSETS["start_date"])
    fill_field(sx, sy, start_dt.strftime("%Y/%m/%d"))
    sx, sy = field_pos(FIELD_OFFSETS["start_time"])
    fill_field(sx, sy, start_dt.strftime("%H:%M"))

    # 填写结束时间
    sx, sy = field_pos(FIELD_OFFSETS["end_date"])
    fill_field(sx, sy, end_dt.strftime("%Y/%m/%d"))
    sx, sy = field_pos(FIELD_OFFSETS["end_time"])
    fill_field(sx, sy, end_dt.strftime("%H:%M"))

    # 点击保存
    sx, sy = field_pos(FIELD_OFFSETS["save"])
    print("[点击] 保存按钮坐标 (%.0f, %.0f)" % (sx, sy))
    crm.click_at(sx, sy)
    print("[成功] 已点击「保存」。")


if __name__ == "__main__":
    main()
