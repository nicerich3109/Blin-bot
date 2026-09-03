# -*- coding: utf-8 -*-
"""Configurable disciplinary warning workflow from the specification."""
import discord
import database
from notifications import send_dm_if_allowed

FIRST_ROLE="1/3 строгих"
SECOND_ROLE="2/3 строгих"

async def ensure_roles(guild):
    roles={r.name:r for r in guild.roles}
    result=[]
    for name in (FIRST_ROLE,SECOND_ROLE):
        role=roles.get(name)
        if role is None: role=await guild.create_role(name=name,reason="Blin Bot: disciplinary system")
        result.append(role)
    return result

async def issue_warning(guild,issuer,target,reason,work_off,output_channel):
    if issuer.id==target.id: return False,"Нельзя выдать выговор самому себе."
    roles=await ensure_roles(guild); first,second=roles
    level=2 if second in target.roles else 1 if first in target.roles else 0
    if level>=2:
        new_level=2
        result=f"{target.mention} понижен по причине: {reason}. Отработка: {work_off or 'не указана'}."
    elif level==1:
        await target.remove_roles(first,reason="Blin Bot: второй строгий выговор")
        await target.add_roles(second,reason="Blin Bot: второй строгий выговор")
        new_level=2
        result=f"Выдан второй строгий выговор {target.mention}. Причина: {reason}. Отработка: {work_off or 'не указана'}."
    else:
        await target.add_roles(first,reason="Blin Bot: первый строгий выговор")
        new_level=1
        result=f"Выдан первый строгий выговор {target.mention}. Причина: {reason}. Отработка: {work_off or 'не указана'}."
    database.add_warning(guild.id,target.id,issuer.id,reason,work_off or "",new_level)
    channel=output_channel
    if channel: await channel.send(result+f"\nВыдал(а): {issuer.mention}")
    await send_dm_if_allowed(guild,target,result)
    return True,result
