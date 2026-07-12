# -*- coding: utf-8 -*-
"""
Общая логика обработки решений по заявкам — используется и кнопками
"Принять"/"Отклонить", и слэш-командами /принять, /отклонить (п. 5.1-5.2
ТЗ: команды и кнопки должны работать одинаково на оба типа заявок).

Здесь же исправлен баг из п. 4.1 (роль отпуска не выдавалась): раньше
участник искался только в кэше гильдии (guild.get_member), из-за чего
при отсутствии в кэше поиск молча проваливался. Теперь используется
utils.get_member_safe с запросом через API, а любые сбои подробно
логируются (см. logger_setup.py и bot.log).
"""

import asyncio

import discord

import config
import storage
import utils
from logger_setup import logger

KIND_JOIN = "join"
KIND_VACATION = "vacation"


def find_kind(key: str):
    """Определяет, к какому типу заявок относится ключ, и возвращает
    ('join'|'vacation', нормализованный_ключ) либо (None, None)."""
    key = (key or "").strip().upper()
    if key in storage.DATA["applications"]:
        return KIND_JOIN, key
    if key in storage.DATA["vacations"]:
        return KIND_VACATION, key
    return None, None


async def decide_request(guild: discord.Guild, staff_member: discord.Member,
                          kind: str, key: str, accepted: bool, reason: str = None):
    """
    Обрабатывает решение по заявке. Возвращает (ok: bool, message: str) —
    message предназначен для показа сотруднику, принявшему решение.
    """
    if kind == KIND_JOIN:
        return await _decide_join(guild, staff_member, key, accepted, reason)
    if kind == KIND_VACATION:
        return await _decide_vacation(guild, staff_member, key, accepted, reason)
    return False, "Неизвестный тип заявки."


# ============================== ВСТУПЛЕНИЕ ================================

async def _decide_join(guild, staff_member, number, accepted, reason):
    app = storage.DATA["applications"].get(number)
    if app is None:
        return False, f"Заявка `{number}` не найдена."
    if app["status"] != "pending":
        return False, f"Заявка `{number}` уже обработана (статус: {app['status']})."

    server = app["server"]
    if not utils.is_recruiter(staff_member, server):
        return False, "У вас нет прав обрабатывать заявки этого сервера."

    app["status"] = "accepted" if accepted else "declined"
    app["decided_by"] = staff_member.id
    if reason:
        app["decline_reason"] = reason
    await storage.persist()

    logger.info(
        "Заявка на вступление %s обработана (%s) сотрудником %s",
        number, app["status"], staff_member.id,
    )

    result_label = "✅ Принята" if accepted else "❌ Отклонена"
    role_warning = None

    applicant = await utils.get_member_safe(guild, app["applicant_id"])
    if applicant is None:
        logger.warning("Заявитель %s заявки %s не найден на сервере", app["applicant_id"], number)

    # --- Действия по заявителю при одобрении ---
    if accepted and applicant is not None:
        first_word = app["nickname"].strip().split(" ")[0] if app["nickname"].strip() else applicant.display_name
        new_nick = f"New Blin {server} {first_word}"
        try:
            await applicant.edit(nick=new_nick, reason=f"Заявка {number} одобрена")
        except discord.Forbidden:
            logger.error("Нет прав изменить ник участнику %s (заявка %s)", applicant.id, number)
            role_warning = "не удалось изменить ник (проверьте иерархию ролей бота)"

        role = guild.get_role(utils.NEW_MEMBER_ROLES[server])
        if role is None:
            logger.error("Роль нового участника для %s не найдена на сервере %s", server, guild.id)
        else:
            try:
                await applicant.add_roles(role, reason=f"Заявка {number} одобрена")
                logger.info("Роль %s выдана участнику %s (заявка %s)", role.id, applicant.id, number)
            except discord.Forbidden:
                logger.error("Нет прав выдать роль %s участнику %s (заявка %s)", role.id, applicant.id, number)
                role_warning = "не удалось выдать роль (проверьте иерархию ролей бота)"

    # --- Логи ---
    logs_channel = guild.get_channel(utils.LOGS_CHANNELS[server])
    log_embed = discord.Embed(
        title=f"Заявка {number} — {result_label}",
        color=discord.Color.green() if accepted else discord.Color.red(),
    )
    log_embed.add_field(name="Никнейм", value=app["nickname"], inline=False)
    log_embed.add_field(name="Статик #", value=app["static"], inline=True)
    log_embed.add_field(name="OOC возраст", value=app["ooc_age"], inline=True)
    log_embed.add_field(name="Сервер", value=utils.SERVER_NAMES[server], inline=True)
    log_embed.add_field(
        name="Заявитель", value=f"<@{app['applicant_id']}> ({app['applicant_id']})", inline=False
    )
    log_embed.add_field(name="Обработал", value=staff_member.mention, inline=True)
    if not accepted and reason:
        log_embed.add_field(name="Причина отказа", value=reason, inline=False)

    if logs_channel:
        await logs_channel.send(embed=log_embed)

    # --- Тикет-канал: снимаем право писать, обновляем исходное сообщение ---
    ticket_channel = guild.get_channel(app["channel_id"])
    if ticket_channel:
        if applicant is not None:
            try:
                await ticket_channel.set_permissions(
                    applicant, view_channel=True, send_messages=False, read_message_history=True
                )
            except discord.Forbidden:
                pass

        await _finalize_ticket_message(ticket_channel, app.get("ticket_message_id"), result_label, accepted)

        result_embed = discord.Embed(
            title=f"Заявка {result_label}",
            color=discord.Color.green() if accepted else discord.Color.red(),
        )
        if not accepted and reason:
            result_embed.description = f"Причина: {reason}"
        await ticket_channel.send(embed=result_embed)

        # Баг п. 1.2 ТЗ v1.1.2: раньше тикет-канал не удалялся ни при
        # принятии, ни при отклонении заявки — он оставался навсегда
        # (у заявителя просто отбиралось право писать). Теперь канал
        # автоматически удаляется через небольшую задержку.
        asyncio.create_task(_delete_ticket_channel_later(ticket_channel, number))

    message = f"Заявка `{number}` обработана: {result_label}."
    if role_warning:
        message += f" Внимание: {role_warning}. Подробности в bot.log."
    return True, message


async def _delete_ticket_channel_later(channel: discord.TextChannel, number: str):
    await asyncio.sleep(config.TICKET_DELETE_DELAY_SECONDS)
    try:
        await channel.delete(reason=f"Заявка {number} обработана — автоочистка тикет-канала")
        logger.info("Тикет-канал заявки %s удалён", number)
    except (discord.NotFound, discord.Forbidden):
        logger.warning(
            "Не удалось удалить тикет-канал заявки %s (уже удалён или нет прав)", number
        )


async def _finalize_ticket_message(channel, message_id, result_label, accepted):
    if not message_id:
        return
    try:
        msg = await channel.fetch_message(message_id)
        embed = msg.embeds[0] if msg.embeds else discord.Embed()
        embed.title = f"{embed.title} — {result_label}"
        embed.color = discord.Color.green() if accepted else discord.Color.red()
        await msg.edit(embed=embed, view=None)
    except (discord.NotFound, discord.Forbidden, IndexError):
        logger.warning("Не удалось обновить исходное сообщение заявки в канале %s", channel.id)


# ================================ ОТПУСК ==================================

async def _decide_vacation(guild, staff_member, vac_id, accepted, reason):
    vac = storage.DATA["vacations"].get(vac_id)
    if vac is None:
        return False, f"Заявка `{vac_id}` не найдена."
    if vac["status"] != "pending":
        return False, f"Заявка `{vac_id}` уже обработана (статус: {vac['status']})."

    if not utils.is_vacation_staff(staff_member):
        return False, "У вас нет прав обрабатывать заявки на отпуск."

    vac["status"] = "accepted" if accepted else "declined"
    vac["decided_by"] = staff_member.id
    if reason:
        vac["decline_reason"] = reason
    await storage.persist()

    logger.info(
        "Заявка на отпуск %s обработана (%s) сотрудником %s",
        vac_id, vac["status"], staff_member.id,
    )

    result_label = "✅ Принята" if accepted else "❌ Отклонена"
    role_warning = None

    if accepted:
        role = guild.get_role(utils.VACATION_ROLES.get(vac["server"]))
        if role is None:
            logger.error("Роль отпуска для сервера %s не найдена (guild %s)", vac["server"], guild.id)
            role_warning = "роль отпуска не найдена в config.py"
        else:
            target_id = vac.get("target_id")
            if not target_id:
                logger.warning("В заявке %s не распознан ID участника — роль не выдана", vac_id)
                role_warning = "не удалось распознать ID дискорда в заявке"
            else:
                target = await utils.get_member_safe(guild, target_id)
                if target is None:
                    logger.warning(
                        "Участник %s (заявка %s) не найден на сервере — роль не выдана",
                        target_id, vac_id,
                    )
                    role_warning = "участник не найден на сервере"
                else:
                    try:
                        await target.add_roles(role, reason=f"Отпуск {vac_id} одобрен")
                        logger.info(
                            "Роль отпуска %s выдана участнику %s (заявка %s)",
                            role.id, target.id, vac_id,
                        )
                    except discord.Forbidden:
                        logger.error(
                            "Нет прав выдать роль %s участнику %s (заявка %s) — "
                            "проверьте иерархию ролей бота",
                            role.id, target.id, vac_id,
                        )
                        role_warning = "у бота нет прав выдать роль (иерархия ролей)"

    logs_channel = guild.get_channel(utils.LOGS_CHANNELS[vac["server"]])
    await _finalize_vacation_log_message(
        guild, vac, vac_id, result_label, accepted, staff_member, reason, logs_channel
    )

    if accepted:
        from vacations import refresh_vacation_message  # локальный импорт: избегаем цикличности
        await refresh_vacation_message(guild, vac["server"])

    message = f"Заявка на отпуск `{vac_id}` обработана: {result_label}."
    if role_warning:
        message += f" Внимание: {role_warning}. Подробности в bot.log."
    return True, message


async def _finalize_vacation_log_message(guild, vac, vac_id, result_label, accepted,
                                          staff_member, reason, logs_channel):
    channel_id = vac.get("log_channel_id")
    message_id = vac.get("log_message_id")
    channel = guild.get_channel(channel_id) if channel_id else logs_channel

    if channel and message_id:
        try:
            msg = await channel.fetch_message(message_id)
            embed = msg.embeds[0] if msg.embeds else discord.Embed()
            embed.title = f"{embed.title} — {result_label}"
            embed.color = discord.Color.green() if accepted else discord.Color.red()
            embed.add_field(name="Обработал", value=staff_member.mention, inline=True)
            if not accepted and reason:
                embed.add_field(name="Причина отказа", value=reason, inline=False)
            await msg.edit(embed=embed, view=None)
            return
        except (discord.NotFound, discord.Forbidden, IndexError):
            logger.warning("Не удалось обновить исходное сообщение заявки на отпуск %s", vac_id)

    # Резервный вариант — если исходное сообщение не нашлось, публикуем новое
    if logs_channel:
        embed = discord.Embed(
            title=f"Отпуск {vac_id} — {result_label}",
            color=discord.Color.green() if accepted else discord.Color.red(),
        )
        embed.add_field(name="Обработал", value=staff_member.mention, inline=True)
        if not accepted and reason:
            embed.add_field(name="Причина отказа", value=reason, inline=False)
        await logs_channel.send(embed=embed)
