# -*- coding: utf-8 -*-
"""
Настройка дополнительных функций Blin.

Здесь находятся настройки заявок на выплату контрактов,
дисциплины и сообщений ролей.
"""

# ======================== КОНТРАКТЫ ========================================

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

# Максимум: 20 кнопок на сервер, 10 вариантов у кнопки, 5 полей в модальном окне.
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
        {
            "key": "contract_2",
            "label": "Контракт 2",
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

# ======================== ДИСЦИПЛИНА =======================================

DISCIPLINE_LOG_CHANNELS = {
    "PHX": 1550559942480502794,
    "DN": 1550560587224842270,
}

# ======================== РОЛИ ПО РЕАКЦИИ/КНОПКАМ ==========================

# mode = "reaction" или "button".
# Для reaction: role_id_by_emoji = {"✅": ID_РОЛИ}
# Для button: buttons = максимум 2 кнопки.
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
