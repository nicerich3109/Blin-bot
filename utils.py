# -*- coding: utf-8 -*-
"""Runtime Discord configuration and shared helpers."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
import config
import database
from logger_setup import logger

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


def refresh_runtime_config(guild_id=None):
    if guild_id is None: return
    raw = database.get_config(guild_id)
    for server in SERVER_NAMES:
        s = raw.get("servers", {}).get(server, {})
        RECRUIT_ROLES[server] = tuple(s.get("recruit_roles", []))
        TICKET_CATEGORIES[server] = s.get("ticket_category")
        TICKET_ARCHIVE_CATEGORIES[server] = s.get("ticket_archive_category")
        LOGS_CHANNELS[server] = s.get("logs_channel")
        NEW_MEMBER_ROLES[server] = s.get("new_member_role")
        JOIN_SERVER_ROLES[server] = s.get("join_server_role")
        VACATION_CHANNELS[server] = s.get("vacation_channel")
        VACATION_ROLES[server] = s.get("vacation_role")
        OBZVON_ROLES[server] = s.get("obzvon_role")
        OBZVON_CHANNELS[server] = s.get("obzvon_channels", [])


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
    return bool({r.id for r in member.roles} & set(RECRUIT_ROLES.get(server, ())))

def is_vacation_staff(member):
    if member.guild_permissions.administrator: return True
    allowed = database.get_config(member.guild.id).get("vacation_staff_roles", [])
    return bool({r.id for r in member.roles} & set(allowed))

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
        await message.edit(embeds=embeds, view=view)
        data.setdefault("persistent_messages", {})[store_key] = message.id
        return message
    message = await channel.send(embeds=embeds, view=view)
    data.setdefault("persistent_messages", {})[store_key] = message.id
    return message
