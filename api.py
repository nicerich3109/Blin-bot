# -*- coding: utf-8 -*-
"""Web configuration API for the future Blin Dashboard."""
from aiohttp import web
import discord
import config, database, utils

def _auth(request):
    return bool(config.API_SECRET) and request.headers.get("X-Blin-Secret") == config.API_SECRET

def create_app(bot):
    app=web.Application()
    async def guard(request):
        if not _auth(request): return web.json_response({"error":"unauthorized"},status=401)
    async def health(request): return web.json_response({"ok":True,"service":"blin-bot"})
    async def guilds(request):
        if (x:=await guard(request)): return x
        return web.json_response([{"id":g.id,"name":g.name} for g in bot.guilds])
    async def objects(request):
        if (x:=await guard(request)): return x
        g=bot.get_guild(int(request.match_info["guild_id"]))
        if not g:return web.json_response({"error":"guild_not_found"},status=404)
        return web.json_response({"roles":[{"id":r.id,"name":r.name,"position":r.position,"managed":r.managed} for r in g.roles],"categories":[{"id":c.id,"name":c.name,"position":c.position} for c in g.categories],"channels":[{"id":c.id,"name":c.name,"type":str(c.type),"category_id":c.category_id} for c in g.channels if not isinstance(c,discord.CategoryChannel)]})
    async def cfg(request):
        if (x:=await guard(request)): return x
        gid=int(request.match_info["guild_id"])
        if request.method=="GET": return web.json_response(database.get_config(gid))
        value=await request.json(); database.set_config(gid,value); utils.refresh_runtime_config(gid); return web.json_response({"ok":True,"config":value})
    async def modules(request):
        if (x:=await guard(request)): return x
        gid=int(request.match_info["guild_id"])
        if request.method=="GET": return web.json_response(database.get_modules(gid))
        b=await request.json(); database.set_module(gid,b["module"],bool(b.get("enabled",True)),b.get("settings",{})); return web.json_response({"ok":True})
    async def contracts(request):
        if (x:=await guard(request)): return x
        gid=int(request.match_info["guild_id"])
        if request.method=="GET": return web.json_response(database.list_contracts(gid))
        return web.json_response({"id":database.save_contract(gid,await request.json())},status=201)
    async def consent(request):
        if (x:=await guard(request)): return x
        b=await request.json(); database.set_consent(int(request.match_info["guild_id"]),int(b["user_id"]),bool(b["enabled"])); return web.json_response({"ok":True})
    app.add_routes([web.get("/health",health),web.get("/api/guilds",guilds),web.get("/api/guilds/{guild_id}/objects",objects),web.get("/api/guilds/{guild_id}/config",cfg),web.put("/api/guilds/{guild_id}/config",cfg),web.get("/api/guilds/{guild_id}/modules",modules),web.put("/api/guilds/{guild_id}/modules",modules),web.get("/api/guilds/{guild_id}/contracts",contracts),web.post("/api/guilds/{guild_id}/contracts",contracts),web.put("/api/guilds/{guild_id}/consent",consent)])
    return app

async def start_api(bot):
    runner=web.AppRunner(create_app(bot)); await runner.setup(); await web.TCPSite(runner,config.API_HOST,config.API_PORT).start(); return runner
