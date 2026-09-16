#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把会议信息发送到企业微信群（群机器人 Webhook）。

Webhook 地址读取顺序（避免把 key 硬编码进代码）：
1. 环境变量 WECOM_WEBHOOK
2. 同目录 wecom_webhook.txt 的第一行

消息内容：默认取剪贴板文本（copy_meeting_info.py 复制的会议信息）；
也可用 --text 直接指定。

用法：
    python send_to_wecom.py                  # 发送剪贴板内容（纯文本）
    python send_to_wecom.py --markdown       # markdown 排版发送
    python send_to_wecom.py --text "hello"   # 发送指定文本
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WEBHOOK_ENV = "WECOM_WEBHOOK"
WEBHOOK_FILE = "wecom_webhook.txt"


def resolve_webhook():
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    if url:
        return url
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), WEBHOOK_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            url = f.readline().strip()
        if url:
            return url
    print("[错误] 未配置企业微信机器人 Webhook。")
    print("       请在群设置里添加群机器人，复制 Webhook 地址，然后：")
    print("       1) 写入同目录 %s 文件第一行；或" % WEBHOOK_FILE)
    print("       2) 设置环境变量 %s" % WEBHOOK_ENV)
    sys.exit(2)


def to_markdown(text):
    """把会议信息纯文本转 markdown：普通行加换行，链接行转成可点击链接。"""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("http"):
            lines.append("[点击加入会议](%s)" % s)
        elif s:
            lines.append(s + "  ")
    return "\n".join(lines)


def send(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print("[错误] 网络请求失败: %s" % e)
        sys.exit(4)
    if body.get("errcode") != 0:
        print("[错误] 企业微信返回错误: %s" % body)
        sys.exit(5)
    print("[成功] 消息已发送到企业微信群。")


def main():
    parser = argparse.ArgumentParser(description="发送会议信息到企业微信群")
    parser.add_argument("--text", default=None, help="直接指定要发送的文本")
    parser.add_argument(
        "--url", default=None, help="Webhook 地址（不传则读环境变量或 wecom_webhook.txt）"
    )
    parser.add_argument("--markdown", action="store_true", help="以 markdown 格式发送")
    args = parser.parse_args()

    if args.url:
        url = args.url
    else:
        url = resolve_webhook()

    text = args.text
    if not text:
        from copy_meeting_info import get_clipboard_text

        text = get_clipboard_text()
    if not text:
        print("[错误] 剪贴板为空，且未用 --text 指定内容")
        sys.exit(3)

    if args.markdown:
        payload = {"msgtype": "markdown", "markdown": {"content": to_markdown(text)}}
    else:
        payload = {"msgtype": "text", "text": {"content": text}}
    print("[信息] 发送内容（%d 字符）" % len(text))
    send(url, payload)


if __name__ == "__main__":
    main()
