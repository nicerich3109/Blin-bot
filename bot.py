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
from contracts import ContractPanelView, publish_contract_panel
from discipline import ensure_discipline_roles
from roles_data import save_roles
from consent_view import StandaloneConsentView
from reaction_roles import publish_reaction_role_messages, handle_reaction_add, handle_reaction_remove

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True


class BlinBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(JoinInfoView())
        self.add_view(StandaloneConsentView())
        self.add_view(VacationInfoView("DN"))
        self.add_view(VacationInfoView("PHX"))
        self.add_view(ContractPanelView("DN"))
        self.add_view(ContractPanelView("PHX"))

        for number, app in storage.DATA["applications"].items():
            if app.get("status") == "pending":
                self.add_view(RequestDecisionView("join", number))

        for vac_id, vac in storage.DATA["vacations"].items():
            if vac.get("status") == "pending":
                self.add_view(RequestDecisionView("vacation", vac_id))

        for contract_id, contract in storage.DATA["contracts"].items():
            if contract.get("status") == "pending":
                self.add_view(RequestDecisionView("contract", contract_id))

        register_commands(self)

        if config.GUILD_ID:
            guild_obj = discord.Object(id=config.GUILD_ID)

            # Регистрируем команды только на рабочем сервере.
            # Ранее команды одновременно оставались глобальными, из-за чего
            # Discord мог показывать два одинаковых экземпляра команды.
            self.tree.copy_global_to(guild=guild_obj)
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            await self.tree.sync(guild=guild_obj)
        else:
            await self.tree.sync()


bot = BlinBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info("Бот запущен как %s (ID: %s)", bot.user, bot.user.id)

    try:
        save_roles(bot.guilds)
    except Exception:
        logger.exception("Не удалось сохранить сведения о ролях")

    # Каналы из config.py принадлежат конкретному серверу. Не пытаемся
    # искать их через fetch_channel() в других гильдиях: это приводит к
    # InvalidData: Guild ID resolved to a different guild.
    configured_channel_ids = {
        config.RECRUIT_INFO_CHANNEL,
        config.VACATION_CHANNEL_DN,
        config.VACATION_CHANNEL_PHX,
    }

    for guild in bot.guilds:
        if not any(guild.get_channel(channel_id) is not None for channel_id in configured_channel_ids):
            continue

        logger.info("Инициализация сообщений Blin в гильдии %s (%s)", guild.name, guild.id)
        try:
            await ensure_discipline_roles(guild)
            await publish_contract_panel(guild, "DN")
            await publish_contract_panel(guild, "PHX")
            await publish_reaction_role_messages(guild)
        except Exception:
            logger.exception("Ошибка публикации дополнительных панелей в гильдии %s", guild.id)

        # Каждый тип сообщения обрабатываем независимо. Ошибка одного
        # сообщения не должна останавливать публикацию/обновление остальных.
        recruit_channel = guild.get_channel(config.RECRUIT_INFO_CHANNEL)
        if recruit_channel is not None:
            try:
                embed = discord.Embed(
                    title="Вступление в компанию",
                    description=config.RECRUIT_INFO_TEXT,
                    color=discord.Color.blurple(),
                )
                await utils.ensure_persistent_message(
                    recruit_channel, storage.DATA, "recruit_info", [embed], JoinInfoView()
                )
                await storage.persist()
                logger.info("Сообщение заявок на вступление опубликовано/обновлено: %s", recruit_channel.id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound) as exc:
                logger.exception("Не удалось опубликовать/обновить сообщение заявок: %s", exc)
        else:
            logger.error("Канал заявок на вступление (ID %s) не найден в гильдии %s", config.RECRUIT_INFO_CHANNEL, guild.id)

        for server in ("DN", "PHX"):
            vacation_channel_id = utils.VACATION_CHANNELS[server]
            vacation_channel = guild.get_channel(vacation_channel_id)
            if vacation_channel is None:
                logger.info(
                    "Канал отпуска %s (ID %s) не найден в гильдии %s — пропускаю",
                    server, vacation_channel_id, guild.id
                )
                continue

            try:
                await refresh_vacation_message(guild, server)
                logger.info(
                    "Сообщение отпуска %s опубликовано/обновлено: %s",
                    server, vacation_channel_id
                )
            except (discord.HTTPException, discord.Forbidden, discord.NotFound, discord.InvalidData):
                logger.exception("Не удалось опубликовать/обновить сообщение отпуска для %s", server)

        try:
            changed = await check_and_expire_vacations(guild)
            for server in changed:
                try:
                    await refresh_vacation_message(guild, server)
                except (discord.HTTPException, discord.Forbidden, discord.NotFound, discord.InvalidData):
                    logger.exception("Не удалось обновить список отпускников для %s", server)
            await restore_vacation_schedules(guild)
        except Exception:
            logger.exception("Ошибка при инициализации таймеров отпусков на сервере %s", guild.id)


@bot.event
async def on_raw_reaction_add(payload):
    try:
        await handle_reaction_add(payload)
    except Exception:
        logger.exception("Ошибка обработки добавления реакции")

@bot.event
async def on_raw_reaction_remove(payload):
    try:
        await handle_reaction_remove(payload)
    except Exception:
        logger.exception("Ошибка обработки удаления реакции")


def main():
    if not config.TOKEN or config.TOKEN == "ВСТАВЬТЕ_ТОКЕН_СЮДА":
        raise SystemExit(
            "Не задан токен бота. Установите переменную окружения DISCORD_TOKEN "
            "или впишите токен в config.py."
        )
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
