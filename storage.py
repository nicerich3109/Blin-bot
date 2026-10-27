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

# На PHX было создано 170 заявок до переименования сервера в ST.
# Не позволяем счётчику заявок ST опуститься ниже этого значения.
ST_LEGACY_APPLICATIONS = 170

DEFAULT_DATA = {
    "counters": {"CM": 0, "ST": 0},
    "vac_counters": {"CM": 0, "ST": 0},
    "applications": {},        # номер заявки ("CM-001") -> dict
    "vacations": {},            # id заявки на отпуск ("CM-VAC-001") -> dict
    "persistent_messages": {},  # ключ -> message_id
    "join_cooldowns": {},       # user_id (str) -> ISO-время последней поданной заявки
    "contracts": {},           # номер заявки на выплату -> dict
}


def _migrate_server_labels(data: dict) -> dict:
    """Переносит сохранённые серверные коды DN/PHX на CM/ST без потери заявок."""
    labels = {"DN": "CM", "PHX": "ST"}
    for counter_name in ("counters", "vac_counters"):
        counters = data.setdefault(counter_name, {})
        for old, new in labels.items():
            if old in counters:
                counters[new] = max(int(counters.get(new, 0)), int(counters.pop(old, 0)))

    # Даже если старый счётчик PHX потерян, не начинаем нумерацию ST с 001.
    counters = data.setdefault("counters", {})
    counters["ST"] = max(int(counters.get("ST", 0)), ST_LEGACY_APPLICATIONS)

    for section in ("applications", "vacations", "contracts"):
        for item in data.setdefault(section, {}).values():
            if item.get("server") in labels:
                item["server"] = labels[item["server"]]
    persistent = data.setdefault("persistent_messages", {})
    for old, new in labels.items():
        for key in list(persistent):
            if f"_{old}" in key:
                value = persistent.pop(key)
                persistent[key.replace(f"_{old}", f"_{new}")] = value
    return data


def _load() -> dict:
    if not os.path.exists(config.DATA_FILE):
        loaded = json.loads(json.dumps(DEFAULT_DATA))
    else:
        with open(config.DATA_FILE, "r", encoding="utf-8") as f:
            try:
                loaded = json.load(f)
            except json.JSONDecodeError:
                logger.exception("Не удалось прочитать %s, использую пустое хранилище", config.DATA_FILE)
                loaded = {}
    for key, value in DEFAULT_DATA.items():
        loaded.setdefault(key, json.loads(json.dumps(value)))
    return _migrate_server_labels(loaded)

def _save(data: dict) -> None:
    data_dir = os.path.dirname(config.DATA_FILE)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
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


def next_contract_id(server: str) -> str:
    DATA["counters"].setdefault("CONTRACT", 0)
    DATA["counters"]["CONTRACT"] += 1
    return f"{server}-CON-{DATA['counters']['CONTRACT']:03d}"
