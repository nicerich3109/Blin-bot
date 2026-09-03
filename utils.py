# -*- coding: utf-8 -*-
"""Runtime Discord configuration and shared helpers."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import discord

import config
import database
from logger_setup import logger

# These are logical labels only. They are not Discord IDs. Their Discord
# objects are selected from each guild's Dashboard configuration at runtime.
SERVER_NAMES = {"DN": "Denver", "PHX": "Phoenix"}
RECRUIT_ROLES = {"DN": (), "PHX": ()}
TICKET_CATEGORIES = {"DN": None, "PHX": None}
TICKET_ARCHIVE_CATEGORIES = {"DN": None, "PHX": None}
LOGS_CHANNELS = {"DN": None, "PHX": None}
NEW_MEMBER_ROLES = {"DN": None, "PHX": None}
JOIN_SERVER_ROLES = {"DN": None, "PHX": None}
VACATION_CHANNELS = {"DN": None, "PHX": None}
VACATION_ROLES = {"DN": None, "PHX": None}
OBZVON_ROLES = {"DN": None, "PHX": None}
OBZVON_CHANNELS = {"DN": [], "PHX": []}


def guild_config(guild_id: int) -> dict:
    """Return the complete configuration for one Discord guild."""
    return database.get_config(guild_id)


def server_config(guild_id: int, server: str) -> dict:
    """Return one logical server/profile configuration for a guild."""
    return guild_config(guild_id).get("servers", {}).get(server, {})


def object_id(guild_id: int, server: str, key: str):
    """Resolve a configured Discord object ID without embedding it in code."""
    value = server_config(guild_id, server).get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def object_ids(guild_id: int, server: str, key: str) -> list[int]:
    value = server_config(guild_id, server).get(key, [])
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def refresh_runtime_config(guild_id=None):
    """Refresh compatibility mappings for legacy modules.

    New code should prefer server_config/object_id so multiple guilds cannot
    overwrite each other's runtime settings.
    """
    if guild_id is None:
        return
    raw = database.get_config(guild_id)
    for server in SERVER_NAMES:
        s = raw.get("servers", {}).get(server, {})
        RECRUIT_ROLES[server] = tuple(object_ids(guild_id, server, "recruit_roles"))
        TICKET_CATEGORIES[server] = object_id(guild_id, server, "ticket_category")
        TICKET_ARCHIVE_CATEGORIES[server] = object_id(guild_id, server, "ticket_archive_category")
        LOGS_CHANNELS[server] = object_id(guild_id, server, "logs_channel")
        NEW_MEMBER_ROLES[server] = object_id(guild_id, server, "new_member_role")
        JOIN_SERVER_ROLES[server] = object_id(guild_id, server, "join_server_role")
        VACATION_CHANNELS[server] = object_id(guild_id, server, "vacation_channel")
        VACATION_ROLES[server] = object_id(guild_id, server, "vacation_role")
        OBZVON_ROLES[server] = object_id(guild_id, server, "obzvon_role")
        OBZVON_CHANNELS[server] = object_ids(guild_id, server, "obzvon_channels")


def is_module_enabled(guild_id: int, module: str) -> bool:
    return database.module_enabled(guild_id, module)


def parse_discord_id(raw):
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    return int(digits) if digits else None


def parse_vacation_date(raw):
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    return None

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def vacation_timezone():
    return ZoneInfo(config.VACATION_TIMEZONE)


def now():
    return datetime.now(vacation_timezone())


def combine_vacation_datetime(until_date, until_time):
    return datetime.combine(until_date, until_time, tzinfo=vacation_timezone())


def parse_stored_datetime(value):
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=vacation_timezone())


def parse_ten_minute_time(raw):
    m = _TIME_RE.match(raw.strip())
    if not m or int(m.group(2)) % 10:
        return None
    return datetime.strptime(raw.strip(), "%H:%M").time()


def is_recruiter(member, server):
    if member.guild_permissions.administrator:
        return True
    return bool({r.id for r in member.roles} & set(RECRUIT_ROLES.get(server, ())))


def is_vacation_staff(member):
    if member.guild_permissions.administrator:
        return True
    allowed = database.get_config(member.guild.id).get("vacation_staff_roles", [])
    try:
        allowed = {int(x) for x in allowed}
    except (TypeError, ValueError):
        allowed = set()
    return bool({r.id for r in member.roles} & allowed)


async def get_member_safe(guild, user_id):
    if not user_id:
        return None
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def ensure_persistent_message(channel, data, store_key, embeds, view=None):
    stored_id = data.get("persistent_messages", {}).get(store_key)
    message = None
    if stored_id:
        try:
            message = await channel.fetch_message(stored_id)
        except (discord.NotFound, discord.Forbidden):
            message = None
    if message:
        try:
            await message.edit(embeds=embeds, view=view)
            data.setdefault("persistent_messages", {})[store_key] = message.id
            return message
        except (discord.NotFound, discord.Forbidden):
            message = None
    message = await channel.send(embeds=embeds, view=view)
    data.setdefault("persistent_messages", {})[store_key] = message.id
    return message
