# -*- coding: utf-8 -*-
"""Сбор сведений о ролях Discord в постоянный файл data/roles.json."""

import json
import os
from datetime import datetime, timezone

from logger_setup import logger

ROLES_FILE = os.getenv("BLIN_ROLES_FILE", "/app/data/roles.json")


def collect_roles(guilds):
    roles = []
    for guild in guilds:
        for role in guild.roles:
            if role.is_default():
                continue
            roles.append({
                "guild_id": guild.id,
                "role_id": role.id,
                "name": role.name,
                "admin": bool(role.permissions.administrator),
            })
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "roles": roles,
    }


def save_roles(guilds):
    data = collect_roles(guilds)
    directory = os.path.dirname(ROLES_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = ROLES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ROLES_FILE)
    logger.info("Сведения о ролях сохранены: %s ролей -> %s", len(data["roles"]), ROLES_FILE)
