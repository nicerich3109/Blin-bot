# -*- coding: utf-8 -*-
"""Заявки на выплату контрактов."""
import discord
import config, storage, utils
from logger_setup import logger
from ui_decision import RequestDecisionView

class ContractOptionSelect(discord.ui.Select):
    def __init__(self,server,key):
        self.server,self.key=server,key
        options=config.CONTRACT_BUTTONS[server][key]["options"][:10]
        super().__init__(placeholder="Выберите опцию из меню:",options=[
            discord.SelectOption(label=str(o["label"])[:100],value=str(o["value"])[:100],
                                 description=str(o.get("description",""))[:100] or None) for o in options])
    async def callback(self,interaction):
        option=next(o for o in config.CONTRACT_BUTTONS[self.server][self.key]["options"] if str(o["value"])==self.values[0])
        await interaction.response.send_modal(ContractModal(self.server,self.key,option))

class ContractOptionView(discord.ui.View):
    def __init__(self,server,key):
        super().__init__(timeout=120); self.add_item(ContractOptionSelect(server,key))

class ContractModal(discord.ui.Modal):
    def __init__(self,server,key,option):
        super().__init__(title=str(option.get("modal_title","Заявка на выплату"))[:45])
        self.server,self.key,self.option=server,key,option
        for i,field in enumerate(option.get("fields",[])[:5]):
            item=discord.ui.TextInput(label=str(field.get("label",f"Поле {i+1}"))[:45],
                placeholder=str(field.get("placeholder",""))[:100] or None,
                style=discord.TextStyle.paragraph if field.get("paragraph") else discord.TextStyle.short,
                required=bool(field.get("required",True)),max_length=min(int(field.get("max_length",1000)),4000))
            setattr(self,f"field_{i}",item); self.add_item(item)
    async def on_submit(self,interaction):
        values={}
        for i,field in enumerate(self.option.get("fields",[])[:5]):
            values[str(field.get("label",f"Поле {i+1}"))]=str(getattr(self,f"field_{i}").value)
        number=storage.next_contract_id(self.server)
        channel=interaction.guild.get_channel(config.CONTRACT_PAYOUT_CHANNELS[self.server])
        if channel is None:
            await interaction.response.send_message("❌ Канал заявок на выплату не найден.",ephemeral=True); return
        embed=discord.Embed(title=f"Заявка на выплату {number}",description=f"Тип: **{self.option.get('label',self.key)}**",color=discord.Color.gold())
        embed.add_field(name="Заявитель",value=f"{interaction.user.mention} ({interaction.user.id})",inline=False)
        for label,value in values.items(): embed.add_field(name=label[:256],value=value[:1024] or "—",inline=False)
        embed.add_field(name="Сервер",value=utils.SERVER_NAMES[self.server],inline=True)
        msg=await channel.send(embed=embed,view=RequestDecisionView("contract",number))
        storage.DATA["contracts"][number]={"server":self.server,"requester_id":interaction.user.id,"option":self.option.get("label",self.key),"fields":values,"status":"pending","message_id":msg.id}
        await storage.persist()
        await interaction.response.send_message(f"Заявка {number} отправлена на рассмотрение.",ephemeral=True)

class ContractPanelButton(discord.ui.Button):
    def __init__(self,server,key,item):
        super().__init__(label=item["label"][:80],style=getattr(discord.ButtonStyle,item.get("style","primary"),discord.ButtonStyle.primary),custom_id=f"contract_panel_{server}_{key}")
        self.server,self.key=server,key
    async def callback(self,interaction):
        await interaction.response.send_message("Выберите опцию из меню:",view=ContractOptionView(self.server,self.key),ephemeral=True)

class ContractPanelView(discord.ui.View):
    def __init__(self,server):
        super().__init__(timeout=None)
        for item in config.CONTRACT_BUTTONS[server][:20]: self.add_item(ContractPanelButton(server,item["key"],item))

async def publish_contract_panel(guild,server):
    channel=guild.get_channel(config.CONTRACT_PANEL_CHANNELS[server])
    if channel is None: logger.error("Канал панели контрактов %s не найден",server); return
    embed=discord.Embed(title=config.CONTRACT_PANEL_TITLES[server],description=config.CONTRACT_PANEL_TEXTS[server],color=discord.Color.blurple())
    if config.CONTRACT_PANEL_IMAGES.get(server): embed.set_image(url=config.CONTRACT_PANEL_IMAGES[server])
    await utils.ensure_persistent_message(channel,storage.DATA,f"contract_panel_{server}",[embed],ContractPanelView(server))
    await storage.persist()
