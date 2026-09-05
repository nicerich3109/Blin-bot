# -*- coding: utf-8 -*-
"""Contract bonus application engine. Blocks are created/edited by Dashboard API."""
import discord, database

MAX_BUTTONS=20; MAX_OPTIONS=10; MAX_MODAL_FIELDS=5

def _button_style(name):
    return getattr(discord.ButtonStyle,name,discord.ButtonStyle.primary)

def _option_name(option): return str(option.get("name",option.get("label","Опция")))

def _normalize_block(block):
    """Accept the Dashboard constructor format and the original bot format."""
    if not isinstance(block,dict): return {}
    message=block.get("message") if isinstance(block.get("message"),dict) else {}
    out=dict(block)
    out["embed"]=message.get("mode", "embed") != "none" if "message" in block else bool(block.get("embed",True))
    out["color"]=message.get("color",block.get("color"))
    out["title"]=message.get("title",block.get("title"))
    out["description"]=message.get("text",message.get("description",block.get("description")))
    out["message_text"]=block.get("message_text", "" if "message" in block else block.get("message_text",""))
    if message.get("image"): out["image"]=message["image"]
    out["review_channel"]=block.get("review_channel",block.get("review_channel_id"))
    out["logs_channel"]=block.get("logs_channel",block.get("logs_channel_id"))
    buttons=[]
    for b in block.get("buttons",[])[:MAX_BUTTONS]:
        if not isinstance(b,dict): continue
        nb=dict(b); nb["name"]=_option_name(b)
        opts=[]
        for o in b.get("options",[])[:MAX_OPTIONS]:
            if not isinstance(o,dict): continue
            no=dict(o); no["name"]=_option_name(o); no["modal_title"]=o.get("modal_title",o.get("label",o.get("name","Контракт")))
            opts.append(no)
        nb["options"]=opts; buttons.append(nb)
    out["buttons"]=buttons
    return out

class ContractOptionsView(discord.ui.View):
    def __init__(self,guild_id,block):
        super().__init__(timeout=300); self.guild_id=guild_id; self.block=_normalize_block(block)
        options=self.block.get("options",[])[:MAX_OPTIONS]
        if not options: return
        select=discord.ui.Select(placeholder=self.block.get("select_placeholder","Выберите опцию"),options=[discord.SelectOption(label=_option_name(x)[:100],description=str(x.get("description",""))[:100] or None,value=str(i)) for i,x in enumerate(options)])
        async def callback(interaction):
            option=options[int(select.values[0])]; await interaction.response.send_modal(ContractModal(guild_id,self.block,option))
        select.callback=callback; self.add_item(select)

class ContractModal(discord.ui.Modal):
    def __init__(self,guild_id,block,option):
        option=option or {}; title=str(option.get("modal_title",_option_name(option)))[:45]
        super().__init__(title=title); self.guild_id=guild_id; self.block=block; self.option=option
        for field in option.get("fields",[])[:MAX_MODAL_FIELDS]:
            field=field if isinstance(field,dict) else {}
            self.add_item(discord.ui.TextInput(label=str(field.get("label",field.get("name","Поле")))[:45],placeholder=str(field.get("placeholder",""))[:100],style=discord.TextStyle.paragraph if field.get("paragraph") else discord.TextStyle.short,required=bool(field.get("required",True)),max_length=1000))
    async def on_submit(self,interaction):
        values={item.label:item.value for item in self.children if isinstance(item,discord.ui.TextInput)}
        channel_id=self.block.get("review_channel"); channel=interaction.guild.get_channel(int(channel_id)) if channel_id else None
        embed=discord.Embed(title=f"Заявка: {_option_name(self.option)}",color=discord.Color.blue())
        for k,v in values.items(): embed.add_field(name=k,value=v,inline=False)
        embed.set_footer(text=f"Подал: {interaction.user} ({interaction.user.id})")
        if channel: await channel.send(embed=embed)
        await interaction.response.send_message("Заявка на премию отправлена.",ephemeral=True)

async def publish_block(channel,block):
    block=_normalize_block(block)
    content=block.get("message_text") or None; embed=None
    if block.get("embed",True):
        embed=discord.Embed(title=block.get("title") or discord.Embed.Empty,description=block.get("description") or discord.Embed.Empty)
        if block.get("color"):
            try: embed.colour=discord.Colour(int(str(block["color"]).lstrip('#'),16))
            except (TypeError,ValueError): pass
        if block.get("image"): embed.set_image(url=block["image"])
    view=discord.ui.View(timeout=None)
    for option in block.get("buttons",[])[:MAX_BUTTONS]:
        b=discord.ui.Button(label=str(option.get("label",option.get("name","Контракт")))[:80],style=_button_style(option.get("style","primary")))
        async def cb(interaction,b=b): await interaction.response.send_message("Выберите опцию из меню:",view=ContractOptionsView(interaction.guild.id,b),ephemeral=True)
        b.callback=cb; view.add_item(b)
    await channel.send(content=content,embed=embed,view=view)
