# tool-auto

自动化预约 WPS 会议并推送到企业微信群。

## 功能

- 自动启动 WPS 会议并点击「预约会议」
- 按配置自动填写会议主题、开始/结束时间并保存
- 自动分享会议并复制邀请信息（含入会链接）到剪贴板
- 通过企业微信群机器人 Webhook 推送到指定群聊

## 环境要求

- Windows + Python 3.8+
- 依赖：`opencv-python`、`numpy`、`Pillow`
- WPS 会议客户端（wpsmeeting）
- 企业微信群机器人 Webhook 地址（群设置 → 群机器人 → 添加）

## 配置

编辑 `meeting_config.json`：

```json
{
  "subject": "周例会",
  "start_time": "2026/10/01 09:30",
  "end_time": "2026/10/01 11:30"
}
```

在 `wecom_webhook.txt` 第一行填入群机器人 Webhook 地址，
或设置环境变量 `WECOM_WEBHOOK`（二选一，密钥请勿提交到仓库）。

## 配置企业微信 Webhook（wecom_webhook.txt）

该文件含机器人密钥，出于安全考虑**没有提交到仓库**，需要自己创建。

### 第 1 步：获取 Webhook 地址

1. 打开企业微信的目标群聊 → 右上角「...」→ **群机器人** → **添加机器人**
2. 创建后复制 Webhook 地址，形如：

```
https://qyapi.weixin.qq.com/cgi-webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

（注意：机器人只能在**企业内部群**添加，客户群不支持。）

### 第 2 步：创建配置文件

在**项目根目录**（即 `run_meeting.py` 等脚本所在目录）新建文本文件
`wecom_webhook.txt`，把地址完整粘贴到**第一行**，保存为 UTF-8 编码：

```
wecom_webhook.txt
├── 与 click_reserve_meeting.py、send_to_wecom.py 等脚本同级
└── 内容只有一行：完整的 Webhook 地址
```

文件内容范例：

```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

（`key=` 后面就是你的机器人密钥，粘贴时保持地址完整、不要加引号。）

### 替代方式：环境变量

不想用文件的话，也可以设置系统环境变量 `WECOM_WEBHOOK`，值为同样的
Webhook 地址。脚本读取优先级：**环境变量 > wecom_webhook.txt 文件**。

### 常见错误

| 现象 | 原因 |
| --- | --- |
| 提示「未配置企业微信机器人 Webhook」 | 文件不存在/不在脚本同目录，或环境变量未设置 |
| 企业微信返回 `errcode: 93000` | Webhook key 无效或机器人已被删除 |
| 企业微信返回 `errcode: 45009` | 触发频控（每个机器人每分钟最多 20 条） |

## 使用

```bash
python run_meeting.py        # 全流程：预约 → 填表 → 保存 → 复制 → 发群
```

分步执行：

```bash
python click_reserve_meeting.py   # 只创建会议
python fill_meeting_form.py       # 只填表并保存
python copy_meeting_info.py       # 只分享并复制会议信息
python send_to_wecom.py           # 只发送到企业微信群（内容取剪贴板）
```

各脚本均支持 `--dry-run`（只定位打印坐标，不实际点击/发送）；
`send_to_wecom.py` 另支持 `--markdown`（排版发送）与 `--text`（指定内容）。

## 实现原理

- 通过进程名定位 WPS 会议窗口（不依赖窗口标题），并支持从托盘恢复隐藏的主窗口
- 用 OpenCV 模板匹配定位「预约会议」按钮、表单「保存」按钮锚点与各输入框
- 文本输入走剪贴板 + Ctrl+V，支持中文
- Win32 API 模拟鼠标点击与键盘操作

## 注意

- 模板匹配基于 1080p 分辨率截图标定，界面缩放或版本更新后需重新截图
- `wecom_webhook.txt` 含群机器人密钥，泄露后任何人可向群里发消息，请勿提交到公开仓库
- 仅用于个人办公自动化，请遵守企业微信与 WPS 的使用条款
