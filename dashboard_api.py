# -*- coding: utf-8 -*-
"""Dashboard API v2.

The API exposes only runtime Discord data and per-guild configuration. The
frontend must not contain the shared secret; production authentication should
be added at the Dashboard backend with Discord OAuth2.
"""
import os
import discord
from aiohttp import web
import config
import database


def _auth(request):
    return bool(config.API_SECRET) and request.headers.get("X-Blin-Secret") == config.API_SECRET


def _guild(bot, request):
    try:
        return bot.get_guild(int(request.match_info["guild_id"]))
    except (KeyError, TypeError, ValueError):
        return None


def _error(message, status=400):
    return web.json_response({"error": message}, status=status)


def _validate_contract(block):
    if not isinstance(block, dict):
        return "contract must be an object"
    buttons = block.get("buttons", [])
    if not isinstance(buttons, list) or len(buttons) > 20:
        return "at most 20 buttons are allowed"
    for button in buttons:
        options = button.get("options", [])
        if not isinstance(options, list) or len(options) > 10:
            return "at most 10 options are allowed per button"
        for option in options:
            fields = option.get("fields", [])
            if not isinstance(fields, list) or len(fields) > 5:
                return "at most 5 modal fields are allowed per option"
    return None


def create_app(bot):
    origins = {x.strip() for x in os.getenv("BLIN_API_ALLOWED_ORIGINS", "").split(",") if x.strip()}

    @web.middleware
    async def cors(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)
        origin = request.headers.get("Origin")
        if origin and origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Blin-Secret"
            response.headers["Access-Control-Allow-Methods"] = "GET, PUT, POST, OPTIONS"
        return response

    @web.middleware
    async def auth(request, handler):
        if request.path == "/health" or request.method == "OPTIONS":
            return await handler(request)
        if not _auth(request):
            return _error("unauthorized", 401)
        return await handler(request)

    app = web.Application(middlewares=[cors, auth])

    async def health(request):
        return web.json_response({"ok": True, "service": "blin-bot", "api_version": 2})

    async def guilds(request):
        return web.json_response([
            {"id": g.id, "name": g.name, "member_count": g.member_count}
            for g in bot.guilds if database.guild_enabled(g.id)
        ])

    async def objects(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        return web.json_response({
            "roles": [{"id": r.id, "name": r.name, "position": r.position, "managed": r.managed}
                      for r in guild.roles if not r.managed],
            "categories": [{"id": c.id, "name": c.name, "position": c.position} for c in guild.categories],
            "channels": [{"id": c.id, "name": c.name, "type": str(c.type), "category_id": c.category_id}
                         for c in guild.channels if not isinstance(c, discord.CategoryChannel)],
        })

    async def cfg(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        if request.method == "GET":
            return web.json_response(database.get_config(guild.id))
        try:
            value = await request.json()
        except Exception:
            return _error("invalid_json")
        if not isinstance(value, dict):
            return _error("config_must_be_object")
        database.set_config(guild.id, value)
        return web.json_response({"ok": True, "config": value})

    async def modules(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        if request.method == "GET":
            return web.json_response(database.get_modules(guild.id))
        try:
            body = await request.json()
            database.set_module(guild.id, body["module"], bool(body.get("enabled", True)), body.get("settings", {}))
        except (KeyError, ValueError, TypeError):
            return _error("invalid_module_payload")
        return web.json_response({"ok": True, "modules": database.get_modules(guild.id)})

    async def contracts(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        if request.method == "GET":
            return web.json_response(database.list_contracts(guild.id))
        try:
            block = await request.json()
        except Exception:
            return _error("invalid_json")
        error = _validate_contract(block)
        if error:
            return _error(error)
        return web.json_response({"id": database.save_contract(guild.id, block)}, status=201)

    async def warnings(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        raw = request.query.get("user_id")
        try:
            target_id = int(raw) if raw else None
        except ValueError:
            return _error("invalid_user_id")
        return web.json_response(database.list_warnings(guild.id, target_id))

    async def reaction_roles(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        if request.method == "GET":
            return web.json_response(database.list_reaction_role_configs(guild.id))
        try:
            value = await request.json()
            buttons = value.get("buttons", [])
            if not isinstance(value, dict) or not isinstance(buttons, list) or len(buttons) > 20:
                return _error("invalid_reaction_role_payload")
            database.save_reaction_role_config(guild.id, value)
        except Exception:
            return _error("invalid_reaction_role_payload")
        return web.json_response({"ok": True}, status=201)

    async def consent(request):
        guild = _guild(bot, request)
        if not guild:
            return _error("guild_not_found", 404)
        try:
            body = await request.json()
            user_id = int(body["user_id"])
            enabled = bool(body["enabled"])
        except (KeyError, TypeError, ValueError):
            return _error("invalid_consent_payload")
        database.set_consent(guild.id, user_id, enabled)
        return web.json_response({"ok": True, "enabled": enabled})

    app.add_routes([
        web.get("/health", health),
        web.get("/api/guilds", guilds),
        web.get("/api/guilds/{guild_id}/objects", objects),
        web.get("/api/guilds/{guild_id}/config", cfg),
        web.put("/api/guilds/{guild_id}/config", cfg),
        web.get("/api/guilds/{guild_id}/modules", modules),
        web.put("/api/guilds/{guild_id}/modules", modules),
        web.get("/api/guilds/{guild_id}/contracts", contracts),
        web.post("/api/guilds/{guild_id}/contracts", contracts),
        web.get("/api/guilds/{guild_id}/warnings", warnings),
        web.get("/api/guilds/{guild_id}/reaction-roles", reaction_roles),
        web.post("/api/guilds/{guild_id}/reaction-roles", reaction_roles),
        web.put("/api/guilds/{guild_id}/consent", consent),
    ])
    return app


async def start_api(bot):
    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    await web.TCPSite(runner, config.API_HOST, config.API_PORT).start()
    return runner
