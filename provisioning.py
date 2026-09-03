# -*- coding: utf-8 -*-
"""Optional server-structure provisioning requested by the Dashboard.

The Dashboard supplies names and relationships; Discord IDs are returned by
Discord after creation and saved into the guild configuration. Nothing is
hard-coded here for a particular server.
"""
import discord
import database


async def provision_guild(guild: discord.Guild, blueprint: dict) -> dict:
    """Create missing roles/categories/channels from a Dashboard blueprint.

    Existing objects are reused by name. The function deliberately never
    deletes existing Discord objects.
    """
    if not isinstance(blueprint, dict):
        raise ValueError("blueprint must be an object")

    created = {"roles": [], "categories": [], "channels": []}
    role_map = {r.name: r for r in guild.roles}
    category_map = {c.name: c for c in guild.categories}
    channel_map = {c.name: c for c in guild.channels if not isinstance(c, discord.CategoryChannel)}

    for role_data in blueprint.get("roles", []):
        name = str(role_data.get("name", "")).strip()
        if not name or name in role_map:
            continue
        role = await guild.create_role(
            name=name,
            hoist=bool(role_data.get("hoist", False)),
            mentionable=bool(role_data.get("mentionable", False)),
            reason="Blin Dashboard server setup",
        )
        role_map[name] = role
        created["roles"].append({"id": role.id, "name": role.name})

    for category_data in blueprint.get("categories", []):
        name = str(category_data.get("name", "")).strip()
        if not name or name in category_map:
            continue
        category = await guild.create_category(name=name, reason="Blin Dashboard server setup")
        category_map[name] = category
        created["categories"].append({"id": category.id, "name": category.name})

    for channel_data in blueprint.get("channels", []):
        name = str(channel_data.get("name", "")).strip()
        if not name or name in channel_map:
            continue
        category_name = str(channel_data.get("category", "")).strip()
        category = category_map.get(category_name)
        channel = await guild.create_text_channel(
            name=name,
            category=category,
            reason="Blin Dashboard server setup",
        )
        channel_map[name] = channel
        created["channels"].append({"id": channel.id, "name": channel.name, "category_id": channel.category_id})

    return created


def save_provisioning_result(guild_id: int, created: dict):
    cfg = database.get_config(guild_id)
    cfg.setdefault("provisioning", {})["last_result"] = created
    database.set_config(guild_id, cfg)
    return cfg
