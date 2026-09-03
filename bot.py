# -*- coding: utf-8 -*-
"""Blin Bot entry point. Discord configuration is loaded from SQLite."""
import discord
from discord.ext import commands
import config, database, storage, utils
from logger_setup import logger
from ui_decision import RequestDecisionView
from applications import JoinInfoView
from vacations import VacationInfoView, refresh_vacation_message, check_and_expire_vacations, restore_vacation_schedules
from commands import register_commands
from dashboard_api import start_api

intents = discord.Intents.default()
intents.members = True


class BlinBot(commands.Bot):
    async def setup_hook(self):
        database.init_db()
        self.add_view(JoinInfoView())
        self.add_view(VacationInfoView("DN"))
        self.add_view(VacationInfoView("PHX"))
        for number, app in storage.DATA["applications"].items():
            if app.get("status") == "pending":
                self.add_view(RequestDecisionView("join", number))
        for vac_id, vac in storage.DATA["vacations"].items():
            if vac.get("status") == "pending":
                self.add_view(RequestDecisionView("vacation", vac_id))
        register_commands(self)
        await self.tree.sync()
        await start_api(self)


bot = BlinBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info("Бот запущен как %s (ID: %s)", bot.user, bot.user.id)
    for guild in bot.guilds:
        database.register_guild(guild.id, guild.name)
        utils.refresh_runtime_config(guild.id)
        raw = database.get_config(guild.id)
        channel_id = raw.get("recruit_info_channel")
        recruit_channel = guild.get_channel(channel_id) if channel_id else None
        if recruit_channel:
            embed = discord.Embed(
                title="Вступление в компанию",
                description=config.RECRUIT_INFO_TEXT,
                color=discord.Color.blurple(),
            )
            await utils.ensure_persistent_message(
                recruit_channel,
                storage.DATA,
                f"recruit_info_{guild.id}",
                [embed],
                JoinInfoView(),
            )
            await storage.persist()
        for server in ("DN", "PHX"):
            if utils.VACATION_CHANNELS.get(server):
                try:
                    await refresh_vacation_message(guild, server)
                except discord.HTTPException:
                    logger.exception("Не удалось обновить сообщение отпуска для %s", server)
        try:
            changed = await check_and_expire_vacations(guild)
            for server in changed:
                await refresh_vacation_message(guild, server)
            await restore_vacation_schedules(guild)
        except Exception:
            logger.exception("Ошибка инициализации отпусков на %s", guild.id)


def main():
    if not config.TOKEN:
        raise SystemExit("Не задан DISCORD_TOKEN")
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
