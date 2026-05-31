# -*- coding: utf-8 -*-
"""飞书机器人推送"""
import requests
import json
from config import FEISHU_WEBHOOK_URL


def send_feishu(text: str, title: str = None) -> bool:
    """发送飞书消息"""
    if not FEISHU_WEBHOOK_URL:
        print("[飞书] Webhook 未配置，跳过推送")
        print("=" * 50)
        print(text)
        print("=" * 50)
        return False

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title or "指数基金定投日报"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": text,
                }
            ],
        },
    }

    try:
        resp = requests.post(FEISHU_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                print("[飞书] 推送成功 ✅")
                return True
            else:
                print(f"[飞书] 推送失败: {data}")
                return False
        else:
            print(f"[飞书] HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[飞书] 异常: {e}")
        return False
