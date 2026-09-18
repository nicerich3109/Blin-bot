# -*- coding: utf-8 -*-
"""Роли по реакциям и кнопкам."""
import discord
import config, storage

class ReactionRoleView(discord.ui.View):
    def __init__(self,key):
        super().__init__(timeout=None)
        for cfg in config.REACTION_ROLE_MESSAGES[key].get("buttons",[])[:2]:
            role_id=int(cfg["role_id"])
            button=discord.ui.Button(label=cfg["label"][:80],style=getattr(discord.ButtonStyle,cfg.get("style","primary"),discord.ButtonStyle.primary),custom_id=f"rr_{key}_{role_id}")
            async def callback(interaction,role_id=role_id):
                role=interaction.guild.get_role(role_id)
                if role is None:
                    await interaction.response.send_message("Роль не найдена.",ephemeral=True); return
                try:
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role,reason="Роль снята кнопкой"); text="Роль снята."
                    else:
                        await interaction.user.add_roles(role,reason="Роль выдана кнопкой"); text="Роль выдана."
                    await interaction.response.send_message(text,ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Бот не может изменить эту роль.",ephemeral=True)
            button.callback=callback
            self.add_item(button)

async def publish_reaction_role_messages(guild):
    for key,item in config.REACTION_ROLE_MESSAGES.items():
        channel=guild.get_channel(item["channel_id"])
        if channel is None: continue
        embed=discord.Embed(description=item["text"],color=discord.Color.blurple())
        if item.get("image"): embed.set_image(url=item["image"])
        view=ReactionRoleView(key) if item.get("mode")=="button" else None
        store_key=f"reaction_role_{key}"
        msg=None
        old_id=storage.DATA["persistent_messages"].get(store_key)
        if old_id:
            try: msg=await channel.fetch_message(old_id)
            except (discord.NotFound,discord.Forbidden): pass
        if msg is None:
            msg=await channel.send(embed=embed,view=view)
            storage.DATA["persistent_messages"][store_key]=msg.id
        else:
            await msg.edit(embed=embed,view=view)
        if item.get("mode")=="reaction":
            for emoji in item.get("role_id_by_emoji",{}):
                try: await msg.add_reaction(emoji)
                except discord.HTTPException: pass
        await storage.persist()

async def _handle(payload, add):
    if payload.guild_id is None: return
    guild=payload._state._get_guild(payload.guild_id)
    if guild is None: return
    for key,item in config.REACTION_ROLE_MESSAGES.items():
        if item.get("mode")!="reaction": continue
        if storage.DATA["persistent_messages"].get(f"reaction_role_{key}") != payload.message_id: continue
        role_id=item.get("role_id_by_emoji",{}).get(str(payload.emoji))
        if not role_id: continue
        member=guild.get_member(payload.user_id)
        role=guild.get_role(int(role_id))
        if member is None:
            try: member=await guild.fetch_member(payload.user_id)
            except discord.HTTPException: return
        if role is None: return
        try:
            if add: await member.add_roles(role,reason="Роль по реакции")
            else: await member.remove_roles(role,reason="Роль снята реакцией")
        except discord.Forbidden: pass

async def handle_reaction_add(payload): await _handle(payload,True)
async def handle_reaction_remove(payload): await _handle(payload,False)
