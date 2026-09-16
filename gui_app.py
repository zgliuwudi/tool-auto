# -*- coding: utf-8 -*-
"""会议助手 v1.0.0 —— WPS 会议定时预约 + 企业微信推送 桌面客户端。"""
import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, simpledialog  # noqa: F401

import store
from ui_widgets import C, FONT, FONT_B, FONT_S, FONT_H, FONT_NUM, card, button, pill, toggle

PAGES = [
    ("overview", "概览"),
    ("tasks", "定时任务"),
    ("webhook", "Webhook 配置"),
    ("logs", "执行日志"),
    ("settings", "系统设置"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WPS 会议助手")
        self.geometry("1180x740")
        self.configure(bg=C["bg"])
        self._q = queue.Queue()
        self._sched = store.Scheduler(on_event=lambda k, p: self._q.put((k, p)))
        self._sched.start()

        side = tk.Frame(self, bg=C["side"], width=200)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="\n 会议助手", bg=C["side"], fg=C["text"],
                 font=FONT_H, anchor="w").pack(fill="x")
        tk.Label(side, text=" v1.0.0", bg=C["side"], fg=C["muted"],
                 font=FONT_S, anchor="w").pack(fill="x")
        tk.Label(side, text="\n导航", bg=C["side"], fg=C["muted"],
                 font=FONT_S, anchor="w").pack(fill="x", padx=16)
        self._nav_btns = {}
        for key, label in PAGES:
            b = tk.Label(side, text="  " + label, bg=C["side"], fg=C["text"],
                         font=FONT, anchor="w", pady=8, cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=key: self.show(k))
            self._nav_btns[key] = b
        self._bottom = tk.Frame(side, bg=C["card"], highlightthickness=1,
                                highlightbackground=C["border"])
        self._bottom.pack(side="bottom", fill="x", padx=10, pady=10)
        self._next_label = tk.Label(self._bottom, text="", bg=C["card"], fg=C["text"],
                                    font=FONT_S, justify="left")
        self._next_label.pack(padx=10, pady=8, anchor="w")

        self._content = tk.Frame(self, bg=C["bg"])
        self._content.pack(side="right", fill="both", expand=True)
        self._pages = {}
        self._build_pages()
        self.show("overview")
        self.after(300, self._poll)
        self._refresh_bottom()

    # ---- 框架 ----
    def show(self, key):
        for k, b in self._nav_btns.items():
            b.config(bg=C["blue"] if k == key else C["side"],
                     fg="#ffffff" if k == key else C["text"])
        for k, p in self._pages.items():
            p.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        self._pages[key].refresh()

    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "log":
                    self._pages["logs"].append_runtime(payload)
                elif kind == "tasks_changed":
                    self._refresh_bottom()
                    self._pages["overview"].refresh()
                    self._pages["tasks"].refresh()
                elif kind in ("start", "done"):
                    self._refresh_bottom()
        except queue.Empty:
            pass
        self.after(300, self._poll)

    def _refresh_bottom(self):
        lines = []
        for t in store.load_tasks():
            if t.get("enabled", True):
                lines.append(t["name"] + "\n" + store.next_run_desc(t))
        self._next_label.config(text="\n下次执行\n" + "\n".join(lines[:2]) or "无任务")

    def _build_pages(self):
        self._pages["overview"] = OverviewPage(self._content, self)
        self._pages["tasks"] = TasksPage(self._content, self)
        self._pages["webhook"] = WebhookPage(self._content, self)
        self._pages["logs"] = LogsPage(self._content, self)
        self._pages["settings"] = SettingsPage(self._content, self)


def page_header(parent, title, subtitle, right=None):
    bar = tk.Frame(parent, bg=C["bg"])
    bar.pack(fill="x", padx=28, pady=(22, 10))
    tk.Label(bar, text=title, bg=C["bg"], fg=C["text"], font=FONT_H).pack(side="left")
    if right:
        right.pack(side="right")
    tk.Label(parent, text=subtitle, bg=C["bg"], fg=C["muted"], font=FONT_S
             ).pack(anchor="w", padx=28)


class OverviewPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()
        tasks = store.load_tasks()
        hist = store.load_history()
        month = datetime.now().strftime("%Y-%m")
        ok = sum(1 for h in hist if h["status"] == "成功" and h["ts"].startswith(month))
        fail = sum(1 for h in hist if h["status"] == "失败" and h["ts"].startswith(month))
        stats = tk.Frame(self, bg=C["bg"])
        stats.pack(fill="x", padx=28)
        cards = [("定时任务", len(tasks), C["blue"]),
                 ("本月执行成功", ok, C["green_t"]),
                 ("执行失败", fail, C["red_t"])]
        for title, num, color in cards:
            c = card(stats)
            c.pack(side="left", fill="x", expand=True, padx=(0, 14), ipadx=10)
            tk.Label(c, text=title, bg=C["card"], fg=C["muted"], font=FONT_S
                     ).pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(c, text=str(num), bg=C["card"], fg=color, font=FONT_NUM
                     ).pack(anchor="w", padx=16)
            tk.Label(c, text="共 %d 条记录" % num, bg=C["card"], fg=C["muted"],
                     font=FONT_S).pack(anchor="w", padx=16, pady=(0, 12))

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=14)
        left = card(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))
        tk.Label(left, text="任务列表", bg=C["card"], fg=C["text"],
                 font=FONT_B).pack(anchor="w", padx=16, pady=12)
        for t in tasks[:6]:
            row = tk.Frame(left, bg=C["card2"])
            row.pack(fill="x", padx=12, pady=4)
            dot = C["green_t"] if t.get("enabled", True) else C["muted"]
            tk.Label(row, text="●", bg=C["card2"], fg=dot, font=FONT_S
                     ).pack(side="left", padx=(10, 4))
            tk.Label(row, text=t["name"], bg=C["card2"], fg=C["text"],
                     font=FONT_B).pack(side="left")
            pill(row, t.get("group", "未分组"), C["purple"]).pack(side="left", padx=8)
            tk.Label(row, text="%s  %s  下次: %s" % (
                t.get("trigger", ""), " ".join(store.WEEKDAY_NAMES[d] for d in t.get("weekdays", [])),
                store.next_run_desc(t)), bg=C["card2"], fg=C["muted"], font=FONT_S
                     ).pack(side="left", padx=4)
        if not tasks:
            tk.Label(left, text="暂无任务，去「定时任务」页新增", bg=C["card"],
                     fg=C["muted"], font=FONT_S).pack(pady=20)

        right = card(body)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="固定执行日志", bg=C["card"], fg=C["text"],
                 font=FONT_B).pack(anchor="w", padx=16, pady=12)
        for h in hist[:8]:
            row = tk.Frame(right, bg=C["card2"])
            row.pack(fill="x", padx=12, pady=4)
            mark = "✔" if h["status"] == "成功" else "✖"
            color = C["green_t"] if h["status"] == "成功" else C["red_t"]
            tk.Label(row, text=mark, bg=C["card2"], fg=color, font=FONT_S
                     ).pack(side="left", padx=(10, 4))
            tk.Label(row, text="%s  %s" % (h["task"], h["status"]), bg=C["card2"],
                     fg=C["text"], font=FONT_S).pack(side="left")
            tk.Label(row, text=h["detail"][:40], bg=C["card2"], fg=C["muted"],
                     font=FONT_S).pack(side="left", padx=6)
            tk.Label(row, text=h["ts"][:16], bg=C["card2"], fg=C["muted"],
                     font=FONT_S).pack(side="right", padx=10)

class WebhookPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(top, text="企业微信群 Webhook", bg=C["bg"], fg=C["text"],
                 font=FONT_H).pack(side="left")
        button(top, "＋ 添加 Webhook", self._add).pack(side="right")
        tk.Label(self, text="配置每条群机器人 Webhook 地址，用于发送会议通知",
                 bg=C["bg"], fg=C["muted"], font=FONT_S).pack(anchor="w", padx=28)

        for g in store.load_groups():
            c = card(self)
            c.pack(fill="x", padx=28, pady=(10, 0))
            head = tk.Frame(c, bg=C["card"])
            head.pack(fill="x", padx=14, pady=(10, 0))
            tk.Label(head, text="●", bg=C["card"], fg=C["green_t"],
                     font=FONT_S).pack(side="left")
            tk.Label(head, text="  " + g["name"], bg=C["card"], fg=C["text"],
                     font=FONT_B).pack(side="left")
            button(head, "复制", lambda u=g.get("url", ""): self._copy(u),
                   bg=C["card2"]).pack(side="right", padx=4)
            button(head, "🗑", lambda g=g: self._del(g), bg=C["card"]).pack(side="right")
            row = tk.Frame(c, bg=C["card"])
            row.pack(fill="x", padx=14, pady=(6, 12))
            e = tk.Entry(row, bg=C["entry"], fg=C["muted"], relief="flat",
                         font=("Consolas", 9), highlightthickness=1,
                         highlightbackground=C["border"])
            e.insert(0, g.get("url", ""))
            e.pack(side="left", fill="x", expand=True, ipady=4)

            def save_url(e=e, g=g):
                g["url"] = e.get().strip()
                groups = store.load_groups()
                for x in groups:
                    if x.get("name") == g.get("name"):
                        x["url"] = g["url"]
                store.save_groups(groups)
            e.bind("<FocusOut>", save_url)

        tip = card(self)
        tip.pack(fill="x", padx=28, pady=16)
        tk.Label(tip, text="如何获取企业微信 Webhook 地址?", bg=C["card"],
                 fg=C["text"], font=FONT_B).pack(anchor="w", padx=16, pady=(12, 4))
        for line in ("打开企业微信，进入目标群聊",
                     "点击右上角「...」→「群机器人」→「添加机器人」",
                     "创建机器人后，复制 Webhook 地址",
                     "将地址粘贴到上方输入框中"):
            tk.Label(tip, text="•  " + line, bg=C["card"], fg=C["muted"],
                     font=FONT_S).pack(anchor="w", padx=24)
        tk.Label(tip, text="", bg=C["card"]).pack(pady=6)

    def _add(self):
        name = simpledialog.askstring("添加 Webhook", "群名称：", parent=self)
        if not name:
            return
        url = simpledialog.askstring(
            "添加 Webhook", "Webhook 地址：", parent=self,
            initialvalue="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=")
        if not url:
            return
        groups = store.load_groups()
        groups.append({"name": name, "url": url.strip(), "enabled": True})
        store.save_groups(groups)
        self.refresh()

    def _del(self, g):
        if messagebox.askyesno("删除", "确定删除「%s」？" % g["name"]):
            store.save_groups([x for x in store.load_groups()
                               if x.get("name") != g.get("name")])
            self.refresh()

    def _copy(self, url):
        self.app.clipboard_clear()
        self.app.clipboard_append(url)
        messagebox.showinfo("已复制", "Webhook 地址已复制到剪贴板")


class LogsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.filter = "全部"
        self.runtime_text = ""

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(top, text="执行日志", bg=C["bg"], fg=C["text"], font=FONT_H
                 ).pack(side="left")
        for label in ("全部", "成功", "失败"):
            bg = C["blue"] if self.filter == label else C["card"]
            button(top, label, lambda l=label: self._set_filter(l), bg=bg
                   ).pack(side="right", padx=3)
        tk.Label(self, text="查看每条任务的执行记录", bg=C["bg"], fg=C["muted"],
                 font=FONT_S).pack(anchor="w", padx=28)

        box = tk.Frame(self, bg=C["bg"])
        box.pack(fill="both", expand=True, padx=28, pady=14)
        hist = store.load_history()
        if not hist and not self.runtime_text:
            c = card(box)
            c.pack(fill="x")
            tk.Label(c, text="暂无记录", bg=C["card"], fg=C["muted"],
                     font=FONT_S).pack(pady=20)
        for h in hist[:50]:
            if self.filter != "全部" and h["status"] != self.filter:
                continue
            c = card(box)
            c.pack(fill="x", pady=(0, 8))
            row = tk.Frame(c, bg=C["card"])
            row.pack(fill="x", padx=14, pady=(10, 0))
            mark = "✔" if h["status"] == "成功" else "✖"
            color = C["green_t"] if h["status"] == "成功" else C["red_t"]
            tk.Label(row, text=mark, bg=C["card"], fg=color, font=FONT_B
                     ).pack(side="left", padx=(0, 8))
            tk.Label(row, text=h["task"], bg=C["card"], fg=C["text"],
                     font=FONT_B).pack(side="left")
            pill(row, h["status"],
                 C["green"] if h["status"] == "成功" else C["red"]
                 ).pack(side="left", padx=8)
            tk.Label(row, text=h["ts"], bg=C["card"], fg=C["muted"],
                     font=FONT_S).pack(side="right")
            tk.Label(c, text="    " + h["detail"], bg=C["card"], fg=C["muted"],
                     font=FONT_S, anchor="w").pack(fill="x", padx=10, pady=(2, 10))
        if self.runtime_text:
            c = card(box)
            c.pack(fill="both", expand=True, pady=(8, 0))
            tk.Label(c, text="实时输出", bg=C["card"], fg=C["text"],
                     font=FONT_B).pack(anchor="w", padx=14, pady=(8, 2))
            t = tk.Text(c, bg=C["entry"], fg=C["green_t"], relief="flat",
                        font=("Consolas", 9), height=8)
            t.pack(fill="x", padx=14, pady=(0, 12))
            t.insert("1.0", self.runtime_text)
            t.config(state="disabled")

    def append_runtime(self, msg):
        self.runtime_text = getattr(self, "runtime_text", "") + msg + "\n"
        tail = self.runtime_text.splitlines()[-200:]
        self.runtime_text = "\n".join(tail)

    def _set_filter(self, label):
        self.filter = label
        self.refresh()


class SettingsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()
        st = store.load_settings()
        page = tk.Frame(self, bg=C["bg"])
        page.pack(fill="both", expand=True)
        page_header(page, "系统设置", "调整 WPS 启动、告警模板和重试参数")

        def section(title):
            c = card(page)
            c.pack(fill="x", padx=28, pady=(0, 14))
            tk.Label(c, text=title, bg=C["card"], fg=C["text"],
                     font=FONT_B).pack(anchor="w", padx=16, pady=(12, 4))
            return c

        def field(parent, label, value):
            tk.Label(parent, text=label, bg=C["card"], fg=C["muted"],
                     font=FONT_S).pack(anchor="w", padx=16)
            e = tk.Entry(parent, bg=C["entry"], fg=C["text"],
                         insertbackground=C["text"], relief="flat", font=FONT,
                         highlightthickness=1, highlightbackground=C["border"])
            e.insert(0, str(value))
            e.pack(fill="x", padx=16, pady=(2, 10))
            return e

        c1 = section("WPS 客户端配置")
        e_path = field(c1, "WPS 启动文件路径", st["wps_path"])
        e_args = field(c1, "启动参数", st["wps_args"])

        c2 = section("消息模板")
        tk.Label(c2, text="模板变量占位符（可选填, 无效果）: (task) (link) (time)",
                 bg=C["card"], fg=C["muted"], font=FONT_S).pack(anchor="w", padx=16)
        t_ok = tk.Text(c2, bg=C["entry"], fg=C["text"], relief="flat", font=FONT,
                       height=5, highlightthickness=1,
                       highlightbackground=C["border"])
        t_ok.insert("1.0", st["msg_success"])
        t_ok.pack(fill="x", padx=16, pady=(4, 8))
        t_fail = tk.Text(c2, bg=C["entry"], fg=C["text"], relief="flat", font=FONT,
                         height=2, highlightthickness=1,
                         highlightbackground=C["border"])
        t_fail.insert("1.0", st["msg_fail"])
        t_fail.pack(fill="x", padx=16, pady=(0, 12))

        c3 = section("失败重试问题")
        e_retry = field(c3, "最大重试次数", st["retry_max"])
        e_intv = field(c3, "重试间隔 (秒)", st["retry_interval"])

        def save():
            store.save_settings({
                "wps_path": e_path.get().strip(),
                "wps_args": e_args.get().strip(),
                "msg_success": t_ok.get("1.0", "end").strip(),
                "msg_fail": t_fail.get("1.0", "end").strip(),
                "retry_max": e_retry.get().strip() or 3,
                "retry_interval": e_intv.get().strip() or 30,
            })
            messagebox.showinfo("已保存", "系统设置已保存")

        bar = tk.Frame(page, bg=C["bg"])
        bar.pack(fill="x", pady=(4, 20))
        button(bar, "💾 保存设置", save).pack(side="right", padx=28)


class TasksPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(top, text="定时任务", bg=C["bg"], fg=C["text"], font=FONT_H
                 ).pack(side="left")
        button(top, "＋ 新建任务", self._new_task).pack(side="right")
        tk.Label(self, text="创建任务后由程序自动在 WPS 会议开始前完成预约并推送到群",
                 bg=C["bg"], fg=C["muted"], font=FONT_S).pack(anchor="w", padx=28)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=14)
        left = tk.Frame(body, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        tasks = store.load_tasks()
        if not tasks:
            c = card(left)
            c.pack(fill="x")
            tk.Label(c, text="暂无任务", bg=C["card"], fg=C["muted"],
                     font=FONT_S).pack(pady=30)
        for t in tasks:
            self._task_card(left, t)
        self._calendar(body)

    def _task_card(self, parent, t):
        c = card(parent)
        c.pack(fill="x", pady=(0, 10))
        head = tk.Frame(c, bg=C["card"])
        head.pack(fill="x", padx=14, pady=(10, 0))
        dot = C["green_t"] if t.get("enabled", True) else C["muted"]
        tk.Label(head, text="●", bg=C["card"], fg=dot, font=FONT_S
                 ).pack(side="left")
        tk.Label(head, text="  " + t["name"], bg=C["card"], fg=C["text"],
                 font=FONT_B).pack(side="left")
        pill(head, t.get("group", "未分组"), C["purple"]).pack(side="left", padx=8)
        _, get = toggle(head, t.get("enabled", True),
                        lambda on, t=t: self._toggle(t, on))
        get()
        button(head, "▶ 执行", lambda t=t: self._run_now(t), bg=C["card2"]).pack(
            side="right", padx=4)
        button(head, "✎", lambda t=t: self._edit(t), bg=C["card"]).pack(
            side="right", padx=4)
        button(head, "🗑", lambda t=t: self._delete(t), bg=C["card"]).pack(side="right")
        info = tk.Frame(c, bg=C["card"])
        info.pack(fill="x", padx=14, pady=(0, 10))
        days = " ".join(store.WEEKDAY_NAMES[d] for d in t.get("weekdays", []))
        tk.Label(info, text="🕐  %s    %s    下次: %s" % (
            t.get("trigger", ""), days, store.next_run_desc(t)),
            bg=C["card"], fg=C["muted"], font=FONT_S).pack(side="left")

    def _toggle(self, t, on):
        t["enabled"] = on
        tasks = store.load_tasks()
        for x in tasks:
            if x.get("id") == t.get("id"):
                x["enabled"] = on
        store.save_tasks(tasks)
        self.refresh()

    def _delete(self, t):
        if messagebox.askyesno("删除", "确定删除任务「%s」？" % t["name"]):
            store.save_tasks([x for x in store.load_tasks()
                              if x.get("id") != t.get("id")])
            self.refresh()

    def _run_now(self, t):
        """立即执行一次该任务（与调度器互斥，避免同时操作 WPS）。"""
        sched = self.app._sched
        if sched.busy.is_set():
            messagebox.showinfo("提示", "有任务正在执行中，请稍后再试")
            return
        if not messagebox.askyesno("执行", "现在立刻执行一次「%s」？" % t["name"]):
            return
        name = t["name"]

        def work():
            sched.busy.set()
            sched.on_event("start", t)
            sched.log("手动触发任务「%s」" % name)
            ok, detail = store.execute_task(t, sched.log)
            sched.on_event("done", {"ok": ok, "detail": detail, "task": name})
            sched.busy.clear()

        threading.Thread(target=work, daemon=True).start()
        messagebox.showinfo(
            "已开始", "任务已在后台执行，过程与结果见「执行日志」页")

    def _new_task(self):
        TaskDialog(self, on_saved=self.refresh)

    def _edit(self, t):
        TaskDialog(self, task=t, on_saved=self.refresh)

    def _calendar(self, parent):
        right = card(parent)
        right.pack(side="right", fill="y", padx=(14, 0), ipadx=6)
        tk.Label(right, text="排班日历预览", bg=C["card"], fg=C["text"],
                 font=FONT_B).pack(anchor="w", padx=14, pady=(12, 4))
        now = datetime.now()
        tk.Label(right, text=now.strftime("%Y 年 %m 月"), bg=C["card"],
                 fg=C["text"], font=FONT_B).pack(pady=(0, 6))
        cal = tk.Frame(right, bg=C["card"])
        cal.pack(padx=10)
        for i, d in enumerate(["日", "一", "二", "三", "四", "五", "六"]):
            tk.Label(cal, text=d, bg=C["card"], fg=C["muted"], font=FONT_S,
                     width=3).grid(row=0, column=i)
        first = now.replace(day=1)
        days = (first + timedelta(days=32)).replace(day=1) - first
        active = set()
        for t in store.load_tasks():
            if t.get("enabled", True):
                for off in range(days.days):
                    d = first + timedelta(days=off)
                    if d.weekday() in t.get("weekdays", []):
                        active.add(d.day)
        for off in range(days.days):
            day = first + timedelta(days=off)
            col, row = (first.weekday() + 1) % 7, off // 7 + 1
            today = day.day == now.day
            tk.Label(cal, text=str(day.day), width=3,
                     bg=C["blue"] if today else C["card"],
                     fg="#ffffff" if today else (C["red_t"] if day.day in active else C["muted"]),
                     font=FONT_S).grid(row=row, column=col, pady=1)
        legend = tk.Frame(right, bg=C["card"])
        legend.pack(anchor="w", padx=14, pady=(6, 0))
        tk.Label(legend, text="● 排班日   ● 今天", bg=C["card"], fg=C["muted"],
                 font=FONT_S).pack()
        tk.Label(right, text="已排班日期", bg=C["card"], fg=C["text"],
                 font=FONT_S).pack(anchor="w", padx=14, pady=(8, 2))
        box = tk.Frame(right, bg=C["card"])
        box.pack(fill="x", padx=12, pady=(0, 12))
        col = 0
        for off in range(days.days):
            d = first + timedelta(days=off)
            if d.weekday() in [x for t in store.load_tasks()
                               if t.get("enabled", True) for x in t.get("weekdays", [])]:
                pill(box, d.strftime("%Y-%m-%d"), C["red"]).grid(
                    row=col // 2, column=col % 2, padx=3, pady=2, sticky="w")
                col += 1


class TaskDialog(tk.Toplevel):
    """新建/编辑任务弹窗。"""

    def __init__(self, master, task=None, on_saved=None):
        super().__init__(master)
        self.title("新建任务" if task is None else "编辑任务")
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.on_saved = on_saved
        self.task = task or {"id": "%d" % int(datetime.now().timestamp() * 1000),
                             "weekdays": [0, 1, 2, 3, 4], "enabled": True}
        tk.Label(self, text="新建任务" if task is None else "编辑任务",
                 bg=C["card"], fg=C["text"], font=FONT_H).pack(
            anchor="w", padx=24, pady=(18, 8))

        tk.Label(self, text="任务名称", bg=C["card"], fg=C["muted"],
                 font=FONT_S).pack(anchor="w", padx=24)
        e_name = tk.Entry(self, bg=C["entry"], fg=C["text"], insertbackground=C["text"],
                          relief="flat", font=FONT, highlightthickness=1,
                          highlightbackground=C["border"])
        e_name.insert(0, self.task.get("name", ""))
        e_name.pack(fill="x", padx=24, pady=(2, 10))

        tk.Label(self, text="执行时间", bg=C["card"], fg=C["muted"],
                 font=FONT_S).pack(anchor="w", padx=24)
        e_time = tk.Entry(self, bg=C["entry"], fg=C["text"], insertbackground=C["text"],
                          relief="flat", font=FONT, highlightthickness=1,
                          highlightbackground=C["border"], width=12)
        e_time.insert(0, self.task.get("trigger", "09:00"))
        e_time.pack(anchor="w", padx=24, pady=(2, 10))

        tk.Label(self, text="会议结束时间", bg=C["card"], fg=C["muted"],
                 font=FONT_S).pack(anchor="w", padx=24)
        e_end = tk.Entry(self, bg=C["entry"], fg=C["text"], insertbackground=C["text"],
                         relief="flat", font=FONT, highlightthickness=1,
                         highlightbackground=C["border"], width=12)
        e_end.insert(0, self.task.get("meeting_end", "10:00"))
        e_end.pack(anchor="w", padx=24, pady=(2, 10))

        tk.Label(self, text="重复日期", bg=C["card"], fg=C["muted"],
                 font=FONT_S).pack(anchor="w", padx=24)
        days = tk.Frame(self, bg=C["card"])
        days.pack(anchor="w", padx=24, pady=(2, 10))
        self._day_vars = []
        for i, d in enumerate(store.WEEKDAY_NAMES):
            v = {"on": i in self.task.get("weekdays", []), "idx": i}
            b = tk.Label(days, text=d, width=4, pady=4, cursor="hand2",
                         bg=C["blue"] if v["on"] else C["card2"],
                         fg="#ffffff" if v["on"] else C["muted"], font=FONT_S)

            def click(e, v=v, b=b):
                v["on"] = not v["on"]
                b.config(bg=C["blue"] if v["on"] else C["card2"],
                         fg="#ffffff" if v["on"] else C["muted"])
            b.bind("<Button-1>", click)
            b.pack(side="left", padx=2)
            self._day_vars.append(v)

        tk.Label(self, text="企业微信群", bg=C["card"], fg=C["muted"],
                 font=FONT_S).pack(anchor="w", padx=24)
        groups = [g["name"] for g in store.load_groups()]
        combo = ttk.Combobox(self, values=groups or ["（先去 Webhook 配置添加）"],
                             state="readonly", font=FONT_S)
        if self.task.get("group"):
            combo.set(self.task["group"])
        elif groups:
            combo.current(0)
        combo.pack(fill="x", padx=24, pady=(2, 10))

        en = tk.BooleanVar(value=self.task.get("enabled", True))
        ttk.Checkbutton(self, text="启用此任务", variable=en).pack(
            anchor="w", padx=24, pady=(0, 14))

        row = tk.Frame(self, bg=C["card"])
        row.pack(fill="x", padx=24, pady=(0, 18))
        button(row, "取消", self.destroy, bg=C["card2"]).pack(side="right", padx=4)
        button(row, "✔ 保存", lambda: self._save(
            e_name, e_time, e_end, combo, en)).pack(side="right")

    def _save(self, e_name, e_time, e_end, combo, en):
        name = e_name.get().strip()
        if not name:
            messagebox.showwarning("提示", "请填写任务名称", parent=self)
            return
        trigger = e_time.get().strip()
        try:
            h, m = map(int, trigger.split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except (ValueError, AssertionError):
            messagebox.showwarning("提示", "执行时间格式应为 HH:MM", parent=self)
            return
        weekdays = [v["idx"] for v in self._day_vars if v["on"]]
        if not weekdays:
            messagebox.showwarning("提示", "请至少选择一个重复日期", parent=self)
            return
        tasks = [t for t in store.load_tasks() if t.get("id") != self.task.get("id")]
        tasks.append({
            "id": self.task.get("id"),
            "name": name,
            "enabled": en.get(),
            "trigger": "%02d:%02d" % (h, m),
            "meeting_end": e_end.get().strip() or "10:00",
            "weekdays": sorted(weekdays),
            "group": combo.get(),
            "last_run_date": self.task.get("last_run_date"),
        })
        store.save_tasks(tasks)
        self.destroy()
        if self.on_saved:
            self.on_saved()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

