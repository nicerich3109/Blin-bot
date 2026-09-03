# -*- coding: utf-8 -*-
"""Applications and recruiter call flow.

Discord IDs are resolved from the active guild's Dashboard configuration.
"""
import re
import discord
import config
import storage
import utils
from ui_decision import RequestDecisionView


class JoinModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(label="Ваш никнейм", max_length=100)
    static = discord.ui.TextInput(label="Ваш статик #", max_length=20)
    ooc_age = discord.ui.TextInput(label="Ваш OOC возраст", max_length=10)
    ooc_name = discord.ui.TextInput(label="Ваше OOC имя", max_length=100)
    previous_families = discord.ui.TextInput(label="В каких семьях были?", style=discord.TextStyle.paragraph, max_length=300, required=False)

    def __init__(self, server: str):
        super().__init__(title=f"Заявка на вступление — {utils.SERVER_NAMES[server]}")
        self.server = server

    async def on_submit(self, interaction: discord.Interaction):
        token = utils.set_current_guild(interaction.guild.id)
        try:
            age_raw = str(self.ooc_age.value).strip()
            age_digits = re.sub(r"\D", "", age_raw)
            age_value = int(age_digits) if age_digits else None
            if age_value is None or not (14 <= age_value <= 50):
                await interaction.response.send_message("❌ Заявка автоматически отклонена: указан некорректный OOC возраст. Допустимый диапазон — от 14 до 50 лет. Переотправьте заявку.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            await create_join_ticket(interaction, self.server, {
                "nickname": str(self.nickname.value), "static": str(self.static.value),
                "ooc_age": age_raw, "ooc_name": str(self.ooc_name.value),
                "previous_families": str(self.previous_families.value) or "—",
            })
        finally:
            utils.reset_current_guild(token)


class JoinInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        denver_btn = discord.ui.Button(label="Denver", style=discord.ButtonStyle.primary, custom_id="join_apply_dn")
        phoenix_btn = discord.ui.Button(label="Phoenix", style=discord.ButtonStyle.danger, custom_id="join_apply_phx")
        denver_btn.callback = self.on_denver
        phoenix_btn.callback = self.on_phoenix
        self.add_item(denver_btn)
        self.add_item(phoenix_btn)

    async def _open(self, interaction, server):
        token = utils.set_current_guild(interaction.guild.id)
        try:
            remaining = _cooldown_remaining(interaction.user.id)
            if remaining > 0:
                await interaction.response.send_message(f"⏳ Подавать заявку можно не чаще раза в {config.JOIN_APPLICATION_COOLDOWN_SECONDS // 60} мин. Попробуйте снова через {int(remaining)} сек.", ephemeral=True)
                return
            await interaction.response.send_modal(JoinModal(server))
        finally:
            utils.reset_current_guild(token)

    async def on_denver(self, interaction):
        await self._open(interaction, "DN")

    async def on_phoenix(self, interaction):
        await self._open(interaction, "PHX")


def _cooldown_remaining(user_id) -> float:
    last_iso = storage.DATA["join_cooldowns"].get(str(user_id))
    if not last_iso:
        return 0
    try:
        last_dt = utils.parse_stored_datetime(last_iso)
    except ValueError:
        return 0
    return max(0.0, config.JOIN_APPLICATION_COOLDOWN_SECONDS - (utils.now() - last_dt).total_seconds())


async def create_join_ticket(interaction: discord.Interaction, server: str, form: dict):
    token = utils.set_current_guild(interaction.guild.id)
    try:
        guild = interaction.guild
        number = storage.next_ticket_number(server)
        category_id = utils.TICKET_CATEGORIES[server]
        category = guild.get_channel(category_id) if category_id else None
        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send("❌ Категория заявок не настроена в Dashboard.", ephemeral=True)
            return
        recruit_roles = utils.RECRUIT_ROLES[server]
        recruit_role = guild.get_role(recruit_roles[0]) if len(recruit_roles) > 0 else None
        chief_role = guild.get_role(recruit_roles[1]) if len(recruit_roles) > 1 else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if recruit_role:
            overwrites[recruit_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        if chief_role:
            overwrites[chief_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel = await category.create_text_channel(name=number, overwrites=overwrites, reason=f"Заявка на вступление {number}")
        embed = discord.Embed(title=f"Заявка {number}", color=discord.Color.gold())
        embed.add_field(name="Никнейм", value=form["nickname"], inline=False)
        embed.add_field(name="Статик #", value=form["static"], inline=True)
        embed.add_field(name="OOC возраст", value=form["ooc_age"], inline=True)
        embed.add_field(name="OOC имя", value=form["ooc_name"], inline=True)
        embed.add_field(name="Сервер", value=utils.SERVER_NAMES[server], inline=True)
        embed.add_field(name="В каких семьях были", value=form["previous_families"], inline=False)
        embed.set_footer(text=f"Discord: {interaction.user} ({interaction.user.id})")
        pings = interaction.user.mention
        if recruit_role: pings += f" {recruit_role.mention}"
        if chief_role: pings += f" {chief_role.mention}"
        ticket_message = await channel.send(content=pings, embed=embed, view=RequestDecisionView("join", number))
        storage.DATA["applications"][number] = {"server": server, "applicant_id": interaction.user.id, "channel_id": channel.id, "ticket_message_id": ticket_message.id, "status": "pending", **form}
        storage.DATA["join_cooldowns"][str(interaction.user.id)] = utils.now().isoformat()
        await storage.persist()
        await interaction.followup.send(f"Ваша заявка была отправлена, ожидайте оповещения от high staff в канале {channel.mention}", ephemeral=True)
    finally:
        utils.reset_current_guild(token)


class ObzvonChannelSelectView(discord.ui.View):
    def __init__(self, number: str, server: str):
        super().__init__(timeout=300)
        self.number, self.server = number, server
        options = [discord.SelectOption(label=f"Обзвон {i + 1}", value=str(channel_id)) for i, channel_id in enumerate(utils.OBZVON_CHANNELS[server])]
        select = discord.ui.Select(placeholder="Канал обзвона", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction):
        token = utils.set_current_guild(interaction.guild.id)
        try:
            channel_id = int(interaction.data["values"][0])
            await interaction.response.defer(ephemeral=True, thinking=True)
            _, message = await call_to_obzvon(interaction.guild, self.number, channel_id)
            await interaction.followup.send(message, ephemeral=True)
        finally:
            utils.reset_current_guild(token)


async def call_to_obzvon(guild: discord.Guild, number: str, channel_id: int):
    token = utils.set_current_guild(guild.id)
    try:
        app = storage.DATA["applications"].get(number)
        if app is None:
            return False, f"Заявка `{number}` не найдена."
        if app["status"] != "pending":
            return False, f"Заявка `{number}` уже обработана (статус: {app['status']})."
        server = app["server"]
        applicant = await utils.get_member_safe(guild, app["applicant_id"])
        if applicant is None:
            return False, "Заявитель не найден на сервере."
        call_channel = guild.get_channel(channel_id)
        if call_channel is None:
            return False, "Канал обзвона не найден в текущей конфигурации Dashboard."
        role_id = utils.OBZVON_ROLES.get(server)
        role = guild.get_role(role_id) if role_id else None
        if role is None:
            return False, "Роль обзвона не настроена в Dashboard."
        try:
            await applicant.add_roles(role, reason=f"Вызван на обзвон по заявке {number}")
        except discord.Forbidden:
            return False, "Не удалось выдать роль обзвона — проверьте иерархию ролей бота."
        app["obzvon_channel_id"] = channel_id
        await storage.persist()
        ticket_channel = guild.get_channel(app["channel_id"])
        if ticket_channel:
            await ticket_channel.send(f"📞 {applicant.mention}, вас вызвали на обзвон! Пожалуйста, зайдите в канал {call_channel.mention}.")
        return True, f"Заявитель вызван на обзвон в {call_channel.mention}, роль обзвона выдана."
    finally:
        utils.reset_current_guild(token)
