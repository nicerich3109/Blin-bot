# -*- coding: utf-8 -*-
"""
Переключатели функций Blin-bot.

Здесь можно включать/выключать отдельные функции без изменения основной
логики бота. После изменения значений перезапустите бота.

True  = функция включена
False = функция выключена

Заявки на вступление (семью) настраиваются отдельно для Denver/Phoenix.
Заявки на отпуск также настраиваются отдельно для Denver/Phoenix.
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
    """Возвращает True, если заявки в семью включены для указанного сервера."""
    return FAMILY_APPLICATIONS.get(server, False)


def is_vacation_enabled(server: str) -> bool:
    """Возвращает True, если отпуск включён для указанного сервера."""
    return VACATIONS.get(server, False)
