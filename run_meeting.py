#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整串联：
1. 打开/激活 WPS 会议
2. 点击「预约会议」
3. 读取 meeting_config.json 填写表单
4. 点击「保存」
5. 分享会议并复制会议信息到剪贴板
6. 通过群机器人 Webhook 发送到企业微信群

用法：
    python run_meeting.py
"""

import subprocess
import sys


def run_step(script):
    print("\n========== 执行: %s ==========" % script)
    proc = subprocess.run([sys.executable, script], cwd=".")
    if proc.returncode != 0:
        print("[错误] %s 执行失败，退出码 %d" % (script, proc.returncode))
        sys.exit(proc.returncode)


def main():
    run_step("click_reserve_meeting.py")
    print("[信息] 等待预约表单稳定渲染 ...")
    # 表单弹出需要一点时间，给足 2 秒
    import time
    time.sleep(2)
    run_step("fill_meeting_form.py")
    run_step("copy_meeting_info.py")
    run_step("send_to_wecom.py")


if __name__ == "__main__":
    main()
