# -*- coding: utf-8 -*-
"""
Настройка заявок на выплату контрактов.

Этот файл специально отделён от основной config.py.
Здесь можно менять кнопки, варианты выбора, текст панели и поля модальных окон.

Ограничения Discord/бота:
- максимум 20 кнопок на сервер;
- максимум 10 вариантов у одной кнопки;
- максимум 5 полей в одном модальном окне.
"""

CONTRACT_PAYOUT_CHANNELS = {
    "PHX": 1525206310474485901,
    "DN": 1372517581415514173,
}

CONTRACT_PANEL_CHANNELS = {
    "PHX": 1525206310474485901,
    "DN": 1372517581415514173,
}

CONTRACT_PANEL_TITLES = {
    "PHX": "Заявки на выплату контрактов — Phoenix",
    "DN": "Заявки на выплату контрактов — Denver",
}

CONTRACT_PANEL_TEXTS = {
    "PHX": "Выберите выполненный контракт и заполните заявку на выплату.",
    "DN": "Выберите выполненный контракт и заполните заявку на выплату.",
}

CONTRACT_PANEL_IMAGES = {
    "PHX": "",
    "DN": "",
}

# key — внутренний уникальный ключ кнопки.
# label — текст кнопки.
# style: primary / secondary / success / danger.
# options — варианты после нажатия кнопки.
#
# У поля:
# label       — название строки;
# placeholder — подсказка;
# required    — обязательность;
# paragraph   — True = большое поле;
# max_length  — максимальная длина.
CONTRACT_BUTTONS = {
    "PHX": [
        {
            "key": "contract_1",
            "label": "Контракт 1",
            "style": "primary",
            "options": [
                {
                    "value": "option_1",
                    "label": "Выплата",
                    "description": "Заявка на получение премии",
                    "modal_title": "Заявка на выплату",
                    "fields": [
                        {
                            "label": "Номер контракта",
                            "placeholder": "Укажите номер контракта",
                            "required": True,
                        },
                        {
                            "label": "Что выполнено",
                            "placeholder": "Опишите выполненный контракт",
                            "paragraph": True,
                            "required": True,
                        },
                    ],
                },
            ],
        },
    ],

    "DN": [
        {
            "key": "contract_1",
            "label": "Контракт 1",
            "style": "primary",
            "options": [
                {
                    "value": "option_1",
                    "label": "Выплата",
                    "description": "Заявка на получение премии",
                    "modal_title": "Заявка на выплату",
                    "fields": [
                        {
                            "label": "Номер контракта",
                            "placeholder": "Укажите номер контракта",
                            "required": True,
                        },
                        {
                            "label": "Что выполнено",
                            "placeholder": "Опишите выполненный контракт",
                            "paragraph": True,
                            "required": True,
                        },
                    ],
                },
            ],
        },
    ],
}

# ======================== ДИСЦИПЛИНА ======================================

DISCIPLINE_LOG_CHANNELS = {
    "PHX": 1550559942480502794,
    "DN": 1550560587224842270,
}

# ======================== РОЛИ ПО РЕАКЦИИ/КНОПКАМ ==========================

# mode = "reaction" или "button".
#
# Для reaction:
#   role_id_by_emoji = {"✅": ID_РОЛИ}
#
# Для button:
#   buttons = максимум 2 кнопки.
#
# image можно оставить пустым.
REACTION_ROLE_MESSAGES = {
    # "example": {
    #     "channel_id": 123456789,
    #     "text": "Выберите роль",
    #     "image": "",
    #     "mode": "button",
    #     "buttons": [
    #         {
    #             "label": "Получить роль",
    #             "role_id": 123456789,
    #             "style": "success",
    #         },
    #     ],
    #     "role_id_by_emoji": {
    #         "✅": 123456789,
    #     },
    # }
}
