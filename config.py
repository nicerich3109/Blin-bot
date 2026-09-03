import os

# Secrets and infrastructure settings only. Discord object IDs belong to the
# per-guild database configuration and are selected through the Dashboard.
TOKEN = os.getenv("DISCORD_TOKEN", "")
DATA_FILE = os.getenv("BLIN_LEGACY_DATA_FILE", "data.json")
LOG_FILE = os.getenv("BLIN_LOG_FILE", "bot.log")
DB_PATH = os.getenv("BLIN_DB_PATH", "blin.sqlite3")
API_HOST = os.getenv("BLIN_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("BLIN_API_PORT", "8080"))
API_SECRET = os.getenv("BLIN_API_SECRET", "")
API_ALLOWED_ORIGINS = os.getenv("BLIN_API_ALLOWED_ORIGINS", "")

# Reserved for the Dashboard OAuth2 backend. The client secret must only live
# on the server; it must never be shipped to browser JavaScript.
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "")

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
