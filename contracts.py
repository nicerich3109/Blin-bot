# -*- coding: utf-8 -*-
"""Contract bonus application engine. Blocks are created/edited by Dashboard API."""
import discord, database

MAX_BUTTONS=20; MAX_OPTIONS=10; MAX_MODAL_FIELDS=5

def _button_style(name):
    return getattr(discord.ButtonStyle,name,discord.ButtonStyle.primary)

class ContractOptionsView(discord.ui.View):
    def __init__(self,guild_id,block):
        super().__init__(timeout=300); self.guild_id=guild_id; self.block=block
        options=block.get("options",[])[:MAX_OPTIONS]
        select=discord.ui.Select(placeholder=block.get("select_placeholder","Выберите опцию"),options=[discord.SelectOption(label=str(x.get("name","Опция"))[:100],value=str(i)) for i,x in enumerate(options)])
        async def callback(interaction):
            option=options[int(select.values[0])]; await interaction.response.send_modal(ContractModal(guild_id,block,option))
        select.callback=callback; self.add_item(select)

class ContractModal(discord.ui.Modal):
    def __init__(self,guild_id,block,option):
        super().__init__(title=str(option.get("modal_title",option.get("name","Контракт")))[:45]); self.guild_id=guild_id; self.block=block; self.option=option
        for i,field in enumerate(option.get("fields",[])[:MAX_MODAL_FIELDS]):
            self.add_item(discord.ui.TextInput(label=str(field.get("label","Поле"))[:45],placeholder=str(field.get("placeholder",""))[:100],style=discord.TextStyle.paragraph if field.get("paragraph") else discord.TextStyle.short,required=bool(field.get("required",True)),max_length=1000))
    async def on_submit(self,interaction):
        values={item.label:item.value for item in self.children if isinstance(item,discord.ui.TextInput)}
        channel_id=self.block.get("review_channel"); channel=interaction.guild.get_channel(channel_id) if channel_id else None
        embed=discord.Embed(title=f"Заявка: {self.option.get('name','Контракт')}",color=discord.Color.blue())
        for k,v in values.items(): embed.add_field(name=k,value=v,inline=False)
        embed.set_footer(text=f"Подал: {interaction.user} ({interaction.user.id})")
        if channel: await channel.send(embed=embed)
        await interaction.response.send_message("Заявка на премию отправлена.",ephemeral=True)

async def publish_block(channel,block):
    content=block.get("message_text") or None; embed=None
    if block.get("embed",True):
        embed=discord.Embed(title=block.get("title") or discord.Embed.Empty,description=block.get("description") or discord.Embed.Empty)
        if block.get("color"): embed.colour=discord.Colour(int(str(block["color"]).lstrip('#'),16))
        if block.get("image"): embed.set_image(url=block["image"])
    view=discord.ui.View(timeout=None)
    for option in block.get("buttons",[])[:MAX_BUTTONS]:
        b=discord.ui.Button(label=str(option.get("label",option.get("name","Контракт")))[:80],style=_button_style(option.get("style","primary")))
        async def cb(interaction,b=b): await interaction.response.send_message("Выберите опцию из меню:",view=ContractOptionsView(interaction.guild.id,option),ephemeral=True)
        b.callback=cb; view.add_item(b)
    await channel.send(content=content,embed=embed,view=view)
