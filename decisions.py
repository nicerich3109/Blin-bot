# -*- coding: utf-8 -*-
"""
Общая логика обработки решений по заявкам.
"""

import asyncio

import discord

import config
import storage
import utils
import consent_storage
from logger_setup import logger

KIND_JOIN = "join"
KIND_VACATION = "vacation"
KIND_CONTRACT = "contract"


def find_kind(key: str):
    key = (key or "").strip().upper()
    if key in storage.DATA["applications"]:
        return KIND_JOIN, key
    if key in storage.DATA["vacations"]:
        return KIND_VACATION, key
    return None, None


async def decide_request(guild: discord.Guild, staff_member: discord.Member,
                          kind: str, key: str, accepted: bool, reason: str = None):
    if kind == KIND_JOIN:
        return await _decide_join(guild, staff_member, key, accepted, reason)
    if kind == KIND_VACATION:
        return await _decide_vacation(guild, staff_member, key, accepted, reason)
    if kind == KIND_CONTRACT:
        return await _decide_contract(guild, staff_member, key, accepted, reason)
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
    elif consent_storage.has_consent(app["applicant_id"]):
        try:
            if accepted:
                await applicant.send(
                    f"✅ Ваша заявка {number} в {utils.SERVER_NAMES[server]} принята сотрудником {staff_member.mention}."
                )
            else:
                await applicant.send(
                    f"❌ Ваша заявка {number} в {utils.SERVER_NAMES[server]} отклонена {staff_member.mention}. "
                    f"Причина: {reason or 'не указана'}"
                )
        except discord.HTTPException:
            logger.warning("Не удалось отправить уведомление по заявке %s", number)

    # --- Действия по заявителю при одобрении ---
    if accepted and applicant is not None:
        first_word = app["nickname"].strip().split(" ")[0] if app["nickname"].strip() else applicant.display_name
        new_nick = f"New | {server} | {first_word}"
        try:
            await applicant.edit(nick=new_nick, reason=f"Заявка {number} одобрена")
        except discord.Forbidden:
            logger.error("Нет прав изменить ник участнику %s (заявка %s)", applicant.id, number)
            role_warning = "не удалось изменить ник (проверьте иерархию ролей бота)"

        # Сохраняем существующую роль нового участника и дополнительно
        # выдаём роль сервера, указанную в ТЗ.
        for role_id in (utils.NEW_MEMBER_ROLES[server], utils.JOIN_SERVER_ROLES[server]):
            role = guild.get_role(role_id)
            if role is None:
                logger.error("Роль %s для %s не найдена на сервере %s", role_id, server, guild.id)
                role_warning = "не удалось найти/выдать одну из ролей"
                continue
            try:
                await applicant.add_roles(role, reason=f"Заявка {number} одобрена")
                logger.info("Роль %s выдана участнику %s (заявка %s)", role.id, applicant.id, number)
            except discord.Forbidden:
                logger.error("Нет прав выдать роль %s участнику %s (заявка %s)", role.id, applicant.id, number)
                role_warning = "не удалось выдать одну из ролей (проверьте иерархию ролей бота)"

    # --- Снимаем роль обзвона после обработки заявки ---
    if applicant is not None:
        obzvon_role_id = utils.OBZVON_ROLES.get(server)
        obzvon_role = guild.get_role(obzvon_role_id) if obzvon_role_id else None
        if obzvon_role and obzvon_role in applicant.roles:
            try:
                await applicant.remove_roles(obzvon_role, reason=f"Заявка {number} обработана")
            except discord.Forbidden:
                logger.error(
                    "Нет прав снять роль обзвона %s с участника %s (заявка %s)",
                    obzvon_role.id, applicant.id, number,
                )

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

    # --- Тикет: публикуем результат, закрываем заявителю доступ и переносим
    # канал в архивную категорию вместо удаления. ---
    ticket_channel = guild.get_channel(app["channel_id"])
    if ticket_channel:
        await _finalize_ticket_message(ticket_channel, app.get("ticket_message_id"), result_label, accepted)

        result_embed = discord.Embed(
            title=f"Заявка {result_label}",
            color=discord.Color.green() if accepted else discord.Color.red(),
        )
        if not accepted and reason:
            result_embed.description = f"Причина: {reason}"
        await ticket_channel.send(embed=result_embed)

        if applicant is not None:
            try:
                # Явно закрываем заявителю просмотр и отправку сообщений.
                await ticket_channel.set_permissions(
                    applicant,
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False,
                )
            except discord.Forbidden:
                logger.warning("Не удалось закрыть доступ заявителю %s к заявке %s", applicant.id, number)

        archive_category_id = utils.TICKET_ARCHIVE_CATEGORIES[server]
        archive_category = guild.get_channel(archive_category_id)
        if archive_category is None:
            logger.error("Архивная категория %s для %s не найдена", archive_category_id, server)
        else:
            try:
                await ticket_channel.edit(
                    category=archive_category,
                    reason=f"Заявка {number} обработана — перенос в архив",
                )
                logger.info("Заявка %s перемещена в архивную категорию %s", number, archive_category.id)
            except discord.Forbidden:
                logger.error("Нет прав переместить канал заявки %s в архив", number)

    message = f"Заявка `{number}` обработана: {result_label}."
    if role_warning:
        message += f" Внимание: {role_warning}. Подробности в bot.log."
    return True, message


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

    target_for_dm = await utils.get_member_safe(guild, vac.get("target_id"))
    if target_for_dm is not None and consent_storage.has_consent(target_for_dm.id):
        try:
            if accepted:
                await target_for_dm.send(
                    f"✅ Ваша заявка {vac_id} на отпуск ({utils.SERVER_NAMES[vac['server']]}) принята сотрудником {staff_member.mention}."
                )
            else:
                await target_for_dm.send(
                    f"❌ Ваша заявка {vac_id} на отпуск ({utils.SERVER_NAMES[vac['server']]}) отклонена {staff_member.mention}. "
                    f"Причина: {reason or 'не указана'}"
                )
        except discord.HTTPException:
            logger.warning("Не удалось отправить уведомление по заявке на отпуск %s", vac_id)

    logs_channel = guild.get_channel(utils.LOGS_CHANNELS[vac["server"]])
    await _finalize_vacation_log_message(
        guild, vac, vac_id, result_label, accepted, staff_member, reason, logs_channel
    )

    if accepted:
        from vacations import refresh_vacation_message, schedule_vacation_expiry
        await refresh_vacation_message(guild, vac["server"])
        await schedule_vacation_expiry(guild, vac_id)

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

    if logs_channel:
        embed = discord.Embed(
            title=f"Отпуск {vac_id} — {result_label}",
            color=discord.Color.green() if accepted else discord.Color.red(),
        )
        embed.add_field(name="Обработал", value=staff_member.mention, inline=True)
        if not accepted and reason:
            embed.add_field(name="Причина отказа", value=reason, inline=False)
        await logs_channel.send(embed=embed)


# ============================== КОНТРАКТЫ ================================

async def _decide_contract(guild, staff_member, number, accepted, reason):
    item = storage.DATA["contracts"].get(number)
    if item is None:
        return False, f"Заявка {number} не найдена."
    if item.get("status") != "pending":
        return False, f"Заявка {number} уже обработана."
    server = item["server"]
    if not utils.is_recruiter(staff_member, server):
        return False, "У вас нет прав обрабатывать заявки этого сервера."
    item["status"] = "accepted" if accepted else "declined"
    item["decided_by"] = staff_member.id
    if reason:
        item["decline_reason"] = reason
    await storage.persist()
    channel = guild.get_channel(config.CONTRACT_PAYOUT_CHANNELS[server])
    if channel and item.get("message_id"):
        try:
            msg = await channel.fetch_message(item["message_id"])
            if msg.embeds:
                emb = msg.embeds[0]
                emb.title = f"{emb.title} — {'✅ Принята' if accepted else '❌ Отклонена'}"
                emb.color = discord.Color.green() if accepted else discord.Color.red()
                emb.add_field(name="Обработал", value=staff_member.mention, inline=True)
                if not accepted and reason:
                    emb.add_field(name="Причина отказа", value=reason, inline=False)
                await msg.edit(embed=emb, view=None)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.exception("Не удалось обновить заявку на выплату %s", number)
    member = await utils.get_member_safe(guild, item["requester_id"])
    if member is not None and consent_storage.has_consent(member.id):
        try:
            if accepted:
                await member.send(
                    f"✅ Ваша заявка на выплату {number} ({utils.SERVER_NAMES[server]}) "
                    f"принята сотрудником {staff_member.mention}."
                )
            else:
                await member.send(
                    f"❌ Ваша заявка на выплату {number} ({utils.SERVER_NAMES[server]}) "
                    f"отклонена {staff_member.mention}. Причина: {reason or 'не указана'}"
                )
        except discord.HTTPException:
            logger.warning("Не удалось отправить ЛС по заявке %s", number)
    return True, f"Заявка {number} обработана: {'принята' if accepted else 'отклонена'}."
