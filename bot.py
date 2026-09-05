# -*- coding: utf-8 -*-
"""Blin Bot entry point. Discord configuration is loaded from SQLite."""
import discord
from discord.ext import commands
import config, database, storage, utils
from logger_setup import logger
from ui_decision import RequestDecisionView
from applications import JoinInfoView
from vacations import VacationInfoView, refresh_vacation_message, check_and_expire_vacations, restore_vacation_schedules
from contracts import _build_publish_payload
from reaction_roles import RoleButtonView
from commands import register_commands
from dashboard_api import start_api

intents = discord.Intents.default(); intents.members = True; intents.message_content = True

class BlinBot(commands.Bot):
    async def setup_hook(self):
        database.init_db()
        for number, app in storage.DATA["applications"].items():
            if app.get("status") == "pending": self.add_view(RequestDecisionView("join", number))
        for vac_id, vac in storage.DATA["vacations"].items():
            if vac.get("status") == "pending": self.add_view(RequestDecisionView("vacation", vac_id))
        register_commands(self)
        try:
            self.dashboard_runner = await start_api(self); logger.info("Dashboard API запущен на %s:%s", config.API_HOST, config.API_PORT)
        except Exception: logger.exception("Не удалось запустить Dashboard API на %s:%s", config.API_HOST, config.API_PORT); raise
        try: await self.tree.sync(); logger.info("Discord slash-команды синхронизированы")
        except Exception: logger.exception("Не удалось синхронизировать Discord slash-команды")

bot = BlinBot(command_prefix="!", intents=intents)
_dashboard_views_restored = False

async def restore_dashboard_views():
    """Register persistent views for panels published from Dashboard once per process."""
    global _dashboard_views_restored
    if _dashboard_views_restored: return
    for guild in bot.guilds:
        try:
            profiles = database.server_configs(guild.id)
            if profiles:
                bot.add_view(JoinInfoView(profiles))
                for profile in profiles:
                    if database.get_server_config(guild.id, profile).get("vacation_channel"): bot.add_view(VacationInfoView(profile))
            for item in database.list_reaction_role_configs(guild.id): bot.add_view(RoleButtonView(guild.id, item.get("buttons", [])[:20], item.get("id")))
            for block in database.list_contracts(guild.id):
                if block.get("channel_id"):
                    _, _, view = _build_publish_payload(block); bot.add_view(view)
        except Exception: logger.exception("Не удалось восстановить Dashboard views для guild=%s", guild.id)
    _dashboard_views_restored = True

@bot.event
async def on_ready():
    logger.info("Бот запущен как %s (ID: %s)", bot.user, bot.user.id)
    await restore_dashboard_views()
    for guild in bot.guilds:
        database.register_guild(guild.id, guild.name); utils.refresh_runtime_config(guild.id); raw = database.get_config(guild.id); server_profiles = database.server_configs(guild.id)
        recruit_channel_id = raw.get("recruit_info_channel"); recruit_channel = guild.get_channel(int(recruit_channel_id)) if recruit_channel_id else None
        if recruit_channel:
            embed = discord.Embed(title="Вступление в компанию", description=raw.get("join_info_text") or config.RECRUIT_INFO_TEXT, color=discord.Color.blurple())
            await utils.ensure_persistent_message(recruit_channel, storage.DATA, f"recruit_info_{guild.id}", [embed], JoinInfoView(server_profiles)); await storage.persist()
        for server in database.server_keys(guild.id):
            if utils.VACATION_CHANNELS.get(server):
                try: await refresh_vacation_message(guild, server)
                except discord.HTTPException: logger.exception("Не удалось обновить сообщение отпуска для %s", server)
        try:
            changed = await check_and_expire_vacations(guild)
            for server in changed: await refresh_vacation_message(guild, server)
            await restore_vacation_schedules(guild)
        except Exception: logger.exception("Ошибка инициализации отпусков на %s", guild.id)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild: return
    if database.module_enabled(message.guild.id, "applications") is False and not database.get_config(message.guild.id).get("autoreplies"):
        await bot.process_commands(message); return
    rules = database.get_config(message.guild.id).get("autoreplies", [])
    if isinstance(rules, list):
        content = message.content.casefold().strip()
        for rule in rules:
            if not isinstance(rule, dict): continue
            trigger = str(rule.get("trigger", "")).casefold().strip(); response = str(rule.get("response", ""))
            if not trigger or not response or trigger not in content: continue
            channel_id = str(rule.get("channel_id", "")).strip()
            if channel_id and channel_id != str(message.channel.id): continue
            role_id = str(rule.get("role_id", "")).strip()
            if role_id and not any(str(role.id) == role_id for role in getattr(message.author, "roles", [])): continue
            try: await message.channel.send(response, allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False))
            except discord.HTTPException: logger.exception("Не удалось отправить автоответ в guild=%s channel=%s", message.guild.id, message.channel.id)
            break
    await bot.process_commands(message)

def main():
    if not config.TOKEN: raise SystemExit("Не задан DISCORD_TOKEN")
    bot.run(config.TOKEN)

if __name__ == "__main__": main()
