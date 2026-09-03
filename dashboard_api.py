# -*- coding: utf-8 -*-
"""Dashboard API: Discord OAuth2 sessions + per-guild runtime configuration."""
import os
import secrets
from urllib.parse import urlencode

import discord
from aiohttp import web, ClientSession

import config
import database
from provisioning import provision_guild, save_provisioning_result
from contracts import publish_block

OAUTH_STATES = set()
SESSIONS = {}
MANAGE_GUILD = 1 << 5
ADMINISTRATOR = 1 << 3


def _auth(request):
    if config.API_SECRET and request.headers.get("X-Blin-Secret") == config.API_SECRET:
        return {"dev": True}
    return SESSIONS.get(request.cookies.get("blin_session"))


def _guild(bot, request):
    try: return bot.get_guild(int(request.match_info["guild_id"]))
    except (KeyError, TypeError, ValueError): return None


def _error(message, status=400): return web.json_response({"error": message}, status=status)


def _can_manage_guild(session, guild_id):
    if session and session.get("dev"): return True
    if not session: return False
    permissions = int(session.get("guild_permissions", {}).get(str(guild_id), 0))
    return bool(permissions & (MANAGE_GUILD | ADMINISTRATOR))


def _validate_contract(block):
    if not isinstance(block, dict): return "contract must be an object"
    buttons = block.get("buttons", [])
    if not isinstance(buttons, list) or len(buttons) > 20: return "at most 20 buttons are allowed"
    for button in buttons:
        if not isinstance(button, dict): return "button must be an object"
        options = button.get("options", [])
        if not isinstance(options, list) or len(options) > 10: return "at most 10 options are allowed per button"
        for option in options:
            if not isinstance(option, dict): return "option must be an object"
            fields = option.get("fields", [])
            if not isinstance(fields, list) or len(fields) > 5: return "at most 5 modal fields are allowed per option"
    return None


def create_app(bot):
    origins = {x.strip() for x in os.getenv("BLIN_API_ALLOWED_ORIGINS", "").split(",") if x.strip()}

    @web.middleware
    async def cors(request, handler):
        if request.method == "OPTIONS": response = web.Response(status=204)
        else: response = await handler(request)
        origin = request.headers.get("Origin")
        if origin and origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Blin-Secret"
            response.headers["Access-Control-Allow-Methods"] = "GET, PUT, POST, OPTIONS"
        return response

    @web.middleware
    async def auth(request, handler):
        if request.path in {"/health", "/auth/discord", "/auth/callback"} or request.method == "OPTIONS": return await handler(request)
        session = _auth(request)
        if not session: return _error("unauthorized", 401)
        request["blin_session"] = session
        return await handler(request)

    app = web.Application(middlewares=[cors, auth])

    async def health(request): return web.json_response({"ok": True, "service": "blin-bot", "api_version": 3})

    async def auth_discord(request):
        if not config.DISCORD_CLIENT_ID or not config.DISCORD_REDIRECT_URI: return _error("Discord OAuth2 is not configured", 503)
        state = secrets.token_urlsafe(32); OAUTH_STATES.add(state)
        params = {"client_id": config.DISCORD_CLIENT_ID, "response_type": "code", "redirect_uri": config.DISCORD_REDIRECT_URI, "scope": "identify guilds", "state": state}
        return web.HTTPFound("https://discord.com/oauth2/authorize?" + urlencode(params))

    async def auth_callback(request):
        state, code = request.query.get("state"), request.query.get("code")
        if not state or not code or state not in OAUTH_STATES: return _error("invalid_oauth_state", 400)
        OAUTH_STATES.remove(state)
        if not config.DISCORD_CLIENT_ID or not config.DISCORD_CLIENT_SECRET or not config.DISCORD_REDIRECT_URI: return _error("Discord OAuth2 is not configured", 503)
        async with ClientSession() as session:
            async with session.post("https://discord.com/api/oauth2/token", data={"client_id": config.DISCORD_CLIENT_ID, "client_secret": config.DISCORD_CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": config.DISCORD_REDIRECT_URI}, headers={"Content-Type": "application/x-www-form-urlencoded"}) as response:
                if response.status != 200: return _error("oauth_token_exchange_failed", 502)
                token_data = await response.json()
            access_token = token_data.get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}
            async with session.get("https://discord.com/api/users/@me", headers=headers) as response:
                if response.status != 200: return _error("oauth_user_failed", 502)
                user = await response.json()
            async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as response:
                if response.status != 200: return _error("oauth_guilds_failed", 502)
                user_guilds = await response.json()
        allowed = {str(g["id"]): int(g.get("permissions", "0")) for g in user_guilds if int(g.get("permissions", "0")) & (MANAGE_GUILD | ADMINISTRATOR)}
        session_id = secrets.token_urlsafe(32); SESSIONS[session_id] = {"user": user, "guild_permissions": allowed}
        target = os.getenv("BLIN_DASHBOARD_URL", "/dashboard.html")
        response = web.HTTPFound(target)
        response.set_cookie("blin_session", session_id, httponly=True, secure=True, samesite="Lax", max_age=86400)
        return response

    async def auth_me(request):
        session = request["blin_session"]
        return web.json_response({"user": session.get("user"), "guild_ids": list(session.get("guild_permissions", {}).keys())})

    async def auth_logout(request):
        token = request.cookies.get("blin_session")
        if token: SESSIONS.pop(token, None)
        response = web.json_response({"ok": True}); response.del_cookie("blin_session"); return response

    async def guilds(request):
        session = request["blin_session"]
        return web.json_response([{"id": g.id, "name": g.name, "member_count": g.member_count} for g in bot.guilds if database.guild_enabled(g.id) and _can_manage_guild(session, g.id)])

    async def objects(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        return web.json_response({"roles": [{"id": r.id, "name": r.name, "position": r.position, "managed": r.managed} for r in guild.roles if not r.managed], "categories": [{"id": c.id, "name": c.name, "position": c.position} for c in guild.categories], "channels": [{"id": c.id, "name": c.name, "type": str(c.type), "category_id": c.category_id} for c in guild.channels if not isinstance(c, discord.CategoryChannel)]})

    async def cfg(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        if request.method == "GET": return web.json_response(database.get_config(guild.id))
        try: value = await request.json()
        except Exception: return _error("invalid_json")
        if not isinstance(value, dict): return _error("config_must_be_object")
        database.set_config(guild.id, value); return web.json_response({"ok": True, "config": value})

    async def modules(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        if request.method == "GET": return web.json_response(database.get_modules(guild.id))
        try:
            body = await request.json(); database.set_module(guild.id, body["module"], bool(body.get("enabled", True)), body.get("settings", {}))
        except (KeyError, ValueError, TypeError): return _error("invalid_module_payload")
        return web.json_response({"ok": True, "modules": database.get_modules(guild.id)})

    async def contracts(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        if request.method == "GET": return web.json_response(database.list_contracts(guild.id))
        try: block = await request.json()
        except Exception: return _error("invalid_json")
        error = _validate_contract(block)
        if error: return _error(error)
        return web.json_response({"id": database.save_contract(guild.id, block)}, status=201)

    async def publish_contract(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        try: contract_id = int(request.match_info["contract_id"])
        except ValueError: return _error("invalid_contract_id")
        block = database.get_contract(guild.id, contract_id)
        if not block: return _error("contract_not_found", 404)
        channel = guild.get_channel(block.get("channel_id")) if block.get("channel_id") else None
        if not isinstance(channel, discord.TextChannel): return _error("publish_channel_not_configured")
        await publish_block(channel, block); return web.json_response({"ok": True, "channel_id": channel.id})

    async def provision(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        try: blueprint = await request.json()
        except Exception: return _error("invalid_json")
        try: created = await provision_guild(guild, blueprint)
        except (ValueError, discord.Forbidden) as exc: return _error(str(exc), 403 if isinstance(exc, discord.Forbidden) else 400)
        save_provisioning_result(guild.id, created); return web.json_response({"ok": True, "created": created})

    async def warnings(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        raw = request.query.get("user_id")
        try: target_id = int(raw) if raw else None
        except ValueError: return _error("invalid_user_id")
        return web.json_response(database.list_warnings(guild.id, target_id))

    async def reaction_roles(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        if request.method == "GET": return web.json_response(database.list_reaction_role_configs(guild.id))
        try:
            value = await request.json(); buttons = value.get("buttons", [])
            if not isinstance(value, dict) or not isinstance(buttons, list) or len(buttons) > 20: return _error("invalid_reaction_role_payload")
            database.save_reaction_role_config(guild.id, value)
        except Exception: return _error("invalid_reaction_role_payload")
        return web.json_response({"ok": True}, status=201)

    async def consent(request):
        guild = _guild(bot, request)
        if not guild: return _error("guild_not_found", 404)
        if not _can_manage_guild(request["blin_session"], guild.id): return _error("forbidden", 403)
        try: body = await request.json(); user_id = int(body["user_id"]); enabled = bool(body["enabled"])
        except (KeyError, TypeError, ValueError): return _error("invalid_consent_payload")
        database.set_consent(guild.id, user_id, enabled); return web.json_response({"ok": True, "enabled": enabled})

    app.add_routes([
        web.get("/health", health), web.get("/auth/discord", auth_discord), web.get("/auth/callback", auth_callback), web.get("/api/me", auth_me), web.post("/api/logout", auth_logout),
        web.get("/api/guilds", guilds), web.get("/api/guilds/{guild_id}/objects", objects), web.get("/api/guilds/{guild_id}/config", cfg), web.put("/api/guilds/{guild_id}/config", cfg),
        web.get("/api/guilds/{guild_id}/modules", modules), web.put("/api/guilds/{guild_id}/modules", modules), web.get("/api/guilds/{guild_id}/contracts", contracts), web.post("/api/guilds/{guild_id}/contracts", contracts),
        web.post("/api/guilds/{guild_id}/contracts/{contract_id}/publish", publish_contract), web.post("/api/guilds/{guild_id}/provision", provision), web.get("/api/guilds/{guild_id}/warnings", warnings),
        web.get("/api/guilds/{guild_id}/reaction-roles", reaction_roles), web.post("/api/guilds/{guild_id}/reaction-roles", reaction_roles), web.put("/api/guilds/{guild_id}/consent", consent),
    ])
    return app


async def start_api(bot):
    runner = web.AppRunner(create_app(bot)); await runner.setup(); await web.TCPSite(runner, config.API_HOST, config.API_PORT).start(); return runner
