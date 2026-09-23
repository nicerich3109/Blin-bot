# -*- coding: utf-8 -*-
"""
Слэш-команды /принять, /отклонить и /вынесение_из_отпуска.

По ТЗ v1.1 (п. 5.1) команды /принять и /отклонить должны работать
одинаково и для заявок на вступление, и для заявок на отпуск — тип
заявки определяется автоматически по номеру (find_kind), а вся логика
решения общая (decisions.decide_request), как и у кнопок в
ui_decision.py.

П. 2.2 ТЗ v1.1.2: /вынесение_из_отпуска принудительно выносит участника
из отпуска раньше срока (сама логика — в vacations.force_remove_vacation).
Параметр "участник" имеет тип discord.Member, поэтому Discord сам не даёт
выбрать несуществующего человека или того, кого нет на сервере (п. 2.1).
"""

import discord
from discord import app_commands
from discord.ext import commands

import decisions
import storage
import consent_storage
from consent_view import CONSENT_TEXT, StandaloneConsentView
import vacations
import discipline
import config
import utils


async def _autocomplete_number(interaction: discord.Interaction, current: str):
    current = (current or "").upper()
    choices = []

    for number, app in storage.DATA["applications"].items():
        if app["status"] == "pending" and current in number:
            choices.append(app_commands.Choice(name=f"{number} (вступление)", value=number))

    for vac_id, vac in storage.DATA["vacations"].items():
        if vac["status"] == "pending" and current in vac_id:
            choices.append(app_commands.Choice(name=f"{vac_id} (отпуск)", value=vac_id))
    for contract_id, item in storage.DATA["contracts"].items():
        if item["status"] == "pending" and current in contract_id:
            choices.append(app_commands.Choice(name=f"{contract_id} (выплата)", value=contract_id))

    return choices[:25]


def register_commands(bot: commands.Bot):
    @bot.tree.command(name="опубликовать_согласие", description="Опубликовать сообщение с согласием на уведомления")
    @app_commands.default_permissions(administrator=True)
    async def cmd_publish_consent(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("У вас нет прав администратора.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Согласие на системные уведомления Blin",
            description=CONSENT_TEXT,
            color=discord.Color.blurple(),
        )
        await interaction.channel.send(embed=embed, view=StandaloneConsentView())
        await interaction.response.send_message(
            "✅ Сообщение с согласием опубликовано в этом канале.",
            ephemeral=True,
        )

    @bot.tree.command(name="информация_о_человеке", description="Показать сохранённую информацию по заявкам пользователя")
    @app_commands.describe(участник="Пользователь, информацию о котором нужно показать")
    async def cmd_person_info(interaction: discord.Interaction, участник: discord.Member):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not consent_storage.has_consent(interaction.user.id):
            await interaction.response.send_message(
                "❌ Сначала дайте согласие на системные уведомления бота. После этого функции бота станут доступны.",
                ephemeral=True,
            )
            return

        applications = [
            (number, app) for number, app in storage.DATA["applications"].items()
            if int(app.get("applicant_id", 0)) == участник.id
        ]
        if not applications:
            await interaction.response.send_message(
                f"❌ Сохранённых заявок пользователя {участник.mention} не найдено.",
                ephemeral=True,
            )
            return

        allowed = []
        for number, app in applications:
            server = app.get("server")
            if interaction.user.guild_permissions.administrator or (
                server in utils.SERVER_NAMES and utils.is_recruiter(interaction.user, server)
            ):
                allowed.append((number, app))

        if not allowed:
            await interaction.response.send_message(
                "❌ У вас нет прав просматривать заявки этого пользователя.",
                ephemeral=True,
            )
            return

        embeds = []
        for number, app in allowed[-10:]:
            server = app.get("server", "—")
            embed = discord.Embed(title=f"Заявка {number}", color=discord.Color.gold())
            embed.add_field(name="Никнейм", value=str(app.get("nickname", "—")), inline=False)
            embed.add_field(name="Статик #", value=str(app.get("static", "—")), inline=True)
            embed.add_field(name="OOC возраст", value=str(app.get("ooc_age", "—")), inline=True)
            embed.add_field(name="OOC имя", value=str(app.get("ooc_name", "—")), inline=True)
            embed.add_field(name="Сервер", value=utils.SERVER_NAMES.get(server, server), inline=True)
            embed.add_field(name="В каких семьях были", value=str(app.get("previous_families", "—")), inline=False)
            embed.set_footer(text=f"Discord: {участник} ({участник.id})")
            embeds.append(embed)

        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    @bot.tree.command(name="принять", description="Принять заявку (на вступление или отпуск)")
    @app_commands.describe(номер="Номер заявки, например DN-001 или DN-VAC-001")
    @app_commands.autocomplete(номер=_autocomplete_number)
    async def cmd_accept(interaction: discord.Interaction, номер: str):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not consent_storage.has_consent(interaction.user.id):
            await interaction.response.send_message("❌ Сначала дайте согласие на системные уведомления бота. После этого функции бота станут доступны.", ephemeral=True)
            return
        kind, key = decisions.find_kind(номер)
        if kind is None:
            await interaction.response.send_message(f"Заявка `{номер}` не найдена.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await decisions.decide_request(interaction.guild, interaction.user, kind, key, True)
        await interaction.followup.send(message, ephemeral=True)

    @bot.tree.command(name="отклонить", description="Отклонить заявку (на вступление или отпуск)")
    @app_commands.describe(номер="Номер заявки, например DN-001 или DN-VAC-001", причина="Причина отказа")
    @app_commands.autocomplete(номер=_autocomplete_number)
    async def cmd_decline(interaction: discord.Interaction, номер: str, причина: str):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not consent_storage.has_consent(interaction.user.id):
            await interaction.response.send_message("❌ Сначала дайте согласие на системные уведомления бота. После этого функции бота станут доступны.", ephemeral=True)
            return
        kind, key = decisions.find_kind(номер)
        if kind is None:
            await interaction.response.send_message(f"Заявка `{номер}` не найдена.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await decisions.decide_request(
            interaction.guild, interaction.user, kind, key, False, reason=причина
        )
        await interaction.followup.send(message, ephemeral=True)

    @bot.tree.command(
        name="вынесение_из_отпуска",
        description="Принудительно вынести участника из отпуска раньше срока",
    )
    @app_commands.describe(
        участник="Кого вынести из отпуска (тег/выбор участника сервера)",
        причина="Причина принудительного выноса",
    )
    async def cmd_force_remove_vacation(
        interaction: discord.Interaction, участник: discord.Member, причина: str
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not consent_storage.has_consent(interaction.user.id):
            await interaction.response.send_message("❌ Сначала дайте согласие на системные уведомления бота. После этого функции бота станут доступны.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await vacations.force_remove_vacation(
            interaction.guild, interaction.user, участник, причина
        )
        await interaction.followup.send(message, ephemeral=True)


    @bot.tree.command(name="выдать_выговор", description="Выдать дисциплинарное взыскание")
    @app_commands.describe(
        сервер="Сервер: PHX или DN",
        участник="Кому выдать взыскание",
        причина="Причина взыскания",
        отработка="Что необходимо отработать",
    )
    @app_commands.choices(сервер=[
        app_commands.Choice(name="PHX", value="PHX"),
        app_commands.Choice(name="DN", value="DN"),
    ])
    async def cmd_issue_warning(interaction: discord.Interaction, сервер: str, участник: discord.Member, причина: str, отработка: str):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not consent_storage.has_consent(interaction.user.id):
            await interaction.response.send_message("❌ Сначала дайте согласие на системные уведомления бота. После этого функции бота станут доступны.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await discipline.issue_warning(
            interaction.guild, interaction.user, участник, причина, отработка, сервер
        )
        await interaction.followup.send(message, ephemeral=True)
