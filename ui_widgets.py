# -*- coding: utf-8 -*-
"""样式层：调色板 / 字体 / 暗色组件库（样式定义与业务代码分离）。

配色与字体遵循设计规范：
- 背景 #18181b / 侧边栏 #202026 / 卡片 #24242c / 边框 #303038
- 主蓝 #3b82f6 / 成功 #22c55e / 失败 #ef4444
- 文字：标题 #f4f4f5、正文 #d4d4d8、次要 #a1a1aa
- 字体：Segoe UI（标题 18、卡片标题 15、正文 14、辅助 12）
"""
import tkinter as tk

# ---------- 配色（样式：轻盈深灰蓝企业风，避免纯黑） ----------
C = {
    "bg": "#2b2d31",         # 主窗口背景
    "side": "#25272b",       # 侧边栏背景
    "card": "#33363c",       # 卡片/面板背景
    "card2": "#3a3d44",      # 卡片内嵌块
    "border": "#3f4248",     # 卡片细边框/分割线
    "text": "#e9eaec",       # 主文字
    "body": "#d8d9dc",       # 正文文字
    "muted": "#b5b7bc",      # 次要文字
    "faint": "#8f9298",      # 辅助文字
    "blue": "#3b82f6",       # 主蓝色（选中高亮）
    "blue_hi": "#4d8ef8",    # 主蓝 hover
    "blue_soft": "#323c4e",  # 选中项轻微高亮背景
    "green": "#22c55e",      # 成功绿
    "green_t": "#4ade80",    # 成功绿（文字提亮）
    "red": "#ef4444",        # 失败红
    "red_t": "#f87171",      # 失败红（文字提亮）
    "purple": "#8957e5",     # 分组标签
    "entry": "#26282c",      # 输入框背景
    "hover": "#3b3e45",      # 通用 hover 背景
}

# ---------- 字体（样式，Windows Segoe UI，整体收紧） ----------
FONT = ("Segoe UI", 13)            # 列表/Treeview 正文（13px）
FONT_B = ("Segoe UI", 13, "bold")  # 强调正文
FONT_S = ("Segoe UI", 11)          # 辅助文字/时间（11px）
FONT_H = ("Segoe UI", 16, "bold")  # 页面大标题（16px）
FONT_CARD = ("Segoe UI", 14)       # 面板标题（14px）
FONT_CARD_B = ("Segoe UI", 14, "bold")
FONT_NUM = ("Segoe UI", 21, "bold")  # 统计卡数字（21px）
FONT_LOGO = ("Segoe UI", 16, "bold")  # 侧边栏标题
FONT_TINY = ("Segoe UI", 10)       # 胶囊标签等


def _lighten(hex_color, delta=22):
    """样式辅助：颜色提亮，用于 hover。"""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return "#%02x%02x%02x" % (
            min(255, r + delta), min(255, g + delta), min(255, b + delta))
    except (ValueError, IndexError):
        return hex_color


def card(parent, **kw):
    """卡片容器（样式）：#24242c 背景 + #303038 细边框模拟圆角容器。"""
    kw.setdefault("bg", C["card"])
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("highlightbackground", C["border"])
    return tk.Frame(parent, **kw)


def hover(widget, base, hi):
    """样式辅助：为控件挂上 hover 提亮效果。"""
    widget.bind("<Enter>", lambda e: widget.config(bg=hi))
    widget.bind("<Leave>", lambda e: widget.config(bg=base))


def button(parent, text, command=None, bg=None, fg="#ffffff", width=None):
    """按钮（样式）：Label 模拟 + hover 提亮。"""
    b = tk.Label(
        parent, text=text, bg=bg or C["blue"], fg=fg,
        font=FONT_S, padx=10, pady=4, cursor="hand2",
    )
    if command:
        b.bind("<Button-1>", lambda e: command())
    if bg:
        hover(b, bg, _lighten(bg))
    else:
        hover(b, C["blue"], C["blue_hi"])
    if width:
        b.config(width=width)
    return b


def pill(parent, text, color):
    """小胶囊标签（样式）。"""
    return tk.Label(
        parent, text=" %s " % text, bg=color, fg="#ffffff",
        font=FONT_TINY, padx=6, pady=1,
    )


def toggle(parent, initial=False, command=None):
    """模拟 iOS 开关（样式组件），返回 (widget, get_state)。"""
    state = {"on": initial}

    def draw():
        cv.delete("all")
        w, h = 34, 18
        r = h // 2
        bg = C["blue"] if state["on"] else "#4a4d54"
        cv.create_oval(0, 0, 2 * r, h, fill=bg, outline=bg)
        cv.create_oval(w - 2 * r, 0, w, h, fill=bg, outline=bg)
        cv.create_rectangle(r, 0, w - r, h, fill=bg, outline=bg)
        cx = w - r if state["on"] else r
        cv.create_oval(cx - 6, 3, cx + 6, h - 3, fill="#ffffff", outline="#ffffff")

    def click(e):
        state["on"] = not state["on"]
        draw()
        if command:
            command(state["on"])

    cv = tk.Canvas(parent, width=34, height=18, bg=C["card"], highlightthickness=0)
    cv.bind("<Button-1>", click)
    draw()
    return cv, (lambda: state["on"])
