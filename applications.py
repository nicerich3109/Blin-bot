
# -*- coding: utf-8 -*-
"""
Заявки на вступление.

Изменения по ТЗ v1.1:
- вместо текстового поля "Сервер" в модалке теперь два отдельных
  персистентных кнопки в информационном сообщении: "Denver" (синяя) и
  "Phoenix" (красная) — п. 2.1;
- из модалки убраны поля "Планы после вступления" и "Откуда узнали о
  нас" — п. 2.2. Осталось три поля: никнейм, статик, OOC возраст;
- в тикет-канале сразу висят кнопки "Принять"/"Отклонить" — п. 5.2.

Изменения по ТЗ v1.2:
- в модалку добавлены поля "Ваше OOC имя" и "В каких семьях были?"
  (теперь всего 5 полей — максимум, который допускает Discord для
  одной модалки);
- добавлена проверка OOC возраста: допустимый диапазон 14-50 лет.
  Если возраст вне диапазона, заявка автоматически отклоняется ещё
  до создания тикет-канала, а заявителю (и только ему — сообщение
  ephemeral) показывается предупреждение с просьбой переотправить
  заявку с корректным возрастом;
- при принятии заявки новый ник теперь оформляется через разделители
  "|": "{ранг} |{Сервер}| {никнейм}".
"""

import re

import discord

import storage
import utils
from logger_setup import logger
from ui_decision import RequestDecisionView


class JoinModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(label="Ваш никнейм", max_length=100)
    static = discord.ui.TextInput(label="Ваш статик #", max_length=20)
    ooc_age = discord.ui.TextInput(label="Ваш OOC возраст", max_length=10)
    ooc_name = discord.ui.TextInput(label="Ваше OOC имя", max_length=100)
    previous_families = discord.ui.TextInput(
        label="В каких семьях были?",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False,
    )

    def __init__(self, server: str):
        super().__init__(title=f"Заявка на вступление — {utils.SERVER_NAMES[server]}")
        self.server = server

    async def on_submit(self, interaction: discord.Interaction):
        # П. проверки возраста ТЗ v1.2: допустимый диапазон OOC возраста —
        # 14-50 лет. Если значение не число или выходит за диапазон,
        # заявка отклоняется автоматически, тикет-канал даже не создаётся,
        # а заявителю показывается ephemeral-сообщение (видно только ему).
        age_raw = str(self.ooc_age.value).strip()
        age_digits = re.sub(r"\D", "", age_raw)
        age_value = int(age_digits) if age_digits else None

        if age_value is None or not (14 <= age_value <= 50):
            await interaction.response.send_message(
                "❌ Заявка автоматически отклонена: указан некорректный OOC "
                "возраст. Допустимый диапазон — от 14 до 50 лет. "
                "Переотправьте заявку, указав корректный возраст.",
                ephemeral=True,
            )
            logger.info(
                "Заявка на вступление от %s автоматически отклонена — "
                "некорректный OOC возраст: %r", interaction.user.id, age_raw,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        form = {
            "nickname": str(self.nickname.value),
            "static": str(self.static.value),
            "ooc_age": age_raw,
            "ooc_name": str(self.ooc_name.value),
            "previous_families": str(self.previous_families.value) or "—",
        }
        await create_join_ticket(interaction, self.server, form)


class JoinInfoView(discord.ui.View):
    """Персистентные кнопки "Denver" / "Phoenix" под информационным текстом."""

    def __init__(self):
        super().__init__(timeout=None)

        denver_btn = discord.ui.Button(
            label="Denver",
            style=discord.ButtonStyle.primary,  # синяя
            custom_id="join_apply_dn",
        )
        phoenix_btn = discord.ui.Button(
            label="Phoenix",
            style=discord.ButtonStyle.danger,  # красная
            custom_id="join_apply_phx",
        )
        denver_btn.callback = self.on_denver
        phoenix_btn.callback = self.on_phoenix
        self.add_item(denver_btn)
        self.add_item(phoenix_btn)

    async def on_denver(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JoinModal("DN"))

    async def on_phoenix(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JoinModal("PHX"))


async def create_join_ticket(interaction: discord.Interaction, server: str, form: dict):
    guild = interaction.guild
    number = storage.next_ticket_number(server)

    category = guild.get_channel(utils.TICKET_CATEGORIES[server])
    recruit_id, chief_id = utils.RECRUIT_ROLES[server]
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
        name=number, overwrites=overwrites, reason=f"Заявка на вступление {number}"
    )

    embed = discord.Embed(title=f"Заявка {number}", color=discord.Color.gold())
    embed.add_field(name="Никнейм", value=form["nickname"], inline=False)
    embed.add_field(name="Статик #", value=form["static"], inline=True)
    embed.add_field(name="OOC возраст", value=form["ooc_age"], inline=True)
    embed.add_field(name="OOC имя", value=form["ooc_name"], inline=True)
    embed.add_field(name="Сервер", value=utils.SERVER_NAMES[server], inline=True)
    embed.add_field(name="В каких семьях были", value=form["previous_families"], inline=False)
    embed.set_footer(text=f"Discord: {interaction.user} ({interaction.user.id})")

    pings = f"{interaction.user.mention}"
    if recruit_role:
        pings += f" {recruit_role.mention}"
    if chief_role:
        pings += f" {chief_role.mention}"

    view = RequestDecisionView("join", number)
    ticket_message = await channel.send(content=pings, embed=embed, view=view)

    storage.DATA["applications"][number] = {
        "server": server,
        "applicant_id": interaction.user.id,
        "channel_id": channel.id,
        "ticket_message_id": ticket_message.id,
        "status": "pending",
        **form,
    }
    await storage.persist()

    logger.info("Создана заявка на вступление %s от %s", number, interaction.user.id)

    await interaction.followup.send(
        f"Ваша заявка была отправлена, ожидайте оповещения от high staff "
        f"в канале {channel.mention}",
        ephemeral=True,
    )
