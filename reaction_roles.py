# -*- coding: utf-8 -*-
"""Reaction/button role module. Configuration is stored by Dashboard."""
import discord, database


class RoleButtonView(discord.ui.View):
    def __init__(self,guild_id,buttons):
        super().__init__(timeout=None); self.guild_id=guild_id
        for index,item in enumerate(buttons):
            item=dict(item or {})
            key=str(item.get("key") or index)
            b=discord.ui.Button(label=str(item.get("label","Роль"))[:80],style=getattr(discord.ButtonStyle,item.get("style","primary"),discord.ButtonStyle.primary),custom_id=f"role:{guild_id}:{key}")
            async def callback(interaction,b=b,item=item):
                try: role=interaction.guild.get_role(int(item.get("role_id")))
                except (TypeError,ValueError): role=None
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


async def publish(channel,settings,store=None,store_key=None):
    embed=None
    if settings.get("embed",True):
        embed=discord.Embed(title=settings.get("title") or discord.Embed.Empty,description=settings.get("text") or settings.get("description") or discord.Embed.Empty)
        if settings.get("image"): embed.set_image(url=settings["image"])
    content=None if embed else settings.get("text")
    message=None
    if store is not None and store_key:
        stored_id=store.setdefault("persistent_messages",{}).get(store_key)
        if stored_id:
            try: message=await channel.fetch_message(int(stored_id))
            except (discord.NotFound,discord.Forbidden,discord.HTTPException): message=None
    view=RoleButtonView(channel.guild.id,settings.get("buttons",[])[:20])
    if message:
        try: await message.edit(content=content,embed=embed,view=view)
        except (discord.NotFound,discord.Forbidden,discord.HTTPException): message=None
    if message is None: message=await channel.send(content=content,embed=embed,view=view)
    if store is not None and store_key: store.setdefault("persistent_messages",{})[store_key]=message.id
    return message
