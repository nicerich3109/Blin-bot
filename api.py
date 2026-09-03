# -*- coding: utf-8 -*-
"""Small configuration API for the future Blin web dashboard.

Authentication is deliberately via an environment secret for now. Discord OAuth2
will replace it when the website is connected. No Discord IDs are hardcoded here.
"""
from aiohttp import web
import config, database, utils


def _auth(request):
    secret = config.API_SECRET
    return bool(secret) and request.headers.get("X-Blin-Secret") == secret


def create_app(bot):
    app = web.Application()

    async def health(request): return web.json_response({"ok": True, "service": "blin-bot"})

    async def guilds(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"}, status=401)
        return web.json_response([{"id":g.id,"name":g.name} for g in bot.guilds])

    async def discord_objects(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"}, status=401)
        gid=int(request.match_info["guild_id"]); guild=bot.get_guild(gid)
        if not guild: return web.json_response({"error":"guild_not_found"},status=404)
        return web.json_response({
            "roles":[{"id":r.id,"name":r.name,"position":r.position,"managed":r.managed} for r in guild.roles],
            "categories":[{"id":c.id,"name":c.name,"position":c.position} for c in guild.categories],
            "channels":[{"id":c.id,"name":c.name,"type":str(c.type),"category_id":c.category_id} for c in guild.channels if not isinstance(c, discord.CategoryChannel)]
        })

    async def get_config(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"},status=401)
        return web.json_response(database.get_config(int(request.match_info["guild_id"])))

    async def put_config(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"},status=401)
        gid=int(request.match_info["guild_id"]); value=await request.json(); database.set_config(gid,value); utils.refresh_runtime_config(gid)
        return web.json_response({"ok":True,"config":value})

    async def modules(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"},status=401)
        gid=int(request.match_info["guild_id"])
        if request.method=="GET": return web.json_response(database.get_modules(gid))
        body=await request.json(); database.set_module(gid,body["module"],bool(body.get("enabled",True)),body.get("settings",{})); return web.json_response({"ok":True})

    async def contracts(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"},status=401)
        gid=int(request.match_info["guild_id"])
        if request.method=="GET": return web.json_response(database.list_contracts(gid))
        cid=database.save_contract(gid,await request.json()); return web.json_response({"id":cid},status=201)

    async def consent(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"},status=401)
        body=await request.json(); database.set_consent(int(request.match_info["guild_id"]),int(body["user_id"]),bool(body["enabled"])); return web.json_response({"ok":True})

    app.add_routes([
        web.get("/health",health), web.get("/api/guilds",guilds),
        web.get("/api/guilds/{guild_id}/objects",discord_objects),
        web.get("/api/guilds/{guild_id}/config",get_config), web.put("/api/guilds/{guild_id}/config",put_config),
        web.get("/api/guilds/{guild_id}/modules",modules), web.put("/api/guilds/{guild_id}/modules",modules),
        web.get("/api/guilds/{guild_id}/contracts",contracts), web.post("/api/guilds/{guild_id}/contracts",contracts),
        web.put("/api/guilds/{guild_id}/consent",consent),
    ])
    return app

async def start_api(bot):
    runner=web.AppRunner(create_app(bot)); await runner.setup(); site=web.TCPSite(runner,config.API_HOST,config.API_PORT); await site.start(); return runner
