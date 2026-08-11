"""
Общие утилиты для персистентного хранения истории анкет и жалоб в JSON-файлах.

Файлы лежат в папке data/ рядом с ботами. На Replit файловая система
сохраняется между запусками, пока сам Repl не пересоздаётся с нуля —
этого достаточно для истории обращений в клан.
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def data_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Повреждённый файл не должен ронять бота — начинаем с пустого состояния.
        return default


def save_json(path: str, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def format_ts(iso_ts: str) -> str:
    """Короткое читаемое представление времени для истории: 'ДД.MM ЧЧ:ММ'."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%d.%m %H:%M")
    except Exception:
        return iso_ts
