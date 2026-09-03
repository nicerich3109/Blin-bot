# -*- coding: utf-8 -*-
"""SQLite configuration/data layer. Discord IDs are runtime configuration."""
import json, os, sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("BLIN_DB_PATH", "blin.sqlite3"))

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS guilds(guild_id INTEGER PRIMARY KEY,name TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS guild_config(guild_id INTEGER PRIMARY KEY REFERENCES guilds(guild_id) ON DELETE CASCADE,config_json TEXT NOT NULL DEFAULT '{}',updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS modules(guild_id INTEGER NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,module TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,settings_json TEXT NOT NULL DEFAULT '{}',PRIMARY KEY(guild_id,module));
        CREATE TABLE IF NOT EXISTS consents(guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,dm_notifications INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(guild_id,user_id));
        CREATE TABLE IF NOT EXISTS contracts(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,block_json TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS disciplinary_warnings(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,target_id INTEGER NOT NULL,issuer_id INTEGER NOT NULL,reason TEXT NOT NULL,work_off TEXT NOT NULL DEFAULT '',level INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS reaction_roles(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,config_json TEXT NOT NULL);
        """)

def register_guild(guild_id:int,name:str):
    init_db()
    with connect() as db:
        db.execute("INSERT INTO guilds(guild_id,name) VALUES(?,?) ON CONFLICT(guild_id) DO UPDATE SET name=excluded.name,updated_at=CURRENT_TIMESTAMP",(guild_id,name))
        db.execute("INSERT OR IGNORE INTO guild_config(guild_id) VALUES(?)",(guild_id,))
        for m in ("applications","vacations","contracts","discipline","dm_notifications","reaction_roles"):
            db.execute("INSERT OR IGNORE INTO modules(guild_id,module) VALUES(?,?)",(guild_id,m))

def get_config(guild_id:int)->dict[str,Any]:
    with connect() as db:
        row=db.execute("SELECT config_json FROM guild_config WHERE guild_id=?",(guild_id,)).fetchone()
        return json.loads(row["config_json"]) if row else {}

def set_config(guild_id:int,value:dict[str,Any]):
    with connect() as db:
        db.execute("UPDATE guild_config SET config_json=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=?",(json.dumps(value,ensure_ascii=False),guild_id))

def get_modules(guild_id:int):
    with connect() as db:
        return {r["module"]:{"enabled":bool(r["enabled"]),"settings":json.loads(r["settings_json"])} for r in db.execute("SELECT * FROM modules WHERE guild_id=?",(guild_id,))}

def set_module(guild_id:int,module:str,enabled:bool,settings:dict|None=None):
    with connect() as db:
        db.execute("INSERT INTO modules(guild_id,module,enabled,settings_json) VALUES(?,?,?,?) ON CONFLICT(guild_id,module) DO UPDATE SET enabled=excluded.enabled,settings_json=excluded.settings_json",(guild_id,module,int(enabled),json.dumps(settings or {},ensure_ascii=False)))

def set_consent(guild_id:int,user_id:int,enabled:bool):
    with connect() as db:
        db.execute("INSERT INTO consents(guild_id,user_id,dm_notifications) VALUES(?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET dm_notifications=excluded.dm_notifications,updated_at=CURRENT_TIMESTAMP",(guild_id,user_id,int(enabled)))

def has_consent(guild_id:int,user_id:int)->bool:
    with connect() as db:
        r=db.execute("SELECT dm_notifications FROM consents WHERE guild_id=? AND user_id=?",(guild_id,user_id)).fetchone()
        return bool(r and r["dm_notifications"])

def add_warning(guild_id,target_id,issuer_id,reason,work_off,level):
    with connect() as db: db.execute("INSERT INTO disciplinary_warnings(guild_id,target_id,issuer_id,reason,work_off,level) VALUES(?,?,?,?,?,?)",(guild_id,target_id,issuer_id,reason,work_off,level))

def warning_level(guild_id,target_id):
    with connect() as db:
        r=db.execute("SELECT MAX(level) level FROM disciplinary_warnings WHERE guild_id=? AND target_id=?",(guild_id,target_id)).fetchone()
        return int(r["level"] or 0)

def save_contract(guild_id,block):
    with connect() as db:
        r=db.execute("INSERT INTO contracts(guild_id,block_json) VALUES(?,?)",(guild_id,json.dumps(block,ensure_ascii=False)))
        return r.lastrowid

def list_contracts(guild_id):
    with connect() as db:
        return [{"id":r["id"],**json.loads(r["block_json"])} for r in db.execute("SELECT id,block_json FROM contracts WHERE guild_id=? ORDER BY id",(guild_id,))]
