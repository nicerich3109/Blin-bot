# -*- coding: utf-8 -*-
"""
Точка входа. Собирает все модули воедино: регистрирует персистентные
кнопки, слэш-команды, публикует/обновляет информационные сообщения и
восстанавливает таймеры окончания отпусков.
"""

import discord
from discord.ext import commands

import config
import storage
import utils
from logger_setup import logger
from ui_decision import RequestDecisionView
from applications import JoinInfoView
from vacations import (
    VacationInfoView,
    refresh_vacation_message,
    check_and_expire_vacations,
    restore_vacation_schedules,
)
from commands import register_commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class BlinBot(commands.Bot):
    async def setup_hook(self):
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

        if config.GUILD_ID:
            guild_obj = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
        else:
            await self.tree.sync()


bot = BlinBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info("Бот запущен как %s (ID: %s)", bot.user, bot.user.id)

    for guild in bot.guilds:
        configured_channel_ids = {
            config.RECRUIT_INFO_CHANNEL,
            config.VACATION_CHANNEL_DN,
            config.VACATION_CHANNEL_PHX,
        }
        if not any(guild.get_channel(channel_id) is not None for channel_id in configured_channel_ids):
            logger.info("Пропускаю гильдию %s (%s): каналы Blin в config.py не найдены", guild.name, guild.id)
            continue

        recruit_channel = guild.get_channel(config.RECRUIT_INFO_CHANNEL)
        if recruit_channel:
            embed = discord.Embed(
                title="Вступление в компанию",
                description=config.RECRUIT_INFO_TEXT,
                color=discord.Color.blurple(),
            )
            await utils.ensure_persistent_message(
                recruit_channel, storage.DATA, "recruit_info", [embed], JoinInfoView()
            )
            await storage.persist()
        else:
            logger.error("Канал заявок на вступление (ID %s) не найден", config.RECRUIT_INFO_CHANNEL)

        for server in ("DN", "PHX"):
            vacation_channel_id = utils.VACATION_CHANNELS[server]
            if guild.get_channel(vacation_channel_id) is None:
                logger.info("Канал отпуска %s (ID %s) не найден в гильдии %s — пропускаю", server, vacation_channel_id, guild.id)
                continue
            try:
                await refresh_vacation_message(guild, server)
            except (discord.HTTPException, discord.InvalidData):
                logger.exception("Не удалось обновить сообщение отпуска для %s", server)

        try:
            changed = await check_and_expire_vacations(guild)
            for server in changed:
                try:
                    await refresh_vacation_message(guild, server)
                except (discord.HTTPException, discord.InvalidData):
                    logger.exception("Не удалось обновить список отпускников для %s", server)
            await restore_vacation_schedules(guild)
        except Exception:
            logger.exception("Ошибка при инициализации таймеров отпусков на сервере %s", guild.id)


def main():
    if not config.TOKEN or config.TOKEN == "ВСТАВЬТЕ_ТОКЕН_СЮДА":
        raise SystemExit(
            "Не задан токен бота. Установите переменную окружения DISCORD_TOKEN "
            "или впишите токен в config.py."
        )
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
