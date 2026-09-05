# -*- coding: utf-8 -*-
"""Dashboard API: Discord OAuth2 sessions + per-guild runtime configuration."""
import os
import secrets
import logging
from urllib.parse import urlencode

import discord
from aiohttp import web, ClientSession, BasicAuth

import config
import database
import storage
from provisioning import provision_guild, save_provisioning_result
from contracts import publish_block
from applications import JoinInfoView
from vacations import refresh_vacation_message
from reaction_roles import RoleButtonView

logger = logging.getLogger("blin_bot.dashboard")
OAUTH_STATES = set(); SESSIONS = {}; MANAGE_GUILD = 1 << 5; ADMINISTRATOR = 1 << 3


def _auth(request):
    if config.API_SECRET and request.headers.get("X-Blin-Secret") == config.API_SECRET: return {"dev": True, "user": {"id": "dev"}}
    return SESSIONS.get(request.cookies.get("blin_session"))

def _guild(bot, request):
    try: guild_id=int(request.match_info["guild_id"])
    except (KeyError,TypeError,ValueError): return None
    return bot.get_guild(guild_id)

def _error(message,status=400): return web.json_response({"error":message},status=status)
def _is_site_admin(session):
    if not session or session.get("dev"): return bool(session and session.get("dev"))
    return str((session.get("user") or {}).get("id","")) in config.SITE_ADMIN_IDS

def _can_manage_guild(session,guild_id):
    if session and session.get("dev"): return True
    if not session: return False
    permissions=int(session.get("guild_permissions",{}).get(str(guild_id),0))
    return bool(permissions & (MANAGE_GUILD|ADMINISTRATOR))

def _validate_contract(block):
    if not isinstance(block,dict): return "contract must be an object"
    buttons=block.get("buttons",[])
    if not isinstance(buttons,list) or len(buttons)>20: return "at most 20 buttons are allowed"
    for button in buttons:
        if not isinstance(button,dict): return "button must be an object"
        options=button.get("options",[])
        if not isinstance(options,list) or len(options)>10: return "at most 10 options are allowed per button"
        for option in options:
            if not isinstance(option,dict): return "option must be an object"
            fields=option.get("fields",[])
            if not isinstance(fields,list) or len(fields)>5: return "at most 5 modal fields are allowed per option"
    return None

async def _upsert_message(channel,store_key,*,content=None,embed=None,embeds=None,view=None):
    messages=storage.DATA.setdefault("persistent_messages",{}); stored_id=messages.get(store_key); message=None
    if stored_id:
        try: message=await channel.fetch_message(int(stored_id))
        except (discord.NotFound,discord.Forbidden,discord.HTTPException): message=None
    kwargs={"content":content,"view":view}
    if embeds is not None: kwargs["embeds"]=embeds
    else: kwargs["embed"]=embed
    if message:
        try: await message.edit(**kwargs)
        except (discord.NotFound,discord.Forbidden,discord.HTTPException): message=None
    if message is None: message=await channel.send(**kwargs)
    messages[store_key]=message.id; await storage.persist(); return message

def _text_channel(guild,raw_id):
    if not raw_id: return None
    try: channel=guild.get_channel(int(raw_id))
    except (TypeError,ValueError): return None
    return channel if isinstance(channel,(discord.TextChannel,discord.NewsChannel)) else None

async def _publish_applications(guild):
    raw=database.get_config(guild.id); channel=_text_channel(guild,raw.get("recruit_info_channel"))
    if channel is None: raise ValueError("publish_channel_not_configured")
    embed=discord.Embed(title="Вступление в компанию",description=raw.get("join_info_text") or config.RECRUIT_INFO_TEXT,color=discord.Color.blurple())
    return await _upsert_message(channel,f"recruit_info_{guild.id}",embeds=[embed],view=JoinInfoView(database.server_configs(guild.id))),channel

async def _publish_reaction(guild,config_id):
    item=next((x for x in database.list_reaction_role_configs(guild.id) if int(x.get("id",-1))==config_id),None)
    if not item: raise LookupError("reaction_role_not_found")
    channel=_text_channel(guild,item.get("channel_id"))
    if channel is None: raise ValueError("publish_channel_not_configured")
    embed=None
    if item.get("image") or item.get("text"):
        embed=discord.Embed(description=item.get("text") or "")
        if item.get("name"): embed.title=str(item["name"])[:256]
        if item.get("image"): embed.set_image(url=item["image"])
    view=RoleButtonView(guild.id,item.get("buttons",[])[:20],config_id)
    return await _upsert_message(channel,f"reaction_roles_{guild.id}_{config_id}",content=None if embed else item.get("text"),embed=embed,view=view),channel

def create_app(bot):
    origins={x.strip() for x in os.getenv("BLIN_API_ALLOWED_ORIGINS","").split(",") if x.strip()}
    @web.middleware
    async def cors(request,handler):
        if request.method=="OPTIONS": response=web.Response(status=204)
        else: response=await handler(request)
        origin=request.headers.get("Origin")
        if origin and origin in origins:
            response.headers["Access-Control-Allow-Origin"]=origin; response.headers["Access-Control-Allow-Credentials"]="true"; response.headers["Vary"]="Origin"; response.headers["Access-Control-Allow-Headers"]="Content-Type, X-Blin-Secret"; response.headers["Access-Control-Allow-Methods"]="GET, PUT, POST, OPTIONS"
        return response
    @web.middleware
    async def auth(request,handler):
        public={"/","/health","/auth/discord","/auth/callback"}
        if request.path in public or request.method=="OPTIONS": return await handler(request)
        session=_auth(request)
        if not session: return _error("unauthorized",401)
        request["blin_session"]=session; return await handler(request)
    app=web.Application(middlewares=[cors,auth])
    async def root(request): return web.json_response({"service":"Blin Bot API","status":"online","api_version":11,"dashboard":"ready","health":"/health"})
    async def health(request): return web.json_response({"ok":True,"service":"blin-bot","api_version":11})
    async def auth_discord(request):
        if not config.DISCORD_CLIENT_ID or not config.DISCORD_REDIRECT_URI: return _error("Discord OAuth2 is not configured",503)
        state=secrets.token_urlsafe(32); OAUTH_STATES.add(state); params={"client_id":config.DISCORD_CLIENT_ID,"response_type":"code","redirect_uri":config.DISCORD_REDIRECT_URI,"scope":"identify guilds","state":state}; response=web.HTTPFound("https://discord.com/oauth2/authorize?"+urlencode(params)); response.set_cookie("blin_oauth_state",state,httponly=True,secure=True,samesite="None",max_age=600); return response
    async def auth_callback(request):
        query_state=request.query.get("state"); cookie_state=request.cookies.get("blin_oauth_state"); code=request.query.get("code"); state=query_state or cookie_state
        if not code or not state or state not in OAUTH_STATES: return _error("invalid_oauth_state",400)
        if query_state and cookie_state and query_state!=cookie_state: return _error("invalid_oauth_state",400)
        OAUTH_STATES.remove(state)
        if not config.DISCORD_CLIENT_ID or not config.DISCORD_CLIENT_SECRET or not config.DISCORD_REDIRECT_URI: return _error("Discord OAuth2 is not configured",503)
        try:
            async with ClientSession() as session:
                async with session.request("POST","https://discord.com/api/v10/oauth2/token",data={"grant_type":"authorization_code","code":code,"redirect_uri":config.DISCORD_REDIRECT_URI},headers={"Content-Type":"application/x-www-form-urlencoded"},auth=BasicAuth(config.DISCORD_CLIENT_ID,config.DISCORD_CLIENT_SECRET)) as response:
                    if response.status!=200:
                        body=await response.text(); logger.error("Discord OAuth token exchange failed: status=%s body=%s redirect_uri=%s client_id=%s",response.status,body[:1000],config.DISCORD_REDIRECT_URI,config.DISCORD_CLIENT_ID); return _error("oauth_token_exchange_failed",502)
                    token_data=await response.json()
                access_token=token_data.get("access_token")
                if not access_token: return _error("oauth_token_exchange_failed",502)
                headers={"Authorization":f"Bearer {access_token}"}
                async with session.get("https://discord.com/api/users/@me",headers=headers) as response:
                    if response.status!=200: return _error("oauth_user_failed",502)
                    user=await response.json()
                async with session.get("https://discord.com/api/users/@me/guilds",headers=headers) as response:
                    if response.status!=200: return _error("oauth_guilds_failed",502)
                    user_guilds=await response.json()
        except Exception: logger.exception("Unexpected Discord OAuth token exchange error"); return _error("oauth_token_exchange_failed",502)
        allowed={str(g["id"]):int(g.get("permissions","0")) for g in user_guilds if int(g.get("permissions","0"))&(MANAGE_GUILD|ADMINISTRATOR)}; session_id=secrets.token_urlsafe(32); SESSIONS[session_id]={"user":user,"guild_permissions":allowed}; response=web.HTTPFound(os.getenv("BLIN_DASHBOARD_URL","/dashboard.html")); response.set_cookie("blin_session",session_id,httponly=True,secure=True,samesite="None",max_age=86400); response.del_cookie("blin_oauth_state"); return response
    async def auth_me(request):
        session=request["blin_session"]; return web.json_response({"user":session.get("user"),"guild_ids":list(session.get("guild_permissions",{}).keys()),"site_admin":_is_site_admin(session)})
    async def auth_logout(request):
        token=request.cookies.get("blin_session")
        if token: SESSIONS.pop(token,None)
        response=web.json_response({"ok":True}); response.del_cookie("blin_session"); return response
    async def admin(request):
        session=request["blin_session"]
        if not _is_site_admin(session): return _error("forbidden",403)
        return web.json_response({"ok":True,"admin":{"user_id":str(session.get("user",{}).get("id","dev")),"name":session.get("user",{}).get("global_name") or session.get("user",{}).get("username") or "Developer"},"bot":{"online":not bot.is_closed(),"user_id":str(bot.user.id) if bot.user else None,"guild_count":len(bot.guilds)},"configuration":{"configured_admin_count":len(config.SITE_ADMIN_IDS),"api_version":11}})
    async def guilds(request):
        session=request["blin_session"]
        for g in bot.guilds:
            try: database.register_guild(g.id,g.name)
            except Exception: logger.exception("Не удалось зарегистрировать guild %s в БД",g.id)
        result=[{"id":str(g.id),"name":g.name,"member_count":g.member_count} for g in bot.guilds if database.guild_enabled(g.id) and _can_manage_guild(session,g.id)]; return web.json_response(result)
    async def objects(request):
        try: guild_id=int(request.match_info.get("guild_id"))
        except (TypeError,ValueError): return _error("invalid_guild_id",400)
        guild=bot.get_guild(guild_id)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        return web.json_response({"roles":[{"id":str(r.id),"name":r.name,"position":r.position,"managed":r.managed} for r in guild.roles if not r.managed],"categories":[{"id":str(c.id),"name":c.name,"position":c.position} for c in guild.categories],"channels":[{"id":str(c.id),"name":c.name,"type":str(c.type),"category_id":str(c.category_id) if c.category_id else None} for c in guild.channels if not isinstance(c,discord.CategoryChannel)]})
    async def cfg(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        if request.method=="GET": return web.json_response(database.get_config(guild.id))
        try: value=await request.json()
        except Exception: return _error("invalid_json")
        if not isinstance(value,dict): return _error("config_must_be_object")
        database.set_config(guild.id,value); return web.json_response({"ok":True,"config":value})
    async def modules(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        if request.method=="GET": return web.json_response(database.get_modules(guild.id))
        try: body=await request.json(); database.set_module(guild.id,body["module"],bool(body.get("enabled",True)),body.get("settings",{}))
        except (KeyError,ValueError,TypeError): return _error("invalid_module_payload")
        return web.json_response({"ok":True,"modules":database.get_modules(guild.id)})
    async def contracts(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        if request.method=="GET": return web.json_response(database.list_contracts(guild.id))
        try: block=await request.json()
        except Exception: return _error("invalid_json")
        error=_validate_contract(block)
        if error: return _error(error)
        return web.json_response({"id":database.save_contract(guild.id,block)},status=201)
    async def publish_contract(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        try: contract_id=int(request.match_info["contract_id"])
        except ValueError: return _error("invalid_contract_id")
        block=database.get_contract(guild.id,contract_id)
        if not block: return _error("contract_not_found",404)
        channel=_text_channel(guild,block.get("channel_id"))
        if channel is None: return _error("publish_channel_not_configured")
        message=await publish_block(channel,block,store=storage.DATA,store_key=f"contract_{guild.id}_{contract_id}"); await storage.persist(); return web.json_response({"ok":True,"channel_id":str(channel.id),"message_id":str(message.id)})
    async def publish_panel(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        try: body=await request.json()
        except Exception: body={}
        section=str(body.get("section","")).strip().lower()
        try:
            if section=="applications": message,channel=await _publish_applications(guild)
            elif section=="reaction_roles": message,channel=await _publish_reaction(guild,int(body.get("id")))
            elif section=="vacations":
                profile=str(body.get("profile") or "").strip()
                if not profile: return _error("profile_not_configured")
                p=database.get_server_config(guild.id,profile)
                if not p: return _error("profile_not_found",404)
                channel=_text_channel(guild,p.get("vacation_channel"))
                if channel is None: return _error("publish_channel_not_configured")
                await refresh_vacation_message(guild,profile); stored_id=storage.DATA.get("persistent_messages",{}).get(f"vacation_info_{profile}"); message=await channel.fetch_message(int(stored_id)) if stored_id else None
            else: return _error("unsupported_publish_section")
        except ValueError as exc: return _error(str(exc))
        except LookupError as exc: return _error(str(exc),404)
        except discord.Forbidden: return _error("bot_missing_permission",403)
        except discord.HTTPException as exc: logger.exception("Dashboard publish failed guild=%s section=%s",guild.id,section); return _error(f"discord_error_{exc.status}",502)
        return web.json_response({"ok":True,"section":section,"channel_id":str(channel.id),"message_id":str(message.id) if message else None})
    async def provision(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        try: blueprint=await request.json()
        except Exception: return _error("invalid_json")
        try: created=await provision_guild(guild,blueprint)
        except (ValueError,discord.Forbidden) as exc: return _error(str(exc),403 if isinstance(exc,discord.Forbidden) else 400)
        save_provisioning_result(guild.id,created); return web.json_response({"ok":True,"created":created})
    async def warnings(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        raw=request.query.get("user_id")
        try: target_id=int(raw) if raw else None
        except ValueError: return _error("invalid_user_id")
        return web.json_response(database.list_warnings(guild.id,target_id))
    async def reaction_roles(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        if request.method=="GET": return web.json_response(database.list_reaction_role_configs(guild.id))
        try:
            value=await request.json(); buttons=value.get("buttons",[])
            if not isinstance(value,dict) or not isinstance(buttons,list) or len(buttons)>20: return _error("invalid_reaction_role_payload")
            database.save_reaction_role_config(guild.id,value)
        except Exception: return _error("invalid_reaction_role_payload")
        return web.json_response({"ok":True},status=201)
    async def consent(request):
        guild=_guild(bot,request)
        if not guild: return _error("guild_not_found",404)
        if not _can_manage_guild(request["blin_session"],guild.id): return _error("forbidden",403)
        try: body=await request.json(); user_id=int(body["user_id"]); enabled=bool(body["enabled"])
        except (KeyError,TypeError,ValueError): return _error("invalid_consent_payload")
        database.set_consent(guild.id,user_id,enabled); return web.json_response({"ok":True,"enabled":enabled})
    app.add_routes([
        web.get("/",root),web.get("/health",health),web.get("/auth/discord",auth_discord),web.get("/auth/callback",auth_callback),web.get("/api/me",auth_me),web.post("/api/logout",auth_logout),web.get("/api/admin",admin),
        web.get("/api/guilds",guilds),web.get("/api/guilds/{guild_id}/objects",objects),web.get("/api/guilds/{guild_id}/config",cfg),web.put("/api/guilds/{guild_id}/config",cfg),
        web.get("/api/guilds/{guild_id}/modules",modules),web.put("/api/guilds/{guild_id}/modules",modules),web.get("/api/guilds/{guild_id}/contracts",contracts),web.post("/api/guilds/{guild_id}/contracts",contracts),
        web.post("/api/guilds/{guild_id}/contracts/{contract_id}/publish",publish_contract),web.post("/api/guilds/{guild_id}/publish",publish_panel),web.post("/api/guilds/{guild_id}/provision",provision),web.get("/api/guilds/{guild_id}/warnings",warnings),
        web.get("/api/guilds/{guild_id}/reaction-roles",reaction_roles),web.post("/api/guilds/{guild_id}/reaction-roles",reaction_roles),web.post("/api/guilds/{guild_id}/consent",consent)])
    return app

async def start_api(bot):
    runner=web.AppRunner(create_app(bot)); await runner.setup(); await web.TCPSite(runner,config.API_HOST,config.API_PORT).start(); return runner
