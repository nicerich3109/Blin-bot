# -*- coding: utf-8 -*-
import discord
from discord import app_commands
from discord.ext import commands

import database
import decisions
import discipline
import storage
import vacations
from applications import JoinInfoView
from reaction_roles import RoleButtonView
from dashboard_api import _upsert_message
from contracts import publish_block


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


def _can_publish(interaction: discord.Interaction) -> bool:
    return bool(
        interaction.guild
        and (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator)
    )


def _text_channel(guild: discord.Guild, raw_id):
    """Return a publishable text/announcement channel without referencing removed NewsChannel API."""
    if not raw_id:
        return None
    try:
        channel = guild.get_channel(int(raw_id))
    except (TypeError, ValueError):
        return None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _publish_applications(guild: discord.Guild):
    raw = database.get_config(guild.id)
    channel = _text_channel(guild, raw.get("recruit_info_channel"))
    if channel is None:
        raise ValueError("publish_channel_not_configured")
    import config
    embed = discord.Embed(
        title="Вступление в компанию",
        description=raw.get("join_info_text") or config.RECRUIT_INFO_TEXT,
        color=discord.Color.blurple(),
    )
    message = await _upsert_message(
        channel,
        f"recruit_info_{guild.id}",
        embeds=[embed],
        view=JoinInfoView(database.server_configs(guild.id)),
    )
    return message, channel


async def _publish_reaction(guild: discord.Guild, config_id: int):
    item = next(
        (x for x in database.list_reaction_role_configs(guild.id) if int(x.get("id", -1)) == config_id),
        None,
    )
    if not item:
        raise LookupError("reaction_role_not_found")
    channel = _text_channel(guild, item.get("channel_id"))
    if channel is None:
        raise ValueError("publish_channel_not_configured")

    embed = None
    if item.get("image") or item.get("text"):
        embed = discord.Embed(description=item.get("text") or "")
        if item.get("name"):
            embed.title = str(item["name"])[:256]
        if item.get("image"):
            embed.set_image(url=item["image"])

    view = RoleButtonView(guild.id, item.get("buttons", [])[:20], config_id)
    message = await _upsert_message(
        channel,
        f"reaction_roles_{guild.id}_{config_id}",
        content=None if embed else item.get("text"),
        embed=embed,
        view=view,
    )
    return message, channel


async def _publish_all(guild: discord.Guild):
    """Publish/update every configured panel using the same DB settings edited by the Dashboard."""
    results = []

    # Applications
    raw = database.get_config(guild.id)
    if raw.get("recruit_info_channel"):
        message, channel = await _publish_applications(guild)
        results.append(f"заявки: <#{channel.id}>")

    # Vacations — one panel per configured server/state profile.
    for profile in database.server_keys(guild.id):
        profile_cfg = database.get_server_config(guild.id, profile) or {}
        if not profile_cfg.get("vacation_channel"):
            continue
        await vacations.refresh_vacation_message(guild, profile)
        results.append(f"отпуск {profile}: <#{int(profile_cfg['vacation_channel'])}>")

    # Reaction-role panels.
    for item in database.list_reaction_role_configs(guild.id):
        message, channel = await _publish_reaction(guild, int(item["id"]))
        results.append(f"роли «{item.get('name') or item.get('id')}»: <#{channel.id}>")

    # Contract panels.
    for block in database.list_contracts(guild.id):
        channel = _text_channel(guild, block.get("channel_id"))
        if channel is None:
            continue
        await publish_block(
            channel,
            block,
            store=storage.DATA,
            store_key=f"contract_{guild.id}_{block['id']}" if block.get("id") is not None else None,
        )
        results.append(f"контракт: <#{channel.id}>")

    await storage.persist()
    return results


def register_commands(bot: commands.Bot):
    @bot.tree.command(name="publish", description="Опубликовать или обновить панели из настроек Dashboard")
    @app_commands.default_permissions(manage_guild=True)
    async def publish(i: discord.Interaction):
        if not i.guild:
            return await i.response.send_message("Эта команда работает только на сервере.", ephemeral=True)
        if not _can_publish(i):
            return await i.response.send_message("Недостаточно прав. Нужны права управления сервером.", ephemeral=True)

        await i.response.defer(ephemeral=True, thinking=True)
        try:
            results = await _publish_all(i.guild)
        except discord.Forbidden:
            return await i.followup.send("Боту не хватает прав для публикации в одном из настроенных каналов.", ephemeral=True)
        except discord.HTTPException as exc:
            return await i.followup.send(f"Discord вернул ошибку при публикации: HTTP {exc.status}.", ephemeral=True)
        except Exception:
            import logging
            logging.getLogger("blin_bot.commands").exception("/publish failed for guild=%s", i.guild.id)
            return await i.followup.send("Не удалось выполнить публикацию. Проверь настройки Dashboard и логи бота.", ephemeral=True)

        if not results:
            return await i.followup.send("В Dashboard пока нет настроенных панелей для публикации.", ephemeral=True)
        await i.followup.send("Опубликовано/обновлено:\n• " + "\n• ".join(results), ephemeral=True)

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
