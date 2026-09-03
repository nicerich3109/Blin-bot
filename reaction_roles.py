# -*- coding: utf-8 -*-
"""Reaction/button role module. Configuration is stored by Dashboard."""
import discord, database

class RoleButtonView(discord.ui.View):
    def __init__(self,guild_id,buttons):
        super().__init__(timeout=None); self.guild_id=guild_id
        for item in buttons:
            b=discord.ui.Button(label=item.get("label","Роль")[:80],style=getattr(discord.ButtonStyle,item.get("style","primary"),discord.ButtonStyle.primary),custom_id=f"role:{item.get('key','role')}" )
            async def callback(interaction,b=b,item=item):
                role=interaction.guild.get_role(item.get("role_id"))
                if not role:return await interaction.response.send_message("Роль больше не существует.",ephemeral=True)
                try:
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role,reason="Blin Bot role button")
                        text=f"Роль {role.mention} снята."
                    else:
                        await interaction.user.add_roles(role,reason="Blin Bot role button")
                        text=f"Роль {role.mention} выдана."
                    await interaction.response.send_message(text,ephemeral=True)
                except discord.Forbidden: await interaction.response.send_message("Бот не может управлять этой ролью.",ephemeral=True)
            b.callback=callback; self.add_item(b)

async def publish(channel,settings):
    embed=None
    if settings.get("embed",True):
        embed=discord.Embed(title=settings.get("title") or discord.Embed.Empty,description=settings.get("description") or discord.Embed.Empty)
        if settings.get("image"): embed.set_image(url=settings["image"])
    await channel.send(content=settings.get("text"),embed=embed,view=RoleButtonView(channel.guild.id,settings.get("buttons",[])[:20]))
