# -*- coding: utf-8 -*-
"""
Центральные переключатели функций Blin-bot.

Меняйте только значения True / False в этом файле, чтобы включать или
выключать функции без изменения основной логики бота.

После изменения файла перезапустите бота.

Коды серверов:
    DN  = Denver
    PHX = Phoenix

Пример:
    FAMILY_APPLICATIONS["DN"] = False   # заявки Denver отключены
    FAMILY_APPLICATIONS["PHX"] = True   # заявки Phoenix включены
"""

# ========================= ЗАЯВКИ В СЕМЬЮ ================================

FAMILY_APPLICATIONS = {
    "DN": True,   # Denver
    "PHX": True,  # Phoenix
}

# ============================== ОТПУСК ====================================

VACATIONS = {
    "DN": True,   # Denver
    "PHX": True,  # Phoenix
}


def is_family_enabled(server: str) -> bool:
    """Проверяет, включены ли заявки в семью для указанного сервера."""
    return bool(FAMILY_APPLICATIONS.get(server, False))


def is_vacation_enabled(server: str) -> bool:
    """Проверяет, включён ли отпуск для указанного сервера."""
    return bool(VACATIONS.get(server, False))
