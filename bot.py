# -*- coding: utf-8 -*-
"""
Discord-бот: заявки на вступление (DN/PHX) + заявки на отпуск.

Логика:
  1. В канале заявок на вступление висит сообщение с кнопкой "Подать заявку".
     Нажатие открывает модальное окно (шаг 1/2) с полями:
     никнейм, статик, OOC возраст, планы, откуда узнали.
     После отправки открывается модальное окно (шаг 2/2) с полем "Сервер"
     (DN/PHX). После заполнения создаётся приватный тикет-канал,
     пингуются рекрутёры соответствующего сервера.
  2. Рекрутёры обрабатывают заявку слэш-командами /принял и /отклонил.
     Результат публикуется в канал логов, при одобрении заявителю
     меняется ник и выдаётся роль.
  3. В каналах отпусков висит сообщение с кнопкой "Подать заявку" и
     списком тех, кто сейчас в отпуске. Заявка — это одна модалка на
     4 поля. Результат уходит в канал логов заявок с кнопками
     Принять/Отклонить. При принятии — выдаётся роль отпуска,
     при наступлении даты окончания — роль автоматически снимается.

Все ID берутся из config.py.
"""

import asyncio
import json
import os
import re
from datetime import date, datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config

# =====================================================================
# ДАННЫЕ (простое JSON-хранилище)
# =====================================================================

_data_lock = asyncio.Lock()

DEFAULT_DATA = {
    "counters": {"DN": 0, "PHX": 0},
    "vac_counters": {"DN": 0, "PHX": 0},
    "applications": {},        # номер заявки -> dict
    "vacations": {},            # id заявки на отпуск -> dict
    "persistent_messages": {},  # ключ -> message_id
}


def load_data() -> dict:
    if not os.path.exists(config.DATA_FILE):
        return json.loads(json.dumps(DEFAULT_DATA))
    with open(config.DATA_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    for key, value in DEFAULT_DATA.items():
        data.setdefault(key, json.loads(json.dumps(value)))
    return data


def save_data(data: dict) -> None:
    tmp_path = config.DATA_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, config.DATA_FILE)


DATA = load_data()


async def persist():
    async with _data_lock:
        save_data(DATA)


# =====================================================================
# БОТ
# =====================================================================

intents = discord.Intents.default()
intents.members = True  # нужно для управления ролями/никами


class RecruitBot(commands.Bot):
    async def setup_hook(self):
        # Регистрируем персистентные view, чтобы кнопки работали и
        # после перезапуска бота.
        self.add_view(JoinInfoView())
        self.add_view(VacationInfoView("DN"))
        self.add_view(VacationInfoView("PHX"))

        # Регистрируем view для ещё не обработанных заявок на отпуск,
        # чтобы кнопки Принять/Отклонить продолжали работать.
        for vac_id, vac in DATA["vacations"].items():
            if vac.get("status") == "pending":
                self.add_view(VacationDecisionView(vac_id))

        if config.GUILD_ID:
            guild_obj = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
        else:
            await self.tree.sync()


bot = RecruitBot(command_prefix="!", intents=intents)


# =====================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================

def normalize_server(raw: str):
    """Приводит введённый текст к 'DN' или 'PHX', либо None если не распознано."""
    if not raw:
        return None
    up = raw.strip().upper()
    if "PHX" in up:
        return "PHX"
    if "DN" in up:
        return "DN"
    return None


def next_ticket_number(server: str) -> str:
    DATA["counters"][server] += 1
    return f"{server}-{DATA['counters'][server]:03d}"


def next_vacation_id(server: str) -> str:
    DATA["vac_counters"][server] += 1
    return f"{server}-VAC-{DATA['vac_counters'][server]:03d}"


def recruit_role_ids(server: str):
    if server == "DN":
        return config.DN_RECRUIT_ROLE_ID, config.DN_CHIEF_RECRUIT_ROLE_ID
    return config.PHX_RECRUIT_ROLE_ID, config.PHX_CHIEF_RECRUIT_ROLE_ID


def ticket_category_id(server: str) -> int:
    return config.DN_TICKET_CATEGORY_ID if server == "DN" else config.PHX_TICKET_CATEGORY_ID


def logs_channel_id(server: str) -> int:
    return config.DN_LOGS_CHANNEL_ID if server == "DN" else config.PHX_LOGS_CHANNEL_ID


def new_member_role_id(server: str) -> int:
    return config.DN_NEW_MEMBER_ROLE_ID if server == "DN" else config.PHX_NEW_MEMBER_ROLE_ID


def vacation_role_id(server: str) -> int:
    return config.DN_VACATION_ROLE_ID if server == "DN" else config.PHX_VACATION_ROLE_ID


def vacation_channel_id(server: str) -> int:
    return config.VACATION_DN_CHANNEL_ID if server == "DN" else config.VACATION_PHX_CHANNEL_ID


def is_recruiter(member: discord.Member, server: str) -> bool:
    if member.guild_permissions.administrator:
        return True
    recruit_id, chief_id = recruit_role_ids(server)
    member_role_ids = {r.id for r in member.roles}
    return recruit_id in member_role_ids or chief_id in member_role_ids


def is_vacation_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    member_role_ids = {r.id for r in member.roles}
    return any(rid in member_role_ids for rid in config.VACATION_STAFF_ROLE_IDS)


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


async def ensure_persistent_message(channel: discord.TextChannel, store_key: str,
                                     embeds: list, view: discord.ui.View = None):
    """
    Отправляет сообщение один раз и хранит его ID. При повторном вызове
    (например, при рестарте бота) редактирует уже существующее сообщение
    вместо создания дубликата.
    """
    stored_id = DATA["persistent_messages"].get(store_key)
    message = None

    if stored_id:
        try:
            message = await channel.fetch_message(stored_id)
        except (discord.NotFound, discord.Forbidden):
            message = None

    if message is None:
        # Ищем среди последних сообщений канала уже отправленное ботом
        async for msg in channel.history(limit=50):
            if msg.author.id == bot.user.id:
                message = msg
                break

    if message is not None:
        try:
            await message.edit(embeds=embeds, view=view)
            DATA["persistent_messages"][store_key] = message.id
            await persist()
            return message
        except (discord.NotFound, discord.Forbidden):
            message = None

    message = await channel.send(embeds=embeds, view=view)
    DATA["persistent_messages"][store_key] = message.id
    await persist()
    return message


# =====================================================================
# ВИДЖЕТ СПИСКА ОТПУСКНИКОВ + ИНФО-СООБЩЕНИЕ
# =====================================================================

async def build_vacation_embeds(guild: discord.Guild, server: str):
    info_embed = discord.Embed(
        title=f"Отпуск — {server}",
        description=config.VACATION_INFO_TEXT,
        color=discord.Color.blurple(),
    )

    list_embed = discord.Embed(
        title=f"Сейчас в отпуске ({server})",
        color=discord.Color.dark_teal(),
    )

    lines = []
    for vac_id, vac in DATA["vacations"].items():
        if vac.get("server") != server:
            continue
        if vac.get("status") != "accepted" or vac.get("role_removed"):
            continue
        member_id = vac.get("target_id")
        until = vac.get("until_date")
        mention = f"<@{member_id}>" if member_id else "неизвестно"
        lines.append(f"• {mention} — до **{until}**")

    list_embed.description = "\n".join(lines) if lines else "Сейчас никто не в отпуске."

    return [info_embed, list_embed]


async def refresh_vacation_message(guild: discord.Guild, server: str):
    channel_id = vacation_channel_id(server)
    channel = guild.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    embeds = await build_vacation_embeds(guild, server)
    await ensure_persistent_message(
        channel, f"vacation_info_{server}", embeds, VacationInfoView(server)
    )


# =====================================================================
# МОДАЛЬНЫЕ ОКНА: ЗАЯВКА НА ВСТУПЛЕНИЕ
# =====================================================================

class JoinModalPart2(discord.ui.Modal, title="Заявка на вступление (2/2)"):
    server_input = discord.ui.TextInput(
        label="Сервер",
        placeholder="DN/PHX",
        max_length=10,
    )

    def __init__(self, part1_data: dict):
        super().__init__()
        self.part1_data = part1_data

    async def on_submit(self, interaction: discord.Interaction):
        server = normalize_server(self.server_input.value)
        if server is None:
            await interaction.response.send_message(
                "Не удалось распознать сервер. Укажите DN или PHX. "
                "Нажмите на кнопку «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await create_join_ticket(interaction, server, self.part1_data)


class JoinModalPart1(discord.ui.Modal, title="Заявка на вступление (1/2)"):
    nickname = discord.ui.TextInput(label="Ваш никнейм", max_length=100)
    static = discord.ui.TextInput(label="Ваш статик #", max_length=20)
    ooc_age = discord.ui.TextInput(label="Ваш OOC возраст", max_length=10)
    plans = discord.ui.TextInput(
        label="Планы после вступления",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    source = discord.ui.TextInput(label="Откуда узнали о нас", max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        part1_data = {
            "nickname": self.nickname.value,
            "static": self.static.value,
            "ooc_age": self.ooc_age.value,
            "plans": self.plans.value,
            "source": self.source.value,
        }
        await interaction.response.send_modal(JoinModalPart2(part1_data))


async def create_join_ticket(interaction: discord.Interaction, server: str, form: dict):
    guild = interaction.guild
    number = next_ticket_number(server)

    category = guild.get_channel(ticket_category_id(server))
    recruit_id, chief_id = recruit_role_ids(server)
    recruit_role = guild.get_role(recruit_id)
    chief_role = guild.get_role(chief_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True
        ),
    }
    if recruit_role:
        overwrites[recruit_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
    if chief_role:
        overwrites[chief_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    channel = await category.create_text_channel(
        name=number, overwrites=overwrites,
        reason=f"Заявка на вступление {number}",
    )

    embed = discord.Embed(
        title=f"Заявка {number}",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Никнейм", value=form["nickname"], inline=False)
    embed.add_field(name="Статик #", value=form["static"], inline=True)
    embed.add_field(name="OOC возраст", value=form["ooc_age"], inline=True)
    embed.add_field(name="Сервер", value=server, inline=True)
    embed.add_field(name="Планы после вступления", value=form["plans"], inline=False)
    embed.add_field(name="Откуда узнали о нас", value=form["source"], inline=False)
    embed.set_footer(text=f"Discord: {interaction.user} ({interaction.user.id})")

    pings = f"{interaction.user.mention}"
    if recruit_role:
        pings += f" {recruit_role.mention}"
    if chief_role:
        pings += f" {chief_role.mention}"

    await channel.send(content=pings, embed=embed)
    await channel.send(
        "Рекрутёры могут обработать заявку командой `/принял` или `/отклонил`, "
        f"указав номер `{number}`."
    )

    DATA["applications"][number] = {
        "server": server,
        "applicant_id": interaction.user.id,
        "channel_id": channel.id,
        "status": "pending",
        **form,
    }
    await persist()

    await interaction.followup.send(
        f"Ваша заявка была отправлена, ожидайте оповещения от high staff "
        f"в канале {channel.mention}",
        ephemeral=True,
    )


class JoinInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.success,
        custom_id="join_application_button",
    )
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(JoinModalPart1())


# =====================================================================
# ОБРАБОТКА РЕШЕНИЯ ПО ЗАЯВКЕ НА ВСТУПЛЕНИЕ (/принял, /отклонил)
# =====================================================================

async def process_join_decision(interaction: discord.Interaction, number: str,
                                 accepted: bool, reason: str = None):
    number = number.strip().upper()
    app = DATA["applications"].get(number)

    if app is None:
        await interaction.response.send_message(
            f"Заявка `{number}` не найдена.", ephemeral=True
        )
        return

    if app["status"] != "pending":
        await interaction.response.send_message(
            f"Заявка `{number}` уже обработана (статус: {app['status']}).",
            ephemeral=True,
        )
        return

    server = app["server"]
    if not is_recruiter(interaction.user, server):
        await interaction.response.send_message(
            "У вас нет прав обрабатывать заявки этого сервера.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    guild = interaction.guild
    applicant = guild.get_member(app["applicant_id"])

    app["status"] = "accepted" if accepted else "declined"
    app["decided_by"] = interaction.user.id
    if reason:
        app["decline_reason"] = reason
    await persist()

    # --- Канал логов ---
    logs_channel = guild.get_channel(logs_channel_id(server))
    result_text = "✅ ПРИНЯТА" if accepted else "❌ ОТКЛОНЕНА"
    log_embed = discord.Embed(
        title=f"Заявка {number} — {result_text}",
        color=discord.Color.green() if accepted else discord.Color.red(),
    )
    log_embed.add_field(name="Никнейм", value=app["nickname"], inline=False)
    log_embed.add_field(name="Статик #", value=app["static"], inline=True)
    log_embed.add_field(name="OOC возраст", value=app["ooc_age"], inline=True)
    log_embed.add_field(name="Сервер", value=server, inline=True)
    log_embed.add_field(name="Планы после вступления", value=app["plans"], inline=False)
    log_embed.add_field(name="Откуда узнали о нас", value=app["source"], inline=False)
    log_embed.add_field(
        name="Заявитель",
        value=f"<@{app['applicant_id']}> ({app['applicant_id']})",
        inline=False,
    )
    log_embed.add_field(name="Обработал", value=interaction.user.mention, inline=True)
    if not accepted and reason:
        log_embed.add_field(name="Причина отказа", value=reason, inline=False)

    if logs_channel:
        await logs_channel.send(embed=log_embed)

    # --- Действия по заявителю ---
    if accepted and applicant:
        first_word = app["nickname"].strip().split(" ")[0] if app["nickname"].strip() else applicant.display_name
        new_nick = f"New Blin {server} {first_word}"
        try:
            await applicant.edit(nick=new_nick, reason=f"Заявка {number} одобрена")
        except discord.Forbidden:
            pass

        role = guild.get_role(new_member_role_id(server))
        if role:
            try:
                await applicant.add_roles(role, reason=f"Заявка {number} одобрена")
            except discord.Forbidden:
                pass

    # --- Тикет-канал: сообщение с итогом + закрытие для заявителя ---
    ticket_channel = guild.get_channel(app["channel_id"])
    if ticket_channel:
        try:
            if applicant:
                await ticket_channel.set_permissions(
                    applicant, view_channel=True, send_messages=False,
                    read_message_history=True,
                )
        except discord.Forbidden:
            pass

        result_embed = discord.Embed(
            title=f"Заявка {result_text}",
            color=discord.Color.green() if accepted else discord.Color.red(),
        )
        if not accepted and reason:
            result_embed.description = f"Причина: {reason}"
        await ticket_channel.send(embed=result_embed)

    await interaction.followup.send(
        f"Заявка `{number}` обработана: {result_text}.", ephemeral=True
    )


async def application_number_autocomplete(interaction: discord.Interaction, current: str):
    current = (current or "").upper()
    choices = []
    for number, app in DATA["applications"].items():
        if app["status"] == "pending" and current in number:
            choices.append(app_commands.Choice(name=number, value=number))
        if len(choices) >= 25:
            break
    return choices


@bot.tree.command(name="принял", description="Одобрить заявку на вступление")
@app_commands.describe(номер="Номер заявки, например DN-001")
@app_commands.autocomplete(номер=application_number_autocomplete)
async def cmd_accept(interaction: discord.Interaction, номер: str):
    await process_join_decision(interaction, номер, accepted=True)


@bot.tree.command(name="отклонил", description="Отклонить заявку на вступление")
@app_commands.describe(номер="Номер заявки, например DN-001", причина="Причина отказа")
@app_commands.autocomplete(номер=application_number_autocomplete)
async def cmd_decline(interaction: discord.Interaction, номер: str, причина: str):
    await process_join_decision(interaction, номер, accepted=False, reason=причина)


# =====================================================================
# МОДАЛЬНОЕ ОКНО: ЗАЯВКА НА ОТПУСК
# =====================================================================

class VacationModal(discord.ui.Modal, title="Заявка на отпуск"):
    discord_id_input = discord.ui.TextInput(
        label="ID дискорда", placeholder="Ваш ID или упоминание", max_length=50
    )
    until_date_input = discord.ui.TextInput(
        label="До какого числа в отпуск", placeholder="31.10.26", max_length=10
    )
    reason_input = discord.ui.TextInput(
        label="Причина", style=discord.TextStyle.paragraph, max_length=500
    )
    server_input = discord.ui.TextInput(
        label="Сервер", placeholder="DN/PHX", max_length=10
    )

    def __init__(self, server_channel: str):
        # server_channel — сервер, к каналу которого привязана кнопка.
        super().__init__()
        self.server_channel = server_channel

    async def on_submit(self, interaction: discord.Interaction):
        server = normalize_server(self.server_input.value) or self.server_channel

        until = parse_vacation_date(self.until_date_input.value)
        if until is None:
            await interaction.response.send_message(
                "Не удалось распознать дату. Формат: 31.10.26. "
                "Нажмите на кнопку «Подать заявку» ещё раз.",
                ephemeral=True,
            )
            return

        target_id = parse_discord_id(self.discord_id_input.value)

        await interaction.response.defer(ephemeral=True, thinking=True)
        await create_vacation_request(
            interaction, server, target_id, until, self.reason_input.value
        )


async def create_vacation_request(interaction: discord.Interaction, server: str,
                                   target_id, until: date, reason: str):
    guild = interaction.guild
    vac_id = next_vacation_id(server)

    DATA["vacations"][vac_id] = {
        "server": server,
        "requester_id": interaction.user.id,
        "target_id": target_id,
        "until_date": until.strftime("%d.%m.%Y"),
        "reason": reason,
        "status": "pending",
        "role_removed": False,
    }
    await persist()

    logs_channel = guild.get_channel(logs_channel_id(server))
    embed = discord.Embed(
        title=f"Заявка на отпуск {vac_id}",
        color=discord.Color.orange(),
    )
    target_mention = f"<@{target_id}>" if target_id else "не распознан"
    embed.add_field(name="ID дискорда", value=target_mention, inline=False)
    embed.add_field(name="До какого числа", value=until.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="Сервер", value=server, inline=True)
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.set_footer(text=f"Подал: {interaction.user} ({interaction.user.id})")

    view = VacationDecisionView(vac_id)
    if logs_channel:
        await logs_channel.send(embed=embed, view=view)
        bot.add_view(view)  # регистрируем для устойчивости к рестарту

    await interaction.followup.send(
        "Ваша заявка на отпуск отправлена и ожидает рассмотрения.",
        ephemeral=True,
    )


class VacationInfoView(discord.ui.View):
    def __init__(self, server: str):
        super().__init__(timeout=None)
        self.server = server
        button = discord.ui.Button(
            label="Подать заявку",
            style=discord.ButtonStyle.success,
            custom_id=f"vacation_application_button_{server}",
        )
        button.callback = self.apply
        self.add_item(button)

    async def apply(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VacationModal(self.server))


class VacationDecisionView(discord.ui.View):
    def __init__(self, vac_id: str):
        super().__init__(timeout=None)
        self.vac_id = vac_id

        accept_btn = discord.ui.Button(
            label="Принять", style=discord.ButtonStyle.success,
            custom_id=f"vacation_accept_{vac_id}",
        )
        decline_btn = discord.ui.Button(
            label="Отклонить", style=discord.ButtonStyle.danger,
            custom_id=f"vacation_decline_{vac_id}",
        )
        accept_btn.callback = self.on_accept
        decline_btn.callback = self.on_decline
        self.add_item(accept_btn)
        self.add_item(decline_btn)

    async def _check_and_get(self, interaction: discord.Interaction):
        vac = DATA["vacations"].get(self.vac_id)
        if vac is None:
            await interaction.response.send_message("Заявка не найдена.", ephemeral=True)
            return None
        if vac["status"] != "pending":
            await interaction.response.send_message(
                f"Заявка уже обработана (статус: {vac['status']}).", ephemeral=True
            )
            return None
        if not is_vacation_staff(interaction.user):
            await interaction.response.send_message(
                "У вас нет прав обрабатывать заявки на отпуск.", ephemeral=True
            )
            return None
        return vac

    async def on_accept(self, interaction: discord.Interaction):
        vac = await self._check_and_get(interaction)
        if vac is None:
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        vac["status"] = "accepted"
        vac["decided_by"] = interaction.user.id
        await persist()

        guild = interaction.guild
        target = guild.get_member(vac["target_id"]) if vac["target_id"] else None
        role = guild.get_role(vacation_role_id(vac["server"]))
        if target and role:
            try:
                await target.add_roles(role, reason=f"Отпуск {self.vac_id} одобрен")
            except discord.Forbidden:
                pass

        await self._finalize_message(interaction, "✅ Принята")
        await refresh_vacation_message(guild, vac["server"])
        await interaction.followup.send("Заявка на отпуск одобрена.", ephemeral=True)

    async def on_decline(self, interaction: discord.Interaction):
        vac = await self._check_and_get(interaction)
        if vac is None:
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        vac["status"] = "declined"
        vac["decided_by"] = interaction.user.id
        await persist()

        await self._finalize_message(interaction, "❌ Отклонена")
        await interaction.followup.send("Заявка на отпуск отклонена.", ephemeral=True)

    async def _finalize_message(self, interaction: discord.Interaction, result_text: str):
        for item in self.children:
            item.disabled = True
        try:
            message = interaction.message
            embed = message.embeds[0] if message.embeds else discord.Embed()
            embed.title = f"{embed.title} — {result_text}"
            await message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.Forbidden, IndexError):
            pass


# =====================================================================
# ФОНОВАЯ ЗАДАЧА: СНЯТИЕ РОЛИ ПО ОКОНЧАНИЮ ОТПУСКА
# =====================================================================

@tasks.loop(minutes=config.VACATION_CHECK_INTERVAL_MINUTES)
async def vacation_check_loop():
    today = date.today()
    changed_servers = set()

    for vac_id, vac in DATA["vacations"].items():
        if vac["status"] != "accepted" or vac.get("role_removed"):
            continue
        try:
            until = datetime.strptime(vac["until_date"], "%d.%m.%Y").date()
        except ValueError:
            continue
        if today < until:
            continue

        for guild in bot.guilds:
            target = guild.get_member(vac["target_id"]) if vac["target_id"] else None
            role = guild.get_role(vacation_role_id(vac["server"]))
            if target and role and role in target.roles:
                try:
                    await target.remove_roles(role, reason=f"Отпуск {vac_id} закончился")
                except discord.Forbidden:
                    pass
            vac["role_removed"] = True
            changed_servers.add((guild.id, vac["server"]))

    if changed_servers:
        await persist()
        for guild_id, server in changed_servers:
            guild = bot.get_guild(guild_id)
            if guild:
                await refresh_vacation_message(guild, server)


@vacation_check_loop.before_loop
async def before_vacation_check_loop():
    await bot.wait_until_ready()


# =====================================================================
# СТАРТ БОТА
# =====================================================================

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user} (ID: {bot.user.id})")

    for guild in bot.guilds:
        # --- Инфо-сообщение заявок на вступление ---
        recruit_channel = guild.get_channel(config.RECRUIT_INFO_CHANNEL_ID)
        if recruit_channel:
            embed = discord.Embed(
                title="Вступление в компанию",
                description=config.RECRUIT_INFO_TEXT,
                color=discord.Color.blurple(),
            )
            await ensure_persistent_message(
                recruit_channel, "recruit_info", [embed], JoinInfoView()
            )

        # --- Инфо-сообщения + список отпускников ---
        for server in ("DN", "PHX"):
            try:
                await refresh_vacation_message(guild, server)
            except discord.HTTPException:
                pass

    if not vacation_check_loop.is_running():
        vacation_check_loop.start()


def main():
    if not config.TOKEN or config.TOKEN == "ВСТАВЬТЕ_ТОКЕН_СЮДА":
        raise SystemExit(
            "Не задан токен бота. Установите переменную окружения DISCORD_TOKEN "
            "или впишите токен в config.py."
        )
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
