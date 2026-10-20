#!/usr/bin/env python3
"""Точка входа CLI-приложения depviz.

Использование:  python main.py [путь_к_config.csv]
"""
import sys

from depviz.config import ConfigError, load_config


def main(argv):
    config_path = argv[1] if len(argv) > 1 else "config.csv"
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        return 1

    # Этап 1: вывод всех настраиваемых параметров в формате ключ-значение
    for key, value in config.items():
        print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
