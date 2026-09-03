"""Interactive decision components for applications."""
import discord
import decisions
from logger_setup import logger


class RequestDecisionView(discord.ui.View):
    """Persistent accept/decline/call controls for one request."""
    def __init__(self, kind: str, key: str):
        super().__init__(timeout=None)
        self.kind = kind
        self.key = key

        accept_btn = discord.ui.Button(label="Принять", style=discord.ButtonStyle.success,
                                       custom_id=f"decision_accept_{kind}_{key}")
        accept_btn.callback = self.on_accept
        self.add_item(accept_btn)
        if kind == "join":
            call_btn = discord.ui.Button(label="Обзвон", style=discord.ButtonStyle.primary,
                                         custom_id=f"decision_call_{kind}_{key}")
            call_btn.callback = self.on_call
            self.add_item(call_btn)
        decline_btn = discord.ui.Button(label="Отклонить", style=discord.ButtonStyle.danger,
                                        custom_id=f"decision_decline_{kind}_{key}")
        decline_btn.callback = self.on_decline
        self.add_item(decline_btn)

    async def on_accept(self, interaction: discord.Interaction):
        import utils
        token = utils.set_current_guild(interaction.guild.id)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            ok, message = await decisions.decide_request(
                interaction.guild, interaction.user, self.kind, self.key, accepted=True
            )
            await interaction.followup.send(message, ephemeral=True)
        finally:
            utils.reset_current_guild(token)

    async def on_decline(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DeclineReasonModal(self.kind, self.key))

    async def on_call(self, interaction: discord.Interaction):
        import storage, utils
        from applications import ObzvonChannelSelectView
        token = utils.set_current_guild(interaction.guild.id)
        try:
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
                await interaction.response.send_message("У вас нет прав обрабатывать заявки этого сервера.", ephemeral=True)
                return
            await interaction.response.send_message(
                "Выберите канал, в котором пройдёт обзвон:",
                view=ObzvonChannelSelectView(self.key, app["server"]), ephemeral=True
            )
        finally:
            utils.reset_current_guild(token)


class DeclineReasonModal(discord.ui.Modal, title="Причина отказа"):
    reason_input = discord.ui.TextInput(label="Причина", style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, kind: str, key: str):
        super().__init__()
        self.kind = kind
        self.key = key

    async def on_submit(self, interaction: discord.Interaction):
        import utils
        token = utils.set_current_guild(interaction.guild.id)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            ok, message = await decisions.decide_request(
                interaction.guild, interaction.user, self.kind, self.key,
                accepted=False, reason=str(self.reason_input.value)
            )
            await interaction.followup.send(message, ephemeral=True)
            if not ok:
                logger.info("Отказ по заявке %s:%s не применён: %s", self.kind, self.key, message)
        finally:
            utils.reset_current_guild(token)
