# -*- coding: utf-8 -*-
"""
Общие вспомогательные функции: работа с ролями/каналами по серверу,
парсинг даты/времени отпуска, безопасное получение участника гильдии,
персистентные сообщения.
"""

import re
from datetime import datetime

import discord

import config
from logger_setup import logger

SERVER_NAMES = {"DN": "Denver", "PHX": "Phoenix"}

RECRUIT_ROLES = {
    "DN": (config.RECRUIT_DN, config.CHIEF_RECRUIT_DN),
    "PHX": (config.RECRUIT_PHX, config.CHIEF_RECRUIT_PHX),
}
TICKET_CATEGORIES = {"DN": config.TICKET_CATEGORY_DN, "PHX": config.TICKET_CATEGORY_PHX}
LOGS_CHANNELS = {"DN": config.LOGS_CHANNEL_DN, "PHX": config.LOGS_CHANNEL_PHX}
NEW_MEMBER_ROLES = {"DN": config.NEW_MEMBER_DN, "PHX": config.NEW_MEMBER_PHX}
VACATION_CHANNELS = {"DN": config.VACATION_CHANNEL_DN, "PHX": config.VACATION_CHANNEL_PHX}
VACATION_ROLES = {"DN": config.VACATION_ROLE_DN, "PHX": config.VACATION_ROLE_PHX}


# ------------------------------- ПАРСИНГ ---------------------------------

def parse_discord_id(raw: str):
    """Достаёт числовой ID из упоминания <@id>, <@!id> или просто из текста."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def parse_vacation_date(raw: str):
    """Парсит дату вида 31.10.26 или 31.10.2026."""
    raw = raw.strip()
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):(00|10|20|30|40|50)$")


def parse_ten_minute_time(raw: str):
    """
    Парсит время вида "0:00", "0:10", "10:00", "10:30" — часы:минуты,
    минуты обязательно кратны 10. Возвращает datetime.time или None,
    если формат неверный / минуты не кратны 10.
    """
    raw = raw.strip()
    match = _TIME_RE.match(raw)
    if not match:
        return None
    return datetime.strptime(raw, "%H:%M").time()


# --------------------------------- ПРАВА ---------------------------------

def is_recruiter(member: discord.Member, server: str) -> bool:
    if member.guild_permissions.administrator:
        return True
    recruit_id, chief_id = RECRUIT_ROLES[server]
    member_role_ids = {r.id for r in member.roles}
    return recruit_id in member_role_ids or chief_id in member_role_ids


def is_vacation_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    member_role_ids = {r.id for r in member.roles}
    return any(rid in member_role_ids for rid in config.VACATION_STAFF_ROLES)


# ------------------------------- УЧАСТНИКИ --------------------------------

async def get_member_safe(guild: discord.Guild, user_id):
    """
    Возвращает discord.Member по ID, сначала из кэша, а если там его нет —
    запрашивает через API. Раньше бот использовал только guild.get_member,
    который возвращает None, если участник не закэширован, из-за чего
    роль отпуска могла "молча" не выдаваться — это и было причиной бага
    из ТЗ (п. 4.1).
    """
    if not user_id:
        return None
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        logger.warning("Участник с ID %s не найден на сервере %s", user_id, guild.id)
        return None
    except discord.HTTPException:
        logger.exception("Ошибка при запросе участника %s на сервере %s", user_id, guild.id)
        return None


# --------------------------- ПЕРСИСТЕНТНЫЕ СООБЩЕНИЯ -----------------------

async def ensure_persistent_message(channel: discord.TextChannel, data: dict,
                                     store_key: str, embeds: list,
                                     view: discord.ui.View = None):
    """
    Отправляет сообщение один раз и хранит его ID в data. При повторном
    вызове (например, при рестарте бота) редактирует уже существующее
    сообщение вместо создания дубликата.
    """
    stored_id = data["persistent_messages"].get(store_key)
    message = None

    if stored_id:
        try:
            message = await channel.fetch_message(stored_id)
        except (discord.NotFound, discord.Forbidden):
            message = None

    if message is None:
        bot_user_id = channel.guild.me.id
        async for msg in channel.history(limit=50):
            if msg.author.id == bot_user_id:
                message = msg
                break

    if message is not None:
        try:
            await message.edit(embeds=embeds, view=view)
            data["persistent_messages"][store_key] = message.id
            return message
        except (discord.NotFound, discord.Forbidden):
            message = None

    message = await channel.send(embeds=embeds, view=view)
    data["persistent_messages"][store_key] = message.id
    return message
