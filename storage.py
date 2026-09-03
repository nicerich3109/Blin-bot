# -*- coding: utf-8 -*-
"""Compatibility state facade backed by SQLite.

Existing modules can keep using ``storage.DATA`` in memory, while SQLite is
now the persistent source of truth. A legacy data.json is imported only when
no database state exists, so existing installations can migrate safely.
"""
import asyncio
import copy
import json
import os

import config
import database
from logger_setup import logger

_lock = asyncio.Lock()
DEFAULT_DATA = {
    "counters": {},
    "vac_counters": {},
    "applications": {},
    "vacations": {},
    "persistent_messages": {},
    "join_cooldowns": {},
}


def _legacy_load():
    if not os.path.exists(config.DATA_FILE):
        return None
    try:
        with open(config.DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.exception("Не удалось прочитать legacy storage %s", config.DATA_FILE)
        return None


def _load():
    database.init_db()
    data = database.load_state("storage")
    if data is None:
        data = _legacy_load() or copy.deepcopy(DEFAULT_DATA)
        database.save_state("storage", data)
    for key, value in DEFAULT_DATA.items():
        data.setdefault(key, copy.deepcopy(value))
    return data


DATA = _load()


async def persist() -> None:
    async with _lock:
        database.save_state("storage", DATA)


def next_ticket_number(server: str) -> str:
    counters = DATA.setdefault("counters", {})
    counters[server] = int(counters.get(server, 0)) + 1
    return f"{server}-{counters[server]:03d}"


def next_vacation_id(server: str) -> str:
    counters = DATA.setdefault("vac_counters", {})
    counters[server] = int(counters.get(server, 0)) + 1
    return f"{server}-VAC-{counters[server]:03d}"
