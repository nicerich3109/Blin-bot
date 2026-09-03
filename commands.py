# -*- coding: utf-8 -*-
import discord
from discord import app_commands
from discord.ext import commands

import database
import decisions
import discipline
import storage
import vacations


async def _autocomplete_number(interaction: discord.Interaction, current: str):
    """Suggest only pending requests belonging to the current guild."""
    current = (current or "").upper()
    choices = []
    guild_id = interaction.guild_id
    for number, app in storage.DATA["applications"].items():
        if guild_id and app.get("guild_id", guild_id) != guild_id:
            continue
        if app.get("status") == "pending" and current in number.upper():
            choices.append(app_commands.Choice(name=f"{number} (вступление)", value=number))
    for vid, vac in storage.DATA["vacations"].items():
        if guild_id and vac.get("guild_id", guild_id) != guild_id:
            continue
        if vac.get("status") == "pending" and current in vid.upper():
            choices.append(app_commands.Choice(name=f"{vid} (отпуск)", value=vid))
    return choices[:25]


def _module_ok(interaction: discord.Interaction, module: str) -> bool:
    return bool(interaction.guild and database.module_enabled(interaction.guild.id, module))


def register_commands(bot: commands.Bot):
    @bot.tree.command(name="принять", description="Принять заявку")
    @app_commands.describe(номер="Номер заявки")
    @app_commands.autocomplete(номер=_autocomplete_number)
    async def accept(i: discord.Interaction, номер: str):
        if not i.guild:
            return await i.response.send_message("Только на сервере.", ephemeral=True)
        if not _module_ok(i, "applications"):
            return await i.response.send_message("Модуль заявок отключён в настройках сервера.", ephemeral=True)
        kind, key = decisions.find_kind(номер, i.guild.id)
        if not kind:
            return await i.response.send_message("Заявка не найдена.", ephemeral=True)
        await i.response.defer(ephemeral=True, thinking=True)
        _, msg = await decisions.decide_request(i.guild, i.user, kind, key, True)
        await i.followup.send(msg, ephemeral=True)

    @bot.tree.command(name="отклонить", description="Отклонить заявку")
    @app_commands.describe(номер="Номер заявки", причина="Причина")
    @app_commands.autocomplete(номер=_autocomplete_number)
    async def decline(i: discord.Interaction, номер: str, причина: str):
        if not i.guild:
            return await i.response.send_message("Только на сервере.", ephemeral=True)
        if not _module_ok(i, "applications"):
            return await i.response.send_message("Модуль заявок отключён в настройках сервера.", ephemeral=True)
        kind, key = decisions.find_kind(номер, i.guild.id)
        if not kind:
            return await i.response.send_message("Заявка не найдена.", ephemeral=True)
        await i.response.defer(ephemeral=True, thinking=True)
        _, msg = await decisions.decide_request(i.guild, i.user, kind, key, False, reason=причина)
        await i.followup.send(msg, ephemeral=True)

    @bot.tree.command(name="вынесение_из_отпуска", description="Принудительно вынести из отпуска")
    @app_commands.describe(участник="Участник", причина="Причина")
    async def force(i: discord.Interaction, участник: discord.Member, причина: str):
        if not i.guild:
            return await i.response.send_message("Только на сервере.", ephemeral=True)
        if not _module_ok(i, "vacations"):
            return await i.response.send_message("Модуль отпусков отключён в настройках сервера.", ephemeral=True)
        await i.response.defer(ephemeral=True, thinking=True)
        _, msg = await vacations.force_remove_vacation(i.guild, i.user, участник, причина)
        await i.followup.send(msg, ephemeral=True)

    @bot.tree.command(name="выдать_выговор", description="Выдать строгий выговор")
    @app_commands.describe(кому="Кому выдать", причина="Причина", отработка="Отработка")
    async def warning(i: discord.Interaction, кому: discord.Member, причина: str, отработка: str = ""):
        if not i.guild:
            return await i.response.send_message("Только на сервере.", ephemeral=True)
        if not _module_ok(i, "discipline"):
            return await i.response.send_message("Модуль дисциплины отключён в настройках сервера.", ephemeral=True)
        if not i.user.guild_permissions.manage_roles and not i.user.guild_permissions.administrator:
            return await i.response.send_message("Недостаточно прав.", ephemeral=True)
        cfg = database.get_config(i.guild.id)
        channel_id = cfg.get("discipline_channel")
        channel = i.guild.get_channel(channel_id) if channel_id else None
        await i.response.defer(ephemeral=True, thinking=True)
        _, msg = await discipline.issue_warning(i.guild, i.user, кому, причина, отработка, channel)
        await i.followup.send(msg, ephemeral=True)
