# -*- coding: utf-8 -*-
"""数据层：任务 / 企业微信群 Webhook / 执行历史 / 系统设置的 JSON 存取，
以及到点执行会议预约流水线的调度线程。"""
import importlib
import io
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

# exe（PyInstaller）模式下配置/数据文件放在 exe 所在目录，而非临时解压目录
FROZEN = getattr(sys, "frozen", False)
BASE = (os.path.dirname(sys.executable) if FROZEN
        else os.path.dirname(os.path.abspath(__file__)))
if FROZEN:
    os.chdir(BASE)  # exe 模式下模板/配置均相对 exe 目录
TASKS_FILE = os.path.join(BASE, "scheduler_tasks.json")
GROUPS_FILE = os.path.join(BASE, "scheduler_groups.json")
HISTORY_FILE = os.path.join(BASE, "scheduler_history.json")
SETTINGS_FILE = os.path.join(BASE, "system_settings.json")
CONFIG_FILE = os.path.join(BASE, "meeting_config.json")

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

DEFAULT_SETTINGS = {
    "wps_path": r"C:\Program Files\Kingsoft\WPS Office\office6\wps.exe",
    "wps_args": "--meeting --new",
    "msg_success": "【{task}】会议预约开始\n会议主题: {subject}\n会议链接: {link}\n时间: {time}",
    "msg_fail": "会议预约失败",
    "retry_max": 3,
    "retry_interval": 30,
}


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- 任务 ----------
def load_tasks():
    return _load(TASKS_FILE, [])


def save_tasks(tasks):
    _save(TASKS_FILE, tasks)


# ---------- 企业微信群（webhook） ----------
def load_groups():
    return _load(GROUPS_FILE, [])


def save_groups(groups):
    _save(GROUPS_FILE, groups)


# ---------- 执行历史 ----------
def load_history():
    return _load(HISTORY_FILE, [])


def add_history(entry):
    hist = load_history()
    hist.insert(0, entry)
    _save(HISTORY_FILE, hist[:500])


# ---------- 系统设置 ----------
def load_settings():
    st = dict(DEFAULT_SETTINGS)
    st.update(_load(SETTINGS_FILE, {}))
    return st


def save_settings(st):
    _save(SETTINGS_FILE, st)


def group_url(name):
    """按群名取 webhook 地址。"""
    for g in load_groups():
        if g.get("name") == name:
            return g.get("url", "")
    return ""


# ---------- 执行流水线 ----------
def run_step(module_name, argv, log):
    """统一执行入口。

    源码模式：子进程 `python xxx.py`，崩溃互不影响；
    exe 模式（PyInstaller）：无独立解释器，改为进程内调用各脚本 main()。
    """
    log("  $ %s %s" % (module_name, " ".join(argv)))
    if not FROZEN:
        p = subprocess.run(
            [sys.executable, module_name + ".py"] + argv,
            cwd=BASE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        out = (p.stdout or "") + (p.stderr or "")
        tail = out.strip().splitlines()[-3:] if out.strip() else []
        for line in tail:
            log("    " + line)
        if p.returncode != 0:
            raise RuntimeError("%s 退出码 %d" % (module_name, p.returncode))
        return

    old_argv = sys.argv
    old_out, old_err = sys.stdout, sys.stderr
    buf = io.StringIO()
    sys.argv = [module_name + ".py"] + argv
    sys.stdout = sys.stderr = buf
    try:
        importlib.import_module(module_name).main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if code != 0:
            raise RuntimeError("%s 退出码 %d" % (module_name, code))
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        sys.argv = old_argv
    out = buf.getvalue()
    tail = out.strip().splitlines()[-3:] if out.strip() else []
    for line in tail:
        log("    " + line)


def write_meeting_config(task):
    today = datetime.now().strftime("%Y/%m/%d")
    cfg = {
        "subject": task.get("name", "会议"),
        "start_time": "%s %s" % (today, task.get("meeting_start")
                                 or task.get("trigger", "09:00")),
        "end_time": "%s %s" % (today, task.get("meeting_end", "10:00")),
    }
    _save(CONFIG_FILE, cfg)


def execute_task(task, log):
    """执行完整预约流水线，返回 (ok, detail)。"""
    name = task.get("name", "会议")
    settings = load_settings()
    url = group_url(task.get("group", ""))

    def once(attempt):
        log("第 %d 次尝试" % attempt)
        write_meeting_config(task)
        for module_name in (
            "click_reserve_meeting",
            "fill_meeting_form",
            "copy_meeting_info",
        ):
            run_step(module_name, [], log)
        run_step("send_to_wecom", ["--url", url] if url else [], log)

    attempt = 1
    while True:
        try:
            once(attempt)
            add_history({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "task": name, "status": "成功", "detail": "会议预约并发送至群",
            })
            return True, "执行成功"
        except Exception as e:  # noqa: BLE001
            log("  失败: %s" % e)
            if attempt >= int(settings.get("retry_max", 3)):
                add_history({
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "task": name, "status": "失败", "detail": str(e)[:120],
                })
                return False, str(e)[:120]
            time.sleep(int(settings.get("retry_interval", 30)))
            attempt += 1


class Scheduler(threading.Thread):
    """后台调度线程：每 20 秒扫描启用的任务，到点执行。

    任务字段：
      id, name, enabled, trigger "HH:MM", weekdays [0-6],
      group(群名), meeting_end "HH:MM", last_run_date "YYYY-MM-DD"
    """

    def __init__(self, on_event=None):
        super().__init__(daemon=True)
        self.on_event = on_event  # on_event(kind, payload)，供 UI 刷新
        self.busy = threading.Event()

    def log(self, msg):
        if self.on_event:
            self.on_event("log", msg)

    def run(self):
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                self.log("调度异常: %s" % e)
            time.sleep(20)

    def tick(self):
        if self.busy.is_set():
            return
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        for task in load_tasks():
            if not task.get("enabled", True):
                continue
            if task.get("last_run_date") == today:
                continue
            if now.weekday() not in task.get("weekdays", list(range(7))):
                continue
            hh, mm = (task.get("trigger") or "00:00").split(":")[:2]
            if (now.hour, now.minute) < (int(hh), int(mm)):
                continue
            # 到点执行（同一天只跑一次）
            self.busy.set()
            tasks = load_tasks()
            for t in tasks:
                if t.get("id") == task.get("id"):
                    t["last_run_date"] = today
            save_tasks(tasks)
            name = task.get("name", "会议")
            self.log("触发任务「%s」" % name)
            if self.on_event:
                self.on_event("start", task)
            ok, detail = execute_task(task, self.log)
            if self.on_event:
                self.on_event("done", {"ok": ok, "detail": detail, "task": name})
            self.busy.clear()
            if self.on_event:
                self.on_event("tasks_changed", None)
            return  # 一轮只执行一个任务


def next_run_desc(task):
    """任务下次执行的简述，如 '2026-09-18 09:30'。"""
    now = datetime.now()
    weekdays = task.get("weekdays", list(range(7)))
    hh, mm = (task.get("trigger") or "00:00").split(":")[:2]
    for offset in range(8):
        d = now + timedelta(days=offset)
        if d.weekday() not in weekdays:
            continue
        if offset == 0 and (d.hour, d.minute) >= (int(hh), int(mm)):
            continue
        return d.strftime("%Y-%m-%d") + " " + task.get("trigger", "00:00")
    return "-"
