import os

# Secrets and infrastructure settings only. Discord object IDs belong to the
# per-guild database configuration and are selected through the Dashboard.
TOKEN = os.getenv("DISCORD_TOKEN", "")
DATA_FILE = os.getenv("BLIN_LEGACY_DATA_FILE", "/app/data/data.json")
LOG_FILE = os.getenv("BLIN_LOG_FILE", "/app/data/bot.log")
DB_PATH = os.getenv("BLIN_DB_PATH", "/app/data/blin.sqlite3")
API_HOST = os.getenv("BLIN_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("BLIN_API_PORT", "3000")))
API_SECRET = os.getenv("BLIN_API_SECRET", "")
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
