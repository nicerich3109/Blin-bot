# -*- coding: utf-8 -*-
"""
Настройка логирования.

Все важные события (создание заявок, решения по ним, выдача/снятие
ролей и любые ошибки) пишутся и в консоль, и в файл `bot.log`
(с ротацией, чтобы файл не рос бесконечно). Это нужно, чтобы можно было
разобрать причину сбоя (например, почему не выдалась роль отпуска) уже
после того, как событие произошло.
"""

import logging
from logging.handlers import RotatingFileHandler

import config

_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("blin_bot")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        config.LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # discord.py сам по себе довольно "шумный" на уровне INFO — оставляем
    # ему только WARNING и выше, чтобы наш bot.log не тонул в его логах.
    logging.getLogger("discord").setLevel(logging.WARNING)

    _logger = logger
    return logger


logger = get_logger()
