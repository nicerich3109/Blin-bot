# -*- coding: utf-8 -*-
import discord
import consent_storage

CONSENT_TEXT=("Перед отправкой заявки необходимо согласие на получение системных уведомлений бота в личные сообщения Discord.\n\n"
"Согласие означает, что бот сможет отправлять вам служебные уведомления о статусе ваших заявок в организацию, а также о дисциплинарных взысканиях.\n\n"
"Без согласия бот не сможет продолжить оформление заявки.")

class ConsentView(discord.ui.View):
    def __init__(self, modal_factory):
        super().__init__(timeout=180)
        self.modal_factory=modal_factory

    @discord.ui.button(label="Принять",style=discord.ButtonStyle.success)
    async def accept(self,interaction,button):
        await consent_storage.set_consent(interaction.user.id,True)
        await interaction.response.send_modal(self.modal_factory())

    @discord.ui.button(label="Отклонить",style=discord.ButtonStyle.danger)
    async def decline(self,interaction,button):
        await consent_storage.set_consent(interaction.user.id,False)
        await interaction.response.edit_message(content="❌ Согласие не предоставлено. Для работы бота с заявками необходимо разрешить системные уведомления в ЛС.",view=None)
