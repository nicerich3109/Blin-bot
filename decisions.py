# -*- coding: utf-8 -*-
"""Общая логика обработки решений по заявкам."""
import discord
import storage
import utils
import database
from logger_setup import logger
from notifications import send_dm_if_allowed

KIND_JOIN = "join"
KIND_VACATION = "vacation"

def find_kind(key: str, guild_id: int | None = None):
    key=(key or "").strip().upper(); app=storage.DATA["applications"].get(key)
    if app is not None and (guild_id is None or app.get("guild_id",guild_id)==guild_id): return KIND_JOIN,key
    vac=storage.DATA["vacations"].get(key)
    if vac is not None and (guild_id is None or vac.get("guild_id",guild_id)==guild_id): return KIND_VACATION,key
    return None,None

async def decide_request(guild: discord.Guild, staff_member: discord.Member, kind: str, key: str, accepted: bool, reason: str = None):
    if kind==KIND_JOIN: return await _decide_join(guild,staff_member,key,accepted,reason)
    if kind==KIND_VACATION: return await _decide_vacation(guild,staff_member,key,accepted,reason)
    return False,"Неизвестный тип заявки."

async def _decide_join(guild,staff_member,number,accepted,reason):
    app=storage.DATA["applications"].get(number)
    if app is None or app.get("guild_id",guild.id)!=guild.id: return False,f"Заявка `{number}` не найдена на этом сервере."
    if app["status"]!="pending": return False,f"Заявка `{number}` уже обработана (статус: {app['status']})."
    server=app["server"]
    if not utils.is_recruiter(staff_member,server): return False,"У вас нет прав обрабатывать заявки этого сервера."
    app["status"]="accepted" if accepted else "declined"; app["decided_by"]=staff_member.id
    if reason: app["decline_reason"]=reason
    await storage.persist(); result_label="✅ Принята" if accepted else "❌ Отклонена"; role_warning=None
    applicant=await utils.get_member_safe(guild,app["applicant_id"])
    if accepted and applicant is not None:
        first_word=app["nickname"].strip().split(" ")[0] if app["nickname"].strip() else applicant.display_name
        try: await applicant.edit(nick=f"New | {server} | {first_word}",reason=f"Заявка {number} одобрена")
        except discord.Forbidden: role_warning="не удалось изменить ник (проверьте иерархию ролей бота)"
        for role_id in (utils.NEW_MEMBER_ROLES[server],utils.JOIN_SERVER_ROLES[server]):
            role=guild.get_role(role_id) if role_id else None
            if role is None: role_warning="не удалось найти/выдать одну из ролей"; continue
            try: await applicant.add_roles(role,reason=f"Заявка {number} одобрена")
            except discord.Forbidden: role_warning="не удалось выдать одну из ролей (проверьте иерархию ролей бота)"
    if applicant is not None:
        obzvon_role_id=utils.OBZVON_ROLES.get(server); obzvon_role=guild.get_role(obzvon_role_id) if obzvon_role_id else None
        if obzvon_role and obzvon_role in applicant.roles:
            try: await applicant.remove_roles(obzvon_role,reason=f"Заявка {number} обработана")
            except discord.Forbidden: logger.warning("Не удалось снять роль обзвона с %s",applicant.id)
    logs_channel=guild.get_channel(utils.LOGS_CHANNELS[server])
    log_embed=discord.Embed(title=f"Заявка {number} — {result_label}",color=discord.Color.green() if accepted else discord.Color.red())
    log_embed.add_field(name="Никнейм",value=app["nickname"],inline=False); log_embed.add_field(name="Статик #",value=app["static"],inline=True); log_embed.add_field(name="OOC возраст",value=app["ooc_age"],inline=True); log_embed.add_field(name="Сервер",value=utils.server_name(guild.id,server),inline=True); log_embed.add_field(name="Заявитель",value=f"<@{app['applicant_id']}> ({app['applicant_id']})",inline=False); log_embed.add_field(name="Обработал",value=staff_member.mention,inline=True)
    if not accepted and reason: log_embed.add_field(name="Причина отказа",value=reason,inline=False)
    if logs_channel: await logs_channel.send(embed=log_embed)
    ticket_channel=guild.get_channel(app["channel_id"])
    if ticket_channel:
        await _finalize_ticket_message(ticket_channel,app.get("ticket_message_id"),result_label,accepted)
        result_embed=discord.Embed(title=f"Заявка {result_label}",color=discord.Color.green() if accepted else discord.Color.red())
        if not accepted and reason: result_embed.description=f"Причина: {reason}"
        await ticket_channel.send(embed=result_embed)
        if applicant is not None:
            try: await ticket_channel.set_permissions(applicant,view_channel=False,send_messages=False,read_message_history=False)
            except discord.Forbidden: logger.warning("Не удалось закрыть доступ заявителю %s",applicant.id)
        archive_category_id=utils.TICKET_ARCHIVE_CATEGORIES[server]; archive_category=guild.get_channel(archive_category_id) if archive_category_id else None
        if archive_category:
            try: await ticket_channel.edit(category=archive_category,reason=f"Заявка {number} обработана — перенос в архив")
            except discord.Forbidden: logger.error("Нет прав переместить канал заявки %s в архив",number)
    if applicant is not None and database.module_enabled(guild.id,"dm_notifications"):
        cfg=database.get_config(guild.id); template=cfg.get("application_accepted_text" if accepted else "application_declined_text") or ("Ваша заявка {server} была принята." if accepted else "Ваша заявка {server} была отклонена {by} по причине: {reason}")
        text=template.format(server=utils.server_name(guild.id,server),by=staff_member.mention,reason=reason or "не указана",user=applicant.mention)
        await send_dm_if_allowed(guild,applicant,text)
    message=f"Заявка `{number}` обработана: {result_label}."
    if role_warning: message+=f" Внимание: {role_warning}."
    return True,message

async def _finalize_ticket_message(channel,message_id,result_label,accepted):
    if not message_id:return
    try:
        msg=await channel.fetch_message(message_id); embed=msg.embeds[0] if msg.embeds else discord.Embed(); embed.title=f"{embed.title} — {result_label}"; embed.color=discord.Color.green() if accepted else discord.Color.red(); await msg.edit(embed=embed,view=None)
    except (discord.NotFound,discord.Forbidden,IndexError): logger.warning("Не удалось обновить исходное сообщение заявки в канале %s",channel.id)

async def _decide_vacation(guild,staff_member,vac_id,accepted,reason):
    vac=storage.DATA["vacations"].get(vac_id)
    if vac is None or vac.get("guild_id",guild.id)!=guild.id:return False,f"Заявка `{vac_id}` не найдена на этом сервере."
    if vac["status"]!="pending":return False,f"Заявка `{vac_id}` уже обработана (статус: {vac['status']})."
    if not utils.is_vacation_staff(staff_member):return False,"У вас нет прав обрабатывать заявки на отпуск."
    vac["status"]="accepted" if accepted else "declined"; vac["decided_by"]=staff_member.id
    if reason:vac["decline_reason"]=reason
    await storage.persist(); result_label="✅ Принята" if accepted else "❌ Отклонена"; role_warning=None
    target=await utils.get_member_safe(guild,vac.get("target_id"))
    if accepted:
        role=guild.get_role(utils.VACATION_ROLES.get(vac["server"]));
        if role and target:
            try:await target.add_roles(role,reason=f"Отпуск {vac_id} одобрен")
            except discord.Forbidden:role_warning="у бота нет прав выдать роль отпуска"
        elif not role:role_warning="роль отпуска не настроена в Dashboard"
        elif not target:role_warning="участник не найден на сервере"
    logs_channel=guild.get_channel(utils.LOGS_CHANNELS[vac["server"]]); await _finalize_vacation_log_message(guild,vac,vac_id,result_label,accepted,staff_member,reason,logs_channel)
    if accepted:
        from vacations import refresh_vacation_message,schedule_vacation_expiry
        await refresh_vacation_message(guild,vac["server"]); await schedule_vacation_expiry(guild,vac_id)
    if target is not None and database.module_enabled(guild.id,"dm_notifications"):
        cfg=database.get_config(guild.id); template=cfg.get("vacation_accepted_text" if accepted else "vacation_declined_text") or ("Ваша заявка на отпуск принята." if accepted else "Ваша заявка на отпуск отклонена {by} по причине: {reason}")
        await send_dm_if_allowed(guild,target,template.format(server=utils.server_name(guild.id,vac["server"]),by=staff_member.mention,reason=reason or "не указана",user=target.mention))
    message=f"Заявка на отпуск `{vac_id}` обработана: {result_label}."
    if role_warning:message+=f" Внимание: {role_warning}."
    return True,message

async def _finalize_vacation_log_message(guild,vac,vac_id,result_label,accepted,staff_member,reason,logs_channel):
    channel_id=vac.get("log_channel_id"); message_id=vac.get("log_message_id"); channel=guild.get_channel(channel_id) if channel_id else logs_channel
    if channel and message_id:
        try:
            msg=await channel.fetch_message(message_id); embed=msg.embeds[0] if msg.embeds else discord.Embed(); embed.title=f"{embed.title} — {result_label}"; embed.color=discord.Color.green() if accepted else discord.Color.red(); embed.add_field(name="Обработал",value=staff_member.mention,inline=True)
            if not accepted and reason:embed.add_field(name="Причина",value=reason,inline=False)
            await msg.edit(embed=embed,view=None); return
        except (discord.NotFound,discord.Forbidden,IndexError):pass
    if logs_channel:
        embed=discord.Embed(title=f"Отпуск {vac_id} — {result_label}",color=discord.Color.green() if accepted else discord.Color.red()); embed.add_field(name="Обработал",value=staff_member.mention,inline=True)
        if not accepted and reason:embed.add_field(name="Причина",value=reason,inline=False)
        await logs_channel.send(embed=embed)
