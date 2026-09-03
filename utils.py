# -*- coding: utf-8 -*-
"""Runtime Discord configuration and shared helpers."""
import re
from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
import config
import database

# Compatibility aliases for existing configurations. New servers are named in Dashboard.
SERVER_NAMES = {"DN": "Denver", "PHX": "Phoenix"}
_current_guild_id: ContextVar[int | None] = ContextVar("blin_guild_id", default=None)


class RuntimeMap:
    def __init__(self, key: str, many: bool = False): self.key, self.many = key, many
    def _value(self, server):
        gid = _current_guild_id.get()
        if gid is None: return [] if self.many else None
        return object_ids(gid, server, self.key) if self.many else object_id(gid, server, self.key)
    def __getitem__(self, server): return self._value(server)
    def get(self, server, default=None):
        value = self._value(server)
        return default if value is None else value


RECRUIT_ROLES = RuntimeMap("recruit_roles", True)
TICKET_CATEGORIES = RuntimeMap("ticket_category")
TICKET_ARCHIVE_CATEGORIES = RuntimeMap("ticket_archive_category")
LOGS_CHANNELS = RuntimeMap("logs_channel")
NEW_MEMBER_ROLES = RuntimeMap("new_member_role")
JOIN_SERVER_ROLES = RuntimeMap("join_server_role")
VACATION_CHANNELS = RuntimeMap("vacation_channel")
VACATION_ROLES = RuntimeMap("vacation_role")
OBZVON_ROLES = RuntimeMap("obzvon_role")
OBZVON_CHANNELS = RuntimeMap("obzvon_channels", True)


def set_current_guild(guild_id): return _current_guild_id.set(guild_id)
def reset_current_guild(token): _current_guild_id.reset(token)
def guild_config(guild_id): return database.get_config(guild_id)
def server_config(guild_id, server): return database.get_server_config(guild_id, server)
def server_name(guild_id, server): return server_config(guild_id, server).get("name") or SERVER_NAMES.get(server, server)


def object_id(guild_id, server, key):
    value = server_config(guild_id, server).get(key)
    try: return int(value) if value is not None else None
    except (TypeError, ValueError): return None


def object_ids(guild_id, server, key):
    value = server_config(guild_id, server).get(key, [])
    if not isinstance(value, list): return []
    result = []
    for item in value:
        try: result.append(int(item))
        except (TypeError, ValueError): pass
    return result


def refresh_runtime_config(guild_id=None): return None
def is_module_enabled(guild_id, module): return database.module_enabled(guild_id, module)
def parse_discord_id(raw):
    if not raw: return None
    digits = re.sub(r"\D", "", raw)
    return int(digits) if digits else None


def parse_vacation_date(raw):
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try: return datetime.strptime(raw.strip(), fmt).date()
        except ValueError: pass
    return None

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
def vacation_timezone(): return ZoneInfo(config.VACATION_TIMEZONE)
def now(): return datetime.now(vacation_timezone())
def combine_vacation_datetime(until_date, until_time): return datetime.combine(until_date, until_time, tzinfo=vacation_timezone())
def parse_stored_datetime(value):
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=vacation_timezone())
def parse_ten_minute_time(raw):
    m = _TIME_RE.match(raw.strip())
    if not m or int(m.group(2)) % 10: return None
    return datetime.strptime(raw.strip(), "%H:%M").time()


def is_recruiter(member, server):
    if member.guild_permissions.administrator: return True
    allowed = object_ids(member.guild.id, server, "recruit_roles")
    return bool({r.id for r in member.roles} & set(allowed))


def is_vacation_staff(member):
    if member.guild_permissions.administrator: return True
    allowed = database.get_config(member.guild.id).get("vacation_staff_roles", [])
    try: allowed = {int(x) for x in allowed}
    except (TypeError, ValueError): allowed = set()
    return bool({r.id for r in member.roles} & allowed)


async def get_member_safe(guild, user_id):
    if not user_id: return None
    member = guild.get_member(user_id)
    if member: return member
    try: return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException): return None


async def ensure_persistent_message(channel, data, store_key, embeds, view=None):
    stored_id = data.get("persistent_messages", {}).get(store_key)
    message = None
    if stored_id:
        try: message = await channel.fetch_message(stored_id)
        except (discord.NotFound, discord.Forbidden): pass
    if message:
        try:
            await message.edit(embeds=embeds, view=view)
            data.setdefault("persistent_messages", {})[store_key] = message.id
            return message
        except (discord.NotFound, discord.Forbidden): pass
    message = await channel.send(embeds=embeds, view=view)
    data.setdefault("persistent_messages", {})[store_key] = message.id
    return message
