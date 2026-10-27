# -*- coding: utf-8 -*-
"""
Центральные переключатели функций Blin-bot.

Меняйте только значения True / False в этом файле, чтобы включать или
выключать функции без изменения основной логики бота.

После изменения файла перезапустите бота.

Коды серверов:
    CM  = Crime
    ST = State

Пример:
    FAMILY_APPLICATIONS["CM"] = False   # заявки Crime отключены
    FAMILY_APPLICATIONS["ST"] = True   # заявки State включены
"""

# ========================= ЗАЯВКИ В СЕМЬЮ ================================

FAMILY_APPLICATIONS = {
    "CM": True,   # Crime
    "ST": True,  # State
}

# ============================== ОТПУСК ====================================

VACATIONS = {
    "CM": True,   # Crime
    "ST": True,  # State
}


def is_family_enabled(server: str) -> bool:
    """Проверяет, включены ли заявки в семью для указанного сервера."""
    return bool(FAMILY_APPLICATIONS.get(server, False))


def is_vacation_enabled(server: str) -> bool:
    """Проверяет, включён ли отпуск для указанного сервера."""
    return bool(VACATIONS.get(server, False))
