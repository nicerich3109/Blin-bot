# -*- coding: utf-8 -*-
"""Система дисциплинарных взысканий."""
import discord
import config, utils
from logger_setup import logger
async def ensure_discipline_roles(guild):
    result={}
    for name in ("1/3 строгих","2/3 строгих"):
        role=discord.utils.get(guild.roles,name=name)
        if role is None:
            try: role=await guild.create_role(name=name,reason="Blin: система дисциплинарных взысканий")
            except discord.Forbidden: logger.error("Нет прав создать роль %s",name); continue
        result[name]=role.id
    return result
async def issue_warning(guild,issuer,target,reason,workoff):
    if not issuer.guild_permissions.administrator and not (utils.is_recruiter(issuer,"DN") or utils.is_recruiter(issuer,"PHX")): return False,"У вас нет прав выдавать дисциплинарные взыскания."
    roles=await ensure_discipline_roles(guild); one=guild.get_role(roles.get("1/3 строгих")); two=guild.get_role(roles.get("2/3 строгих"))
    if one is None or two is None: return False,"Не удалось найти или создать роли дисциплины."
    state="two" if two in target.roles else "one" if one in target.roles else "none"
    try:
        if state=="none": await target.add_roles(one,reason=reason); title="1/3"; public=f"⚠️ {target.mention} получил выговор (1/3). Выдал: {issuer.mention}. Причина: {reason}. Отработка: {workoff}"
        elif state=="one": await target.remove_roles(one,reason=reason); await target.add_roles(two,reason=reason); title="2/3"; public=f"⚠️ {target.mention} получил выговор (2/3). Выдал: {issuer.mention}. Причина: {reason}. Отработка: {workoff}"
        else: title="понижение"; public=f"⬇️ {target.mention} понижен. Выдал: {issuer.mention}. Причина: {reason}. Отработка: {workoff}"
    except discord.Forbidden: return False,"Бот не может изменить роли участника. Проверьте иерархию ролей."
    dm=f"Вам выдано дисциплинарное взыскание ({title}).\nПричина: {reason}\nОтработка: {workoff}"
    try: await target.send(dm)
    except discord.HTTPException: logger.warning("Не удалось отправить дисциплинарное ЛС %s",target.id)
    return True,public
