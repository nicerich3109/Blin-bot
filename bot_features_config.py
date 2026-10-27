# -*- coding: utf-8 -*-
"""Настройки дополнительных функций Blin."""

CONTRACT_PAYOUT_CHANNELS = {
    "ST": 1525206310474485901,
    "CM": 1372517581415514173,
}

CONTRACT_PANEL_CHANNELS = {
    "ST": 1525152798843469884,
    "CM": 1372267301159567579,
}

CONTRACT_PANEL_TITLES = {
    "ST": "Заявки на выплату с контрактов — State",
    "CM": "Заявки на выплату с контрактов — Crime",
}

CONTRACT_PANEL_TEXTS = {
    "ST": "Выберите выполненный контракт и заполните заявку на выплату.",
    "CM": "Выберите выполненный контракт и заполните заявку на выплату.",
}

CONTRACT_PANEL_IMAGES = {
    "ST": "",
    "CM": "",
}

def _fields(with_quantity, quantity_placeholder="Укажите количество"):
    fields = [
        {"label": "Статик #", "placeholder": "Укажите ваш статический ID", "required": True},
        {"label": "Скрин выполненной работы", "placeholder": "ссылка на скриншот из imgur/yapx/ibb", "required": True},
    ]
    if with_quantity:
        fields.append({"label": "Количество", "placeholder": quantity_placeholder, "required": True})
    return fields

def _options(prefix, prices, with_quantity, quantity_placeholder="Укажите количество"):
    roman = ("I", "II", "III", "IV", "V")
    return [
        {
            "value": f"{prefix.lower().replace(' ', '_')}_{roman[i].lower()}",
            "label": f"{prefix} {roman[i]} - {price}",
            "price": price,
            "with_quantity": with_quantity,
            "description": "Заявка на выплату",
            "modal_title": "Заявка на выплату",
            "fields": _fields(with_quantity, quantity_placeholder),
        }
        for i, price in enumerate(prices)
    ]

CONTRACT_BUTTONS = {
    "ST": [
        {"key": "seafood", "label": "Дары моря", "style": "primary",
         "options": _options("Дары моря", ("1,2234", "1,2512", "0,8893", "0,7619"), True)},
        {"key": "metallurgy", "label": "Металлургия", "style": "primary",
         "options": _options("Металлургия", ("15,000", "20,000", "22,000", "25,000"), False)},
        {"key": "goods", "label": "Товары", "style": "primary",
         "options": _options("Товары", ("15,000", "17,500", "20,000", "25,000"), False)},
        {"key": "atelier", "label": "Ателье", "style": "primary",
         "options": _options("Ателье", ("700", "800", "850", "900", "950"), True, "Укажите сколько одежды вы сдали")},
    ],
    "CM": [
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


REACTION_ROLE_MESSAGES = {}
