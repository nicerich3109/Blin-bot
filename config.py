import os
import base64

# Secrets and infrastructure settings only. Discord object IDs belong to the
# per-guild database configuration and are selected through the Dashboard.
TOKEN = os.getenv("DISCORD_TOKEN", "")
DATA_FILE = os.getenv("BLIN_LEGACY_DATA_FILE", "/app/data/data.json")
LOG_FILE = os.getenv("BLIN_LOG_FILE", "/app/data/bot.log")
DB_PATH = os.getenv("BLIN_DB_PATH", "/app/data/blin.sqlite3")
API_HOST = os.getenv("BLIN_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("BLIN_API_PORT", "3000")))
API_SECRET = os.getenv("BLIN_API_SECRET", "")

# The dashboard is hosted on GitHub Pages. Set a safe default so browser
# requests to the separate API are accepted without requiring an environment
# variable on every deployment. A custom domain can still override this.
os.environ.setdefault("BLIN_API_ALLOWED_ORIGINS", "https://nicerich3109.github.io")
API_ALLOWED_ORIGINS = os.getenv("BLIN_API_ALLOWED_ORIGINS", "")

# Dashboard OAuth2. Keep the client secret server-side only.
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "")
# Site administrators are configured on the backend, never in frontend JS.
SITE_ADMIN_IDS = {
    value.strip() for value in os.getenv("BLIN_SITE_ADMIN_IDS", "").split(",") if value.strip()
}

VACATION_TIMEZONE = os.getenv("BLIN_TIMEZONE", "Europe/Moscow")
JOIN_APPLICATION_COOLDOWN_SECONDS = int(os.getenv("BLIN_JOIN_COOLDOWN", "120"))

RECRUIT_INFO_TEXT = "Мы подарим тебе адекватную компанию, нацеленную как на улучшение самого себя, так и на улучшение и создание контента в игре.\n\nВыбери сервер, чтобы подать заявку на вступление!"
VACATION_INFO_TEXT = "Откинули в бан? Или уезжаете в РЛ по делам? Подай заявку, чтобы мы всегда знали, что ты не пропал.\n\nНажми на кнопку ниже, чтобы подать заявку на отпуск!"

MODULES = (
    "applications",
    "vacations",
    "contracts",
    "discipline",
    "dm_notifications",
    "reaction_roles",
)

# Discord's current server-to-server OAuth2 documentation authenticates the
# token endpoint with HTTP Basic (client_id:client_secret). The dashboard API
# historically supplied these two values in the form body. Normalize that
# request here so the deployed API follows Discord's documented flow without
# exposing the secret to the frontend.
try:
    import aiohttp

    _aiohttp_client_session_post = aiohttp.ClientSession.post

    async def _blin_oauth_post(self, url, *args, **kwargs):
        if str(url).rstrip("/") == "https://discord.com/api/oauth2/token":
            data = kwargs.get("data")
            if isinstance(data, dict):
                data = dict(data)
                data.pop("client_id", None)
                data.pop("client_secret", None)
                kwargs["data"] = data
            headers = dict(kwargs.get("headers") or {})
            credentials = f"{DISCORD_CLIENT_ID}:{DISCORD_CLIENT_SECRET}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            kwargs["headers"] = headers
        return await _aiohttp_client_session_post(self, url, *args, **kwargs)

    aiohttp.ClientSession.post = _blin_oauth_post
except Exception:
    # aiohttp is a runtime dependency; configuration import must remain safe
    # for tools/tests that load config without the HTTP stack installed.
    pass
