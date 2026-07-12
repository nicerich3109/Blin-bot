# -*- coding: utf-8 -*-
"""
Заявки на отпуск.

Изменения по ТЗ v1.1:
- убрано поле "Сервер" из модалки — сервер теперь однозначно определяется
  каналом, в котором нажата кнопка (Denver/Phoenix — разные каналы) — п. 2.3;
- добавлено поле "Время" — точное время окончания отпуска в добавление
  к дате, с шагом в полчаса ("0:00", "0:30", "10:00", "10:30"...) — п. 6.1;
- в сообщении в канале логов сразу есть кнопки "Принять"/"Отклонить",
  отказ теперь тоже открывает модалку с причиной — п. 5.2, 5.3;
- список "сейчас в отпуске" и снятие роли по истечении срока теперь
  проверяются раз в config.VACATION_CHECK_INTERVAL_MINUTES минут
  (см. обоснование интервала в config.py) — п. 6.2.
"""

from datetime import datetime

import discord

import config
import storage
import utils
from logger_setup import logger
from ui_decision import RequestDecisionView


class VacationModal(discord.ui.Modal, title="Заявка на отпуск"):
    discord_id_input = discord.ui.TextInput(
        label="ID дискорда", placeholder="Ваш ID или упоминание", max_length=50
    )
    until_date_input = discord.ui.TextInput(
        label="До какого числа в отпуск", placeholder="31.10.26", max_length=10
    )
    until_time_input = discord.ui.TextInput(
        label="Время окончания (шаг 30 минут)", placeholder="10:00 или 10:30", max_length=5
    )
    reason_input = discord.ui.TextInput(
        label="Причина", style=discord.TextStyle.paragraph, max_length=500
    )

    def __init__(self, server: str):
        super().__init__()
        self.server = server

    async def on_submit(self, interaction: discord.Interaction):
        until_date = utils.parse_vacation_date(str(self.until_date_input.value))
        if until_date is None:
            await interaction.response.send_message(
                "Не удалось распознать дату. Формат: 31.10.26. "
                "Нажмите на кнопку «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        until_time = utils.parse_half_hour_time(str(self.until_time_input.value))
        if until_time is None:
            await interaction.response.send_message(
                "Время должно быть кратно получасу, например 10:00 или 10:30. "
                "Нажмите на кнопку «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        target_id = utils.parse_discord_id(str(self.discord_id_input.value))

        await interaction.response.defer(ephemeral=True, thinking=True)
        until_dt = datetime.combine(until_date, until_time)
        await create_vacation_request(
            interaction, self.server, target_id, until_dt, str(self.reason_input.value)
        )


class VacationInfoView(discord.ui.View):
    def __init__(self, server: str):
        super().__init__(timeout=None)
        self.server = server
        button = discord.ui.Button(
            label="Подать заявку",
            style=discord.ButtonStyle.success,
            custom_id=f"vacation_apply_{server}",
        )
        button.callback = self.apply
        self.add_item(button)

    async def apply(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VacationModal(self.server))


async def create_vacation_request(interaction: discord.Interaction, server: str,
                                   target_id, until_dt: datetime, reason: str):
    guild = interaction.guild
    vac_id = storage.next_vacation_id(server)

    logs_channel = guild.get_channel(utils.LOGS_CHANNELS[server])

    embed = discord.Embed(title=f"Заявка на отпуск {vac_id}", color=discord.Color.orange())
    target_mention = f"<@{target_id}>" if target_id else "не распознан"
    embed.add_field(name="ID дискорда", value=target_mention, inline=False)
    embed.add_field(name="До какого числа", value=until_dt.strftime("%d.%m.%Y %H:%M"), inline=True)
    embed.add_field(name="Сервер", value=utils.SERVER_NAMES[server], inline=True)
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.set_footer(text=f"Подал: {interaction.user} ({interaction.user.id})")

    view = RequestDecisionView("vacation", vac_id)
    log_message = None
    if logs_channel:
        log_message = await logs_channel.send(embed=embed, view=view)

    storage.DATA["vacations"][vac_id] = {
        "server": server,
        "requester_id": interaction.user.id,
        "target_id": target_id,
        "until_datetime": until_dt.isoformat(),
        "reason": reason,
        "status": "pending",
        "role_removed": False,
        "log_channel_id": logs_channel.id if logs_channel else None,
        "log_message_id": log_message.id if log_message else None,
    }
    await storage.persist()

    logger.info("Создана заявка на отпуск %s от %s (цель: %s)", vac_id, interaction.user.id, target_id)

    await interaction.followup.send(
        "Ваша заявка на отпуск отправлена и ожидает рассмотрения.", ephemeral=True
    )


# ============================ СПИСОК ОТПУСКНИКОВ ===========================

async def build_vacation_embeds(guild: discord.Guild, server: str):
    info_embed = discord.Embed(
        title=f"Отпуск — {utils.SERVER_NAMES[server]}",
        description=config.VACATION_INFO_TEXT,
        color=discord.Color.blurple(),
    )

    list_embed = discord.Embed(
        title=f"Сейчас в отпуске ({utils.SERVER_NAMES[server]})",
        color=discord.Color.dark_teal(),
    )

    lines = []
    for vac in storage.DATA["vacations"].values():
        if vac.get("server") != server:
            continue
        if vac.get("status") != "accepted" or vac.get("role_removed"):
            continue
        member_id = vac.get("target_id")
        mention = f"<@{member_id}>" if member_id else "неизвестно"
        until_dt = datetime.fromisoformat(vac["until_datetime"])
        lines.append(f"• {mention} — до **{until_dt.strftime('%d.%m.%Y %H:%M')}**")

    list_embed.description = "\n".join(lines) if lines else "Сейчас никто не в отпуске."
    return [info_embed, list_embed]


async def refresh_vacation_message(guild: discord.Guild, server: str):
    channel_id = utils.VACATION_CHANNELS[server]
    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except discord.HTTPException:
            logger.error("Канал отпуска для %s (ID %s) не найден", server, channel_id)
            return
    embeds = await build_vacation_embeds(guild, server)
    await utils.ensure_persistent_message(
        channel, storage.DATA, f"vacation_info_{server}", embeds, VacationInfoView(server)
    )
    await storage.persist()


# ============================ ФОНОВАЯ ПРОВЕРКА =============================

async def check_and_expire_vacations(guild: discord.Guild):
    """
    Проверяет все принятые заявки на отпуск этого сервера (гильдии) на
    предмет истечения срока и снимает роль там, где срок прошёл.
    Возвращает множество серверов (DN/PHX), для которых список изменился
    и его стоит обновить.
    """
    now = datetime.now()
    changed_servers = set()

    for vac_id, vac in storage.DATA["vacations"].items():
        if vac["status"] != "accepted" or vac.get("role_removed"):
            continue
        try:
            until_dt = datetime.fromisoformat(vac["until_datetime"])
        except (KeyError, ValueError):
            logger.warning("Не удалось разобрать until_datetime для заявки %s", vac_id)
            continue
        if now < until_dt:
            continue

        role = guild.get_role(utils.VACATION_ROLES.get(vac["server"]))
        target = await utils.get_member_safe(guild, vac.get("target_id"))
        if target and role and role in target.roles:
            try:
                await target.remove_roles(role, reason=f"Отпуск {vac_id} закончился")
                logger.info("Роль отпуска снята с участника %s (заявка %s)", target.id, vac_id)
            except discord.Forbidden:
                logger.error(
                    "Нет прав снять роль %s с участника %s (заявка %s)", role.id, target.id, vac_id
                )
        elif target is None:
            logger.warning("Участник по заявке %s не найден при снятии роли отпуска", vac_id)

        vac["role_removed"] = True
        changed_servers.add(vac["server"])

    if changed_servers:
        await storage.persist()

    return changed_servers
