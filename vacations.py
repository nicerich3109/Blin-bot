# -*- coding: utf-8 -*-
"""
Заявки на отпуск.

Изменения по ТЗ v1.1:
- убрано поле "Сервер" из модалки — сервер теперь однозначно определяется
  каналом, в котором нажата кнопка (Denver/Phoenix — разные каналы) — п. 2.3;
- добавлено поле "Время" — точное время окончания отпуска в добавление
  к дате, с шагом в 10 минут ("0:00", "0:10", "10:00", "10:30"...) — п. 6.1;
- в сообщении в канале логов сразу есть кнопки "Принять"/"Отклонить",
  отказ теперь тоже открывает модалку с причиной — п. 5.2, 5.3;
- список "сейчас в отпуске" и снятие роли по истечении срока
  обрабатываются таймером на момент окончания (после одобрения заявки
  и при перезапуске бота) плюс проверка при старте — п. 6.2.

Изменения по ТЗ v1.1.2:
- бага п. 1.3: участник, покинувший сервер до окончания отпуска, больше
  не "зависает" в списке "сейчас в отпуске" до изначально указанной
  даты — запись закрывается сразу, как только участника не стало на
  сервере (см. check_and_expire_vacations);
- п. 2.1: перед созданием заявки проверяется, что "тегнутый" в модалке
  участник существует и правда состоит на сервере;
- п. 2.2: добавлена принудительная отправка домой раньше срока —
  force_remove_vacation(), используется командой /вынесение_из_отпуска
  из commands.py.
"""

from datetime import datetime
import asyncio

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
        label="Время окончания (шаг 10 минут)", placeholder="10:00 или 10:10", max_length=5
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

        until_time = utils.parse_ten_minute_time(str(self.until_time_input.value))
        if until_time is None:
            await interaction.response.send_message(
                "Время должно быть кратно 10 минутам, например 10:00 или 10:10. "
                "Нажмите на кнопку «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        target_id = utils.parse_discord_id(str(self.discord_id_input.value))
        if target_id is None:
            await interaction.response.send_message(
                "Не удалось распознать ID/упоминание участника. Укажите ID или "
                "@упоминание. Нажмите на кнопку «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        # П. 2.1 ТЗ v1.1.2: раньше ID/упоминание никак не проверялось, из-за
        # чего можно было "тегнуть" человека, которого нет на сервере, или
        # вовсе несуществующий ID. Теперь участник ищется на сервере, и без
        # найденного участника заявка не создаётся.
        target_member = await utils.get_member_safe(interaction.guild, target_id)
        if target_member is None:
            await interaction.response.send_message(
                "Указанный участник не найден на этом сервере. Нельзя оформить "
                "отпуск на человека, которого нет на сервере, или на несуществующий "
                "ID. Проверьте ID/упоминание и нажмите «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        until_dt = utils.combine_vacation_datetime(until_date, until_time)
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
        until_dt = utils.parse_stored_datetime(vac["until_datetime"])
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


# ============================ ПЛАНИРОВЩИК ОКОНЧАНИЯ ======================

_scheduled_expiry_tasks: dict[str, asyncio.Task] = {}


def cancel_vacation_expiry(vac_id: str) -> None:
    """Отменяет запланированное автоматическое окончание отпуска."""
    task = _scheduled_expiry_tasks.pop(vac_id, None)
    if task and not task.done():
        task.cancel()


async def _expire_vacation_record(guild: discord.Guild, vac_id: str, vac: dict) -> bool:
    """
    Закрывает одну активную заявку на отпуск: снимает роль (если участник
    ещё на сервере) и помечает role_removed. Возвращает True, если запись
    была изменена.
    """
    if vac.get("status") != "accepted" or vac.get("role_removed"):
        return False

    target_id = vac.get("target_id")
    target = await utils.get_member_safe(guild, target_id)
    left_server = bool(target_id) and target is None

    role = guild.get_role(utils.VACATION_ROLES.get(vac["server"]))
    if target and role and role in target.roles:
        try:
            await target.remove_roles(role, reason=f"Отпуск {vac_id} закончился")
            logger.info("Роль отпуска снята с участника %s (заявка %s)", target.id, vac_id)
        except discord.Forbidden:
            logger.error(
                "Нет прав снять роль %s с участника %s (заявка %s)", role.id, target.id, vac_id
            )
    elif left_server:
        logger.info(
            "Участник %s покинул сервер во время отпуска (заявка %s) — запись закрыта",
            target_id, vac_id,
        )
    elif target is None:
        logger.warning("Участник по заявке %s не найден при снятии роли отпуска", vac_id)

    vac["role_removed"] = True
    return True


async def schedule_vacation_expiry(guild: discord.Guild, vac_id: str) -> None:
    """
    Планирует автоматическое окончание отпуска ровно на until_datetime.
    Если срок уже прошёл — закрывает заявку сразу.
    """
    vac = storage.DATA["vacations"].get(vac_id)
    if vac is None or vac.get("status") != "accepted" or vac.get("role_removed"):
        return

    try:
        until_dt = utils.parse_stored_datetime(vac["until_datetime"])
    except (KeyError, ValueError):
        logger.warning("Не удалось разобрать until_datetime для заявки %s — таймер не запущен", vac_id)
        return

    cancel_vacation_expiry(vac_id)

    now = utils.now()
    if now >= until_dt:
        logger.info(
            "Отпуск %s уже истёк (до %s, сейчас %s) — закрываю сразу",
            vac_id, until_dt.strftime("%d.%m.%Y %H:%M"), now.strftime("%d.%m.%Y %H:%M"),
        )
        if await _expire_vacation_record(guild, vac_id, vac):
            await storage.persist()
            await refresh_vacation_message(guild, vac["server"])
        return

    delay = (until_dt - now).total_seconds()
    logger.info(
        "Запланировано окончание отпуска %s через %.0f сек (в %s %s)",
        vac_id, delay, until_dt.strftime("%d.%m.%Y %H:%M"), config.VACATION_TIMEZONE,
    )

    async def _wait_and_expire():
        try:
            await asyncio.sleep(delay)
            current = storage.DATA["vacations"].get(vac_id)
            if current is None or current.get("role_removed"):
                return
            if await _expire_vacation_record(guild, vac_id, current):
                await storage.persist()
                await refresh_vacation_message(guild, current["server"])
                logger.info("Отпуск %s автоматически закрыт по таймеру", vac_id)
        except asyncio.CancelledError:
            logger.debug("Таймер окончания отпуска %s отменён", vac_id)
        finally:
            _scheduled_expiry_tasks.pop(vac_id, None)

    _scheduled_expiry_tasks[vac_id] = asyncio.create_task(_wait_and_expire())


async def restore_vacation_schedules(guild: discord.Guild) -> None:
    """Восстанавливает таймеры для всех активных отпусков после перезапуска бота."""
    for vac_id, vac in storage.DATA["vacations"].items():
        if vac.get("status") == "accepted" and not vac.get("role_removed"):
            await schedule_vacation_expiry(guild, vac_id)


# ============================ ПРОВЕРКА ПРИ СТАРТЕ ==========================

async def check_and_expire_vacations(guild: discord.Guild):
    """
    Проверяет все принятые заявки на отпуск этого сервера (гильдии) на
    предмет истечения срока и снимает роль там, где срок прошёл.
    Вызывается при запуске бота; для активных отпусков дальше работает
    schedule_vacation_expiry().
    Возвращает множество серверов (DN/PHX), для которых список изменился.

    Баг п. 1.3 ТЗ v1.1.2: раньше запись закрывалась только по истечении
    указанной даты/времени. Если участник покидал сервер до окончания
    отпуска, его запись не закрывалась (условие "now < until_dt" всегда
    было верным до наступления даты) и человек мог "зависать" в списке
    "сейчас в отпуске" вплоть до изначально указанной даты. Теперь запись
    закрывается сразу же, как только выяснилось, что участника больше
    нет на сервере — не дожидаясь даты.
    """
    now = utils.now()
    changed_servers = set()

    for vac_id, vac in storage.DATA["vacations"].items():
        if vac["status"] != "accepted" or vac.get("role_removed"):
            continue

        target_id = vac.get("target_id")
        target = await utils.get_member_safe(guild, target_id)
        left_server = bool(target_id) and target is None

        until_dt = None
        try:
            until_dt = utils.parse_stored_datetime(vac["until_datetime"])
        except (KeyError, ValueError):
            logger.warning("Не удалось разобрать until_datetime для заявки %s", vac_id)

        expired = until_dt is not None and now >= until_dt
        if not left_server and not expired:
            continue

        if await _expire_vacation_record(guild, vac_id, vac):
            changed_servers.add(vac["server"])

    if changed_servers:
        await storage.persist()

    return changed_servers


# ============================ ПРИНУДИТЕЛЬНЫЙ ВЫНОС =========================

async def force_remove_vacation(guild: discord.Guild, staff_member: discord.Member,
                                 target: discord.Member, reason: str):
    """
    П. 2.2 ТЗ v1.1.2: принудительно выносит участника из отпуска раньше
    срока (например, человек вернулся раньше или отпуск закончили по
    другой причине) — используется командой /вынесение_из_отпуска.

    Находит активную (принятую и ещё не закрытую) заявку на отпуск этого
    участника, снимает роль отпуска, закрывает заявку и публикует в
    канал логов сообщение о том, кто кого вынес и по какой причине.
    Возвращает (ok: bool, message: str) для показа тому, кто выполнил
    команду.
    """
    if not utils.is_vacation_staff(staff_member):
        return False, "У вас нет прав снимать людей с отпуска."

    active_vac = None
    active_id = None
    for vac_id, vac in storage.DATA["vacations"].items():
        if (vac.get("target_id") == target.id and vac.get("status") == "accepted"
                and not vac.get("role_removed")):
            active_vac = vac
            active_id = vac_id
            break

    if active_vac is None:
        return False, f"{target.mention} сейчас не числится в отпуске."

    server = active_vac["server"]
    role = guild.get_role(utils.VACATION_ROLES.get(server))
    if role and role in target.roles:
        try:
            await target.remove_roles(role, reason=f"Принудительный вынос из отпуска: {reason}")
        except discord.Forbidden:
            logger.error(
                "Нет прав снять роль %s с участника %s при принудительном выносе "
                "из отпуска (заявка %s)", role.id, target.id, active_id,
            )
            return False, "Не удалось снять роль отпуска — проверьте иерархию ролей бота."

    active_vac["role_removed"] = True
    active_vac["force_removed_by"] = staff_member.id
    active_vac["force_removed_reason"] = reason
    cancel_vacation_expiry(active_id)
    await storage.persist()

    logger.info(
        "Принудительный вынос из отпуска: заявка %s, участник %s, вынес %s, причина: %s",
        active_id, target.id, staff_member.id, reason,
    )

    logs_channel = guild.get_channel(utils.LOGS_CHANNELS[server])
    if logs_channel:
        embed = discord.Embed(
            title=f"Принудительный вынос из отпуска — {active_id}",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Кого вынесли", value=target.mention, inline=True)
        embed.add_field(name="Кто вынес", value=staff_member.mention, inline=True)
        embed.add_field(name="Причина", value=reason, inline=False)
        await logs_channel.send(embed=embed)

    await refresh_vacation_message(guild, server)

    return True, f"{target.mention} принудительно вынесен из отпуска (заявка `{active_id}`)."
