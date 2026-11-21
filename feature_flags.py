# -*- coding: utf-8 -*-
"""
Центральные переключатели функций Blin-bot.

Меняйте True / False, чтобы включать или выключать функции.
После изменения файла перезапустите бота.

Для контрактов:
    True  — уровень доступен участникам;
    False — уровень скрыт из меню выбора.
"""

# ========================= ЗАЯВКИ В СЕМЬЮ ================================

FAMILY_APPLICATIONS = {
    "CM": True,   # Crime
    "ST": True,   # State
}

# ============================== ОТПУСК ====================================

VACATIONS = {
    "CM": True,   # Crime
    "ST": True,   # State
}

# ======================== УРОВНИ КОНТРАКТОВ ==============================
# Ключи соответствуют значениям option["value"] в bot_features_config.py.
# Можно закрывать отдельные уровни, не отключая весь вид контракта.
# Если новый уровень не указан здесь, он считается открытым.

CONTRACT_LEVELS = {
    "ST": {
        "seafood": {
            "seafood_i": True,
            "seafood_ii": True,
            "seafood_iii": True,
            "seafood_iv": True,
        },
        "metallurgy": {
            "metallurgy_i": True,
            "metallurgy_ii": True,
            "metallurgy_iii": True,
            "metallurgy_iv": True,
        },
        "goods": {
            "goods_i": True,
            "goods_ii": True,
            "goods_iii": True,
            "goods_iv": True,
        },
        "atelier": {
            "ателье_i": True,
            "ателье_ii": True,
            "ателье_iii": True,
            "ателье_iv": True,
            "ателье_v": True,
        },
    },
    "CM": {
        "seafood": {
            "seafood_i": True,
            "seafood_ii": True,
            "seafood_iii": True,
            "seafood_iv": True,
        },
        "metallurgy": {
            "metallurgy_i": True,
            "metallurgy_ii": True,
            "metallurgy_iii": True,
            "metallurgy_iv": True,
        },
        "goods": {
            "goods_i": True,
            "goods_ii": True,
            "goods_iii": True,
            "goods_iv": True,
        },
        "atelier": {
            "ателье_i": True,
            "ателье_ii": True,
            "ателье_iii": True,
            "ателье_iv": True,
            "ателье_v": True,
        },
    },
}


def is_family_enabled(server: str) -> bool:
    """Проверяет, включены ли заявки в семью для указанного сервера."""
    return bool(FAMILY_APPLICATIONS.get(server, False))


def is_vacation_enabled(server: str) -> bool:
    """Проверяет, включён ли отпуск для указанного сервера."""
    return bool(VACATIONS.get(server, False))


def is_contract_level_enabled(server: str, contract_key: str, option_value: str) -> bool:
    """Проверяет доступность конкретного уровня контракта."""
    server_flags = CONTRACT_LEVELS.get(server, {})
    contract_flags = server_flags.get(contract_key, {})
    # Новые уровни по умолчанию открыты, чтобы добавление уровня
    # в bot_features_config.py не требовало обязательной правки этого файла.
    return bool(contract_flags.get(option_value, True))
