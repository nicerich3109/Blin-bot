# -*- coding: utf-8 -*-
"""Хранилище согласий на системные личные уведомления."""
import json, os, asyncio
CONSENT_FILE = "consents.json"
_lock = asyncio.Lock()
def _load():
    if not os.path.exists(CONSENT_FILE): return {}
    try:
        with open(CONSENT_FILE, "r", encoding="utf-8") as f: data=json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError): return {}
CONSENTS = _load()
def has_consent(user_id): return CONSENTS.get(str(user_id)) is True
async def set_consent(user_id, value):
    async with _lock:
        CONSENTS[str(user_id)] = bool(value)
        tmp=CONSENT_FILE+".tmp"
        with open(tmp,"w",encoding="utf-8") as f: json.dump(CONSENTS,f,ensure_ascii=False,indent=2)
        os.replace(tmp,CONSENT_FILE)
