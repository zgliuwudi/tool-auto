# -*- coding: utf-8 -*-
"""暗色主题组件库：调色板、卡片、模拟开关、状态标签等。"""
import tkinter as tk

C = {
    "bg": "#0d1117",         # 窗口背景
    "side": "#10151d",       # 侧边栏
    "card": "#161b22",       # 卡片
    "card2": "#1c2128",      # 卡片内嵌块
    "border": "#2a313b",     # 边框
    "text": "#e6edf3",       # 主文字
    "muted": "#8b949e",      # 次要文字
    "blue": "#316dca",       # 主色按钮
    "blue_hi": "#3f82e0",
    "green": "#2ea043",
    "green_t": "#3fb950",
    "red": "#c93c37",
    "red_t": "#f85149",
    "purple": "#8957e5",
    "yellow": "#d29922",
    "entry": "#0d1117",
}

FONT = ("Microsoft YaHei UI", 10)
FONT_B = ("Microsoft YaHei UI", 10, "bold")
FONT_S = ("Microsoft YaHei UI", 9)
FONT_H = ("Microsoft YaHei UI", 13, "bold")
FONT_NUM = ("Consolas", 22, "bold")


def card(parent, **kw):
    """设计稿里的深色圆角感卡片（Tk 用高亮边框模拟）。"""
    kw.setdefault("bg", C["card"])
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("highlightbackground", C["border"])
    return tk.Frame(parent, **kw)


def button(parent, text, command=None, bg=None, fg=None, width=None):
    b = tk.Label(
        parent, text=text, bg=bg or C["blue"], fg=fg or "#ffffff",
        font=FONT_S, padx=12, pady=5, cursor="hand2",
    )
    if command:
        b.bind("<Button-1>", lambda e: command())
        b.bind("<Enter>", lambda e: b.config(bg=bg and _lighten(bg) or C["blue_hi"]))
        b.bind("<Leave>", lambda e: b.config(bg=bg or C["blue"]))
    if width:
        b.config(width=width)
    return b


def _lighten(hex_color):
    try:
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        return "#%02x%02x%02x" % (min(255, r + 18), min(255, g + 18), min(255, b + 18))
    except ValueError:
        return hex_color


def pill(parent, text, color):
    """小标签，如「暂停排班」「产品周例会」。"""
    return tk.Label(
        parent, text=" %s " % text, bg=color, fg="#ffffff",
        font=("Microsoft YaHei UI", 8), padx=6, pady=1,
    )


def toggle(parent, initial=False, command=None):
    """模拟 iOS 开关，返回 (widget, get_state)。"""
    state = {"on": initial}

    def draw():
        cv.delete("all")
        w, h = 36, 18
        bg = C["blue"] if state["on"] else "#30363d"
        cv.create_round = None
        # 圆角矩形：用椭圆+矩形近似
        r = h // 2
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

    cv = tk.Canvas(parent, width=36, height=18, bg=C["card"], highlightthickness=0)
    cv.bind("<Button-1>", click)
    draw()
    return cv, (lambda: state["on"])
