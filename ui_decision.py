# -*- coding: utf-8 -*-
"""
Общие интерактивные компоненты для решений по заявкам: кнопки
"Принять"/"Отклонить" (п. 5.2 ТЗ) и модальное окно для причины отказа
(п. 5.3 ТЗ). Используются как для заявок на вступление, так и для
заявок на отпуск — вся специфика скрыта внутри decisions.decide_request.
"""

import discord

import decisions
from logger_setup import logger


class RequestDecisionView(discord.ui.View):
    """Персистентные кнопки "Принять"/"Отклонить" для одной заявки."""

    def __init__(self, kind: str, key: str):
        super().__init__(timeout=None)
        self.kind = kind
        self.key = key

        accept_btn = discord.ui.Button(
            label="Принять",
            style=discord.ButtonStyle.success,
            custom_id=f"decision_accept_{kind}_{key}",
        )
        accept_btn.callback = self.on_accept
        self.add_item(accept_btn)

        # Кнопка "Обзвон" — только для заявок на вступление. Позволяет
        # вызвать заявителя на обзвон ещё до решения по заявке (кнопки
        # "Принять"/"Отклонить" остаются доступны и после).
        if kind == "join":
            call_btn = discord.ui.Button(
                label="Обзвон",
                style=discord.ButtonStyle.primary,
                custom_id=f"decision_call_{kind}_{key}",
            )
            call_btn.callback = self.on_call
            self.add_item(call_btn)

        decline_btn = discord.ui.Button(
            label="Отклонить",
            style=discord.ButtonStyle.danger,
            custom_id=f"decision_decline_{kind}_{key}",
        )
        decline_btn.callback = self.on_decline
        self.add_item(decline_btn)

    async def on_accept(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await decisions.decide_request(
            interaction.guild, interaction.user, self.kind, self.key, accepted=True
        )
        await interaction.followup.send(message, ephemeral=True)

    async def on_decline(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DeclineReasonModal(self.kind, self.key))

    async def on_call(self, interaction: discord.Interaction):
        # Ленивый импорт — applications.py импортирует этот модуль, поэтому
        # импорт на уровне модуля создал бы циклическую зависимость.
        import storage
        import utils
        from applications import ObzvonChannelSelectView

        app = storage.DATA["applications"].get(self.key)
        if app is None:
            await interaction.response.send_message(f"Заявка `{self.key}` не найдена.", ephemeral=True)
            return
        if app["status"] != "pending":
            await interaction.response.send_message(
                f"Заявка `{self.key}` уже обработана (статус: {app['status']}).", ephemeral=True
            )
            return
        if not utils.is_recruiter(interaction.user, app["server"]):
            await interaction.response.send_message(
                "У вас нет прав обрабатывать заявки этого сервера.", ephemeral=True
            )
            return

        view = ObzvonChannelSelectView(self.key, app["server"])
        await interaction.response.send_message(
            "Выберите канал, в котором пройдёт обзвон:", view=view, ephemeral=True
        )


class DeclineReasonModal(discord.ui.Modal, title="Причина отказа"):
    reason_input = discord.ui.TextInput(
        label="Причина",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, kind: str, key: str):
        super().__init__()
        self.kind = kind
        self.key = key

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await decisions.decide_request(
            interaction.guild,
            interaction.user,
            self.kind,
            self.key,
            accepted=False,
            reason=str(self.reason_input.value),
        )
        await interaction.followup.send(message, ephemeral=True)
        if not ok:
            logger.info("Отказ по заявке %s:%s не применён: %s", self.kind, self.key, message)
