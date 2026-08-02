# -*- coding: utf-8 -*-
"""
Простое JSON-хранилище данных бота: заявки на вступление, заявки на
отпуск, счётчики номеров и ID персистентных сообщений.
"""

import asyncio
import json
import os

import config
from logger_setup import logger

_lock = asyncio.Lock()

DEFAULT_DATA = {
    "counters": {"DN": 0, "PHX": 0},
    "vac_counters": {"DN": 0, "PHX": 0},
    "applications": {},        # номер заявки ("DN-001") -> dict
    "vacations": {},            # id заявки на отпуск ("DN-VAC-001") -> dict
    "persistent_messages": {},  # ключ -> message_id
    "join_cooldowns": {},       # user_id (str) -> ISO-время последней поданной заявки
}


def _load() -> dict:
    if not os.path.exists(config.DATA_FILE):
        return json.loads(json.dumps(DEFAULT_DATA))
    with open(config.DATA_FILE, "r", encoding="utf-8") as f:
        try:
            loaded = json.load(f)
        except json.JSONDecodeError:
            logger.exception("Не удалось прочитать %s, использую пустое хранилище", config.DATA_FILE)
            loaded = {}
    for key, value in DEFAULT_DATA.items():
        loaded.setdefault(key, json.loads(json.dumps(value)))
    return loaded


def _save(data: dict) -> None:
    tmp_path = config.DATA_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, config.DATA_FILE)


DATA = _load()


async def persist() -> None:
    async with _lock:
        _save(DATA)


def next_ticket_number(server: str) -> str:
    DATA["counters"][server] += 1
    return f"{server}-{DATA['counters'][server]:03d}"


def next_vacation_id(server: str) -> str:
    DATA["vac_counters"][server] += 1
    return f"{server}-VAC-{DATA['vac_counters'][server]:03d}"
