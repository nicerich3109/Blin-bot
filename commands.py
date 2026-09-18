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
import vacations
import discipline
import config
import discipline


async def _autocomplete_number(interaction: discord.Interaction, current: str):
    current = (current or "").upper()
    choices = []

    for number, app in storage.DATA["applications"].items():
        if app["status"] == "pending" and current in number:
            choices.append(app_commands.Choice(name=f"{number} (вступление)", value=number))

    for vac_id, vac in storage.DATA["vacations"].items():
        if vac["status"] == "pending" and current in vac_id:
            choices.append(app_commands.Choice(name=f"{vac_id} (отпуск)", value=vac_id))

    return choices[:25]


def register_commands(bot: commands.Bot):
    @bot.tree.command(name="принять", description="Принять заявку (на вступление или отпуск)")
    @app_commands.describe(номер="Номер заявки, например DN-001 или DN-VAC-001")
    @app_commands.autocomplete(номер=_autocomplete_number)
    async def cmd_accept(interaction: discord.Interaction, номер: str):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
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
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await vacations.force_remove_vacation(
            interaction.guild, interaction.user, участник, причина
        )
        await interaction.followup.send(message, ephemeral=True)


    @bot.tree.command(name="выдать_выговор", description="Выдать дисциплинарное взыскание")
    @app_commands.describe(
        участник="Кому выдать взыскание",
        причина="Причина взыскания",
        отработка="Что необходимо отработать",
    )
    async def cmd_issue_warning(interaction: discord.Interaction, участник: discord.Member, причина: str, отработка: str):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await discipline.issue_warning(
            interaction.guild, interaction.user, участник, причина, отработка
        )
        server = "DN" if interaction.channel.id == config.DISCIPLINE_LOG_CHANNELS["DN"] else "PHX"
        if interaction.channel.id in config.DISCIPLINE_LOG_CHANNELS.values():
            await discipline.log_warning(interaction.guild, server, message)
        await interaction.followup.send(message, ephemeral=True)
