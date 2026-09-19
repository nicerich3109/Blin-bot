# -*- coding: utf-8 -*-
import discord
import consent_storage

CONSENT_TEXT = (
    "Перед использованием бота необходимо согласие на получение системных "
    "уведомлений бота в личные сообщения Discord.\n\n"
    "Согласие означает, что бот сможет отправлять вам служебные уведомления "
    "о статусе ваших заявок в организацию, а также о дисциплинарных взысканиях.\n\n"
    "Без согласия использование функций бота недоступно. Подача заявки на "
    "вступление остаётся доступной — согласие можно предоставить прямо при её оформлении."
)


class ConsentView(discord.ui.View):
    """Согласие перед открытием формы заявки на вступление."""

    def __init__(self, modal_factory):
        super().__init__(timeout=180)
        self.modal_factory = modal_factory

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        await consent_storage.set_consent(interaction.user.id, True)
        await interaction.response.send_modal(self.modal_factory())

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger)
    async def decline(self, interaction, button):
        await consent_storage.set_consent(interaction.user.id, False)
        await interaction.response.edit_message(
            content="❌ Согласие не предоставлено. Использование функций бота недоступно. "
                    "Для подачи заявки согласие можно предоставить снова.",
            view=None,
        )


class StandaloneConsentView(discord.ui.View):
    """Постоянная кнопка согласия, публикуемая администратором в канале."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Дать согласие на уведомления",
        style=discord.ButtonStyle.success,
        custom_id="consent_accept_standalone",
    )
    async def accept(self, interaction, button):
        await consent_storage.set_consent(interaction.user.id, True)
        await interaction.response.send_message(
            "✅ Согласие сохранено. Теперь вам доступны функции бота и системные уведомления в ЛС.",
            ephemeral=True,
        )


async def ensure_consent(interaction):
    """Проверяет согласие перед использованием обычных функций бота."""
    if consent_storage.has_consent(interaction.user.id):
        return True
    await interaction.response.send_message(
        "❌ Для использования этой функции необходимо дать согласие на системные уведомления бота.",
        ephemeral=True,
    )
    return False
