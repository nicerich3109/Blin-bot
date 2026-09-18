# -*- coding: utf-8 -*-
"""Настройки дополнительных функций Blin."""

CONTRACT_PAYOUT_CHANNELS = {
    "PHX": 1525206310474485901,
    "DN": 1372517581415514173,
}

CONTRACT_PANEL_CHANNELS = {
    "PHX": 1525152798843469884,
    "DN": 1372267301159567579,
}

CONTRACT_PANEL_TITLES = {
    "PHX": "Заявки на выплату с контрактов — Phoenix",
    "DN": "Заявки на выплату с контрактов — Denver",
}

CONTRACT_PANEL_TEXTS = {
    "PHX": "Выберите выполненный контракт и заполните заявку на выплату.",
    "DN": "Выберите выполненный контракт и заполните заявку на выплату.",
}

CONTRACT_PANEL_IMAGES = {
    "PHX": "",
    "DN": "",
}

def _fields(with_quantity):
    fields = [
        {"label": "Статик #", "placeholder": "Укажите ваш статический ID", "required": True},
        {"label": "Скрин выполненной работы", "placeholder": "ссылка на скриншот из imgur/yapx/ibb", "required": True},
    ]
    if with_quantity:
        fields.append({"label": "Количество", "placeholder": "Укажите сколько рыбы вы сдали", "required": True})
    return fields

def _options(prefix, prices, with_quantity):
    roman = ("I", "II", "III", "IV", "V")
    return [
        {
            "value": f"{prefix.lower().replace(' ', '_')}_{roman[i].lower()}",
            "label": f"{prefix} {roman[i]} - {price}",
            "description": "Заявка на выплату",
            "modal_title": "Заявка на выплату",
            "fields": _fields(with_quantity),
        }
        for i, price in enumerate(prices)
    ]

CONTRACT_BUTTONS = {
    "PHX": [
        {"key": "seafood", "label": "Дары моря", "style": "primary",
         "options": _options("Дары моря", ("1,2234", "1,2512", "0,8893", "0,7619"), True)},
        {"key": "metallurgy", "label": "Металлургия", "style": "primary",
         "options": _options("Металлургия", ("15,000", "20,000", "22,000", "25,000"), False)},
        {"key": "goods", "label": "Товары", "style": "primary",
         "options": _options("Товары", ("15,000", "17,500", "20,000", "25,000"), False)},
        {"key": "atelier", "label": "Ателье", "style": "primary",
         "options": _options("Ателье", ("700", "800", "850", "900", "950"), True)},
    ],
    "DN": [
        {"key": "seafood", "label": "Дары моря", "style": "primary",
         "options": _options("Дары моря", ("1,2234", "1,2512", "0,8893", "0,7619"), True)},
        {"key": "metallurgy", "label": "Металлургия", "style": "primary",
         "options": _options("Металлургия", ("15,000", "20,000", "22,000", "25,000"), False)},
        {"key": "goods", "label": "Товары", "style": "primary",
         "options": _options("Товары", ("15,000", "17,500", "20,000", "25,000"), False)},
        {"key": "atelier", "label": "Ателье", "style": "primary",
         "options": _options("Ателье", ("700", "800", "850", "900", "950"), True)},
    ],
}

DISCIPLINE_LOG_CHANNELS = {
    "PHX": 1550559942480502794,
    "DN": 1550560587224842270,
}

REACTION_ROLE_MESSAGES = {}
