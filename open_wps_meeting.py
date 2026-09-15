#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打开本地 WPS 会议（wpsmeeting）软件。

设计要点：
1. 优先使用已知的可执行文件路径（本机已确认存在）。
2. 若已知路径失效，自动在常见安装目录中搜索 wpsmeeting.exe / kmeeting.exe。
3. 也支持通过桌面 / 开始菜单的 "WPS会议.lnk" 快捷方式启动。
4. Windows 下用 os.startfile / subprocess.Popen 启动；非 Windows 给出提示。
"""

import os
import subprocess
import sys

# 当前用户名（用于拼接 AppData 路径）
USER = os.environ.get("USERNAME") or os.environ.get("USER") or "max"

# 已知候选路径（按优先级排序）：可执行文件优先，其次快捷方式
CANDIDATE_PATHS = [
    # 主程序（最可靠）
    r"C:\Users\%s\AppData\Local\Programs\wpsmeeting\wpsmeeting.exe" % USER,
    # 作为 WPS Office 插件的会议组件
    r"C:\Users\%s\AppData\Roaming\kingsoft\wps\addons\pool\win-i386\kmeeting_3.1.0.590\kmeeting.exe" % USER,
    r"C:\Users\%s\AppData\Roaming\kingsoft\wps\addons\pool\win-i386\kmeeting_3.1.0.341\kmeeting.exe" % USER,
    # 桌面快捷方式
    r"C:\Users\%s\Desktop\WPS会议.lnk" % USER,
    r"C:\Users\%s\Desktop\software\WPS会议.lnk" % USER,
    # 开始菜单快捷方式
    r"C:\Users\%s\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\WPS会议.lnk" % USER,
]

# 搜索范围（在候选路径都不存在时，用于兜底查找）
SEARCH_DIRS = [
    r"C:\Users\%s\AppData\Local\Programs" % USER,
    r"C:\Users\%s\AppData\Roaming\kingsoft\wps\addons\pool\win-i386" % USER,
    r"C:\Program Files",
    r"C:\Program Files (x86)",
]
SEARCH_NAMES = ["wpsmeeting.exe", "kmeeting.exe"]


def find_by_search():
    """在常见目录中递归查找 wpsmeeting.exe / kmeeting.exe。"""
    for base in SEARCH_DIRS:
        if not os.path.isdir(base):
            continue
        try:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if f.lower() in SEARCH_NAMES:
                        return os.path.join(root, f)
        except PermissionError:
            # 某些子目录无权限，忽略即可
            continue
    return None


def resolve_target():
    """返回最终要启动的目标路径；找不到返回 None。"""
    for path in CANDIDATE_PATHS:
        if os.path.exists(path):
            return path
    return find_by_search()


def launch(target):
    """启动目标程序 / 快捷方式。"""
    if sys.platform.startswith("win"):
        # os.startfile 能正确解析 .lnk 快捷方式
        os.startfile(os.path.normpath(target))
        return True
    # 非 Windows：尝试用系统默认方式打开（通常仅对路径有效）
    try:
        subprocess.Popen(["xdg-open", target])
        return True
    except Exception:
        subprocess.Popen(["open", target])
        return True


def main():
    target = resolve_target()
    if not target:
        print("[错误] 未找到 WPS 会议（wpsmeeting.exe / kmeeting.exe）。")
        print("请确认 WPS 会议已安装，或手动修改脚本中的 CANDIDATE_PATHS。")
        sys.exit(1)

    print("[信息] 启动目标: %s" % target)
    try:
        launch(target)
        print("[成功] 已尝试打开 WPS 会议。")
    except Exception as e:
        print("[错误] 启动失败: %s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
