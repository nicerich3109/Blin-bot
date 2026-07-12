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
"""

import discord

import storage
import utils
from logger_setup import logger
from ui_decision import RequestDecisionView


class JoinModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(label="Ваш никнейм", max_length=100)
    static = discord.ui.TextInput(label="Ваш статик #", max_length=20)
    ooc_age = discord.ui.TextInput(label="Ваш OOC возраст", max_length=10)

    def __init__(self, server: str):
        super().__init__(title=f"Заявка на вступление — {utils.SERVER_NAMES[server]}")
        self.server = server

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        form = {
            "nickname": str(self.nickname.value),
            "static": str(self.static.value),
            "ooc_age": str(self.ooc_age.value),
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
    embed.add_field(name="Сервер", value=utils.SERVER_NAMES[server], inline=True)
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
