# -*- coding: utf-8 -*-
"""SQLite 缓存层，避免重复拉取数据"""
from __future__ import annotations
import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    return conn


def get(key: str, max_age_minutes: int = 30) -> dict | None:
    """获取缓存，过期返回 None"""
    conn = get_conn()
    row = conn.execute(
        "SELECT data, updated_at FROM cache WHERE key=?",
        (key,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    data, updated = json.loads(row[0]), datetime.fromisoformat(row[1])
    if datetime.now() - updated > timedelta(minutes=max_age_minutes):
        return None
    return data


def set(key: str, data):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO cache (key, data, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(data), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
