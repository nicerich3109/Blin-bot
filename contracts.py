# -*- coding: utf-8 -*-
"""Contract bonus application engine. Blocks are created/edited by Dashboard API."""
import discord, database

MAX_BUTTONS=20; MAX_OPTIONS=10; MAX_MODAL_FIELDS=5

def _button_style(name): return getattr(discord.ButtonStyle,name,discord.ButtonStyle.primary)
def _option_name(option): return str(option.get("name",option.get("label","Опция")))

def _normalize_block(block):
    if not isinstance(block,dict): return {}
    message=block.get("message") if isinstance(block.get("message"),dict) else {}
    out=dict(block); out["embed"]=message.get("mode","embed")!="none" if "message" in block else bool(block.get("embed",True)); out["color"]=message.get("color",block.get("color")); out["title"]=message.get("title",block.get("title")); out["description"]=message.get("text",message.get("description",block.get("description"))); out["message_text"]=block.get("message_text","")
    if message.get("image"): out["image"]=message["image"]
    out["review_channel"]=block.get("review_channel",block.get("review_channel_id")); out["logs_channel"]=block.get("logs_channel",block.get("logs_channel_id"))
    buttons=[]
    for b in block.get("buttons",[])[:MAX_BUTTONS]:
        if not isinstance(b,dict): continue
        nb=dict(b); nb["name"]=_option_name(b); nb["options"]=[]
        for o in b.get("options",[])[:MAX_OPTIONS]:
            if not isinstance(o,dict): continue
            no=dict(o); no["name"]=_option_name(o); no["modal_title"]=o.get("modal_title",o.get("label",o.get("name","Контракт"))); nb["options"].append(no)
        buttons.append(nb)
    out["buttons"]=buttons; return out

class ContractOptionsView(discord.ui.View):
    def __init__(self,guild_id,block):
        super().__init__(timeout=300); self.guild_id=guild_id; self.block=_normalize_block(block); options=self.block.get("options",[])[:MAX_OPTIONS]
        if not options: return
        select=discord.ui.Select(placeholder=self.block.get("select_placeholder","Выберите опцию"),options=[discord.SelectOption(label=_option_name(x)[:100],description=str(x.get("description",""))[:100] or None,value=str(i)) for i,x in enumerate(options)])
        async def callback(interaction): await interaction.response.send_modal(ContractModal(guild_id,self.block,options[int(select.values[0])]))
        select.callback=callback; self.add_item(select)

class ContractModal(discord.ui.Modal):
    def __init__(self,guild_id,block,option):
        super().__init__(title=str(option.get("modal_title",_option_name(option)))[:45]); self.guild_id=guild_id; self.block=block; self.option=option
        for f in option.get("fields",[])[:MAX_MODAL_FIELDS]:
            f=f if isinstance(f,dict) else {}; self.add_item(discord.ui.TextInput(label=str(f.get("label",f.get("name","Поле")))[:45],placeholder=str(f.get("placeholder",""))[:100],style=discord.TextStyle.paragraph if f.get("paragraph") else discord.TextStyle.short,required=bool(f.get("required",True)),max_length=1000))
    async def on_submit(self,interaction):
        values={item.label:item.value for item in self.children if isinstance(item,discord.ui.TextInput)}; channel_id=self.block.get("review_channel"); channel=interaction.guild.get_channel(int(channel_id)) if channel_id else None
        embed=discord.Embed(title=f"Заявка: {_option_name(self.option)}",color=discord.Color.blue())
        for k,v in values.items(): embed.add_field(name=k,value=v,inline=False)
        embed.set_footer(text=f"Подал: {interaction.user} ({interaction.user.id})")
        if channel: await channel.send(embed=embed)
        await interaction.response.send_message("Заявка на премию отправлена.",ephemeral=True)


def _build_publish_payload(block):
    block=_normalize_block(block); content=block.get("message_text") or None; embed=None
    if block.get("embed",True):
        embed=discord.Embed(title=block.get("title") or discord.Embed.Empty,description=block.get("description") or discord.Embed.Empty)
        if block.get("color"):
            try: embed.colour=discord.Colour(int(str(block["color"]).lstrip('#'),16))
            except (TypeError,ValueError): pass
        if block.get("image"): embed.set_image(url=block["image"])
    view=discord.ui.View(timeout=None); scope=str(block.get("id") or "draft")
    for index,option in enumerate(block.get("buttons",[])[:MAX_BUTTONS]):
        option_data=option; b=discord.ui.Button(label=str(option.get("label",option.get("name","Контракт")))[:80],style=_button_style(option.get("style","primary")),custom_id=f"contract:{scope}:{index}")
        async def cb(interaction,option_data=option_data): await interaction.response.send_message("Выберите опцию из меню:",view=ContractOptionsView(interaction.guild.id,option_data),ephemeral=True)
        b.callback=cb; view.add_item(b)
    return content,embed,view


async def publish_block(channel,block,store=None,store_key=None):
    content,embed,view=_build_publish_payload(block); message=None
    if store is not None and store_key:
        stored_id=store.setdefault("persistent_messages",{}).get(store_key)
        if stored_id:
            try: message=await channel.fetch_message(int(stored_id))
            except (discord.NotFound,discord.Forbidden,discord.HTTPException): message=None
    if message:
        try: await message.edit(content=content,embed=embed,view=view)
        except (discord.NotFound,discord.Forbidden,discord.HTTPException): message=None
    if message is None: message=await channel.send(content=content,embed=embed,view=view)
    if store is not None and store_key: store.setdefault("persistent_messages",{})[store_key]=message.id
    return message
