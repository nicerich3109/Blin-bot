# -*- coding: utf-8 -*-
"""Роли по реакциям и кнопкам."""
import discord
import config, storage

class ReactionRoleView(discord.ui.View):
    def __init__(self,key):
        super().__init__(timeout=None)
        item=config.REACTION_ROLE_MESSAGES[key]
        for cfg in item.get("buttons",[])[:2]:
            role_id=int(cfg["role_id"])
            button=discord.ui.Button(label=cfg["label"][:80],style=getattr(discord.ButtonStyle,cfg.get("style","primary"),discord.ButtonStyle.primary),custom_id=f"rr_{key}_{role_id}")
            async def callback(interaction,role_id=role_id):
                role=interaction.guild.get_role(role_id)
                if role is None: await interaction.response.send_message("Роль не найдена.",ephemeral=True); return
                try:
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role,reason="Роль снята кнопкой")
                        text="Роль снята."
                    else:
                        await interaction.user.add_roles(role,reason="Роль выдана кнопкой")
                        text="Роль выдана."
                    await interaction.response.send_message(text,ephemeral=True)
                except discord.Forbidden: await interaction.response.send_message("❌ Бот не может изменить эту роль.",ephemeral=True)
            button.callback=callback; self.add_item(button)

async def publish_reaction_role_messages(guild):
    for key,item in config.REACTION_ROLE_MESSAGES.items():
        channel=guild.get_channel(item["channel_id"])
        if channel is None: continue
        embed=discord.Embed(description=item["text"],color=discord.Color.blurple())
        if item.get("image"): embed.set_image(url=item["image"])
        view=ReactionRoleView(key) if item.get("mode")=="button" else None
        message_id=storage.DATA["persistent_messages"].get(f"reaction_role_{key}")
        msg=None
        if message_id:
            try: msg=await channel.fetch_message(message_id)
            except (discord.NotFound,discord.Forbidden): pass
        if msg is None: msg=await channel.send(embed=embed,view=view); storage.DATA["persistent_messages"][f"reaction_role_{key}"]=msg.id
        else: await msg.edit(embed=embed,view=view)
        await storage.persist()

async def handle_reaction_add(payload):
    if payload.guild_id is None: return
    cfg=next((v for v in config.REACTION_ROLE_MESSAGES.values() if v.get("message_id")==payload.message_id),None)
    if not cfg or cfg.get("mode")!="reaction": return
    role_id=cfg.get("role_id_by_emoji",{}).get(str(payload.emoji))
    if not role_id: return
    guild=bot_guild=payload._state._get_guild(payload.guild_id)
    if guild is None: return
    member=guild.get_member(payload.user_id)
    role=guild.get_role(int(role_id))
    if member and role:
        try: await member.add_roles(role,reason="Роль по реакции")
        except discord.Forbidden: pass

async def handle_reaction_remove(payload):
    if payload.guild_id is None: return
    cfg=next((v for v in config.REACTION_ROLE_MESSAGES.values() if v.get("message_id")==payload.message_id),None)
    if not cfg or cfg.get("mode")!="reaction": return
    role_id=cfg.get("role_id_by_emoji",{}).get(str(payload.emoji))
    if not role_id: return
    guild=payload._state._get_guild(payload.guild_id)
    if guild is None: return
    member=guild.get_member(payload.user_id); role=guild.get_role(int(role_id))
    if member and role:
        try: await member.remove_roles(role,reason="Роль снята реакцией")
        except discord.Forbidden: pass
