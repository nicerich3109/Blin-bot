# -*- coding: utf-8 -*-
"""Восстановление заявок на вступление из каналов логов."""

import re

import discord

import config
import storage
from logger_setup import logger


CHANNELS = {
    "ST": config.LOGS_CHANNEL_ST,
    "CM": config.LOGS_CHANNEL_CM,
}
NUMBER_RE = re.compile(r"\b(ST|CM)-(\d+)\b", re.IGNORECASE)
USER_ID_RE = re.compile(r"(?:<@!?|\()?(\d{15,22})")


def _field_map(embed: discord.Embed) -> dict:
    return {
        str(field.name).strip().casefold(): str(field.value).strip()
        for field in embed.fields
    }


def _extract_id(value: str):
    match = USER_ID_RE.search(value or "")
    return int(match.group(1)) if match else None


def _parse_log_message(message: discord.Message, server: str):
    for embed in message.embeds:
        title = embed.title or ""
        match = NUMBER_RE.search(title)
        if not match or match.group(1).upper() != server:
            continue

        title_lower = title.casefold()
        if "принята" in title_lower:
            status = "accepted"
        elif "отклонена" in title_lower:
            status = "declined"
        else:
            # В каналах логов находятся именно записи об обработанных заявках.
            continue

        fields = _field_map(embed)
        applicant_id = _extract_id(fields.get("заявитель", ""))
        if applicant_id is None:
            # Совместимость со старым форматом, где ID мог быть в описании/футере.
            applicant_id = _extract_id(embed.footer.text or "")
        if applicant_id is None:
            return None

        nickname = fields.get("никнейм")
        static = fields.get("статик #")
        age = fields.get("ooc возраст")
        if not nickname or not static or not age:
            return None

        staff_id = _extract_id(fields.get("обработал", ""))
        return match.group(0).upper(), {
            "server": server,
            "applicant_id": applicant_id,
            "channel_id": None,
            "ticket_message_id": None,
            "status": status,
            "nickname": nickname,
            "static": static,
            "ooc_age": age,
            "ooc_name": fields.get("ooc имя", "—"),
            "previous_families": fields.get("в каких семьях были", "—"),
            "decided_by": staff_id,
            "restored_from_log": True,
            "log_channel_id": message.channel.id,
            "log_message_id": message.id,
            "created_at": message.created_at.isoformat(),
        }

    return None


async def restore_from_logs(bot: discord.Client):
    """Добавляет в DATA только те заявки, которых там ещё нет."""
    added = {"ST": 0, "CM": 0}
    skipped_existing = {"ST": 0, "CM": 0}
    skipped_unreadable = {"ST": 0, "CM": 0}

    for server, channel_id in CHANNELS.items():
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.exception("Не удалось получить канал логов %s (%s)", server, channel_id)
                raise RuntimeError(
                    f"Не удалось открыть канал логов {server} (ID {channel_id}). "
                    "Проверьте доступ бота и права на просмотр истории."
                )

        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError(f"Канал логов {server} не является текстовым каналом.")

        async for message in channel.history(limit=None, oldest_first=True):
            parsed = _parse_log_message(message, server)
            if parsed is None:
                continue

            number, record = parsed
            if number in storage.DATA["applications"]:
                skipped_existing[server] += 1
                continue

            storage.DATA["applications"][number] = record
            added[server] += 1

    if sum(added.values()):
        await storage.persist()

    logger.info(
        "Восстановление заявок завершено. Добавлено: ST=%s, CM=%s; уже были: ST=%s, CM=%s",
        added["ST"], added["CM"], skipped_existing["ST"], skipped_existing["CM"],
    )
    return added, skipped_existing, skipped_unreadable
