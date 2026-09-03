# -*- coding: utf-8 -*-
"""Opt-in DM notifications. Discord can still reject delivery; callers must handle that."""
import discord
import database

class NotificationConsentView(discord.ui.View):
    def __init__(self, on_accept, on_decline):
        super().__init__(timeout=300)
        self.on_accept_cb=on_accept; self.on_decline_cb=on_decline
    @discord.ui.button(label="Принять",style=discord.ButtonStyle.success)
    async def accept(self,interaction:discord.Interaction,button):
        await database.set_consent(interaction.guild.id,interaction.user.id,True)
        await self.on_accept_cb(interaction)
    @discord.ui.button(label="Отклонить",style=discord.ButtonStyle.secondary)
    async def decline(self,interaction:discord.Interaction,button):
        await self.on_decline_cb(interaction)

def consent_text():
    return ("Перед созданием заявки необходимо согласиться на системные уведомления в личных сообщениях.\n\n"
            "Согласие означает, что Blin Bot сможет отправлять вам в ЛС уведомления о статусе заявок "
            "и дисциплинарных взысканиях. Согласие можно не давать; в этом случае заявка не создаётся.")

async def send_dm_if_allowed(guild,user,content,embed=None):
    if not database.has_consent(guild.id,user.id): return False
    try:
        await user.send(content=content,embed=embed); return True
    except (discord.Forbidden,discord.HTTPException): return False
