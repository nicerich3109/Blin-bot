import os

# Runtime-only settings. Discord object IDs are stored in SQLite and edited via the web API.
TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("BLIN_GUILD_ID", "0")) or None
DATA_FILE = os.getenv("BLIN_LEGACY_DATA_FILE", "data.json")
LOG_FILE = os.getenv("BLIN_LOG_FILE", "bot.log")
DB_PATH = os.getenv("BLIN_DB_PATH", "blin.sqlite3")
API_HOST = os.getenv("BLIN_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("BLIN_API_PORT", "8080"))
API_SECRET = os.getenv("BLIN_API_SECRET", "")
VACATION_TIMEZONE = os.getenv("BLIN_TIMEZONE", "Europe/Moscow")
JOIN_APPLICATION_COOLDOWN_SECONDS = int(os.getenv("BLIN_JOIN_COOLDOWN", "120"))

RECRUIT_INFO_TEXT = "Мы подарим тебе адекватную компанию, нацеленную как на улучшение самого себя, так и на улучшение и создание контента в игре.\n\nВыбери сервер, чтобы подать заявку на вступление!"
VACATION_INFO_TEXT = "Откинули в бан? Или уезжаете в РЛ по делам? Подай заявку, чтобы мы всегда знали, что ты не пропал.\n\nНажми на кнопку ниже, чтобы подать заявку на отпуск!"

# Only logical module names live in source code; their Discord objects are selected at runtime.
MODULES = ("applications", "vacations", "contracts", "discipline", "dm_notifications", "reaction_roles")
