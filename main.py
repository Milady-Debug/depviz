#!/usr/bin/env python3
"""Точка входа CLI-приложения depviz.

Использование:  python main.py [путь_к_config.csv]
"""
import sys

from depviz.config import ConfigError, load_config
from depviz.maven import MavenError, MavenRepository, parse_coordinate


def main(argv):
    config_path = argv[1] if len(argv) > 1 else "config.csv"
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        return 1

    if config["test_mode"]:
        print("Тестовый режим будет поддержан на этапе 3.", file=sys.stderr)
        return 1

    # Этап 2: вывод прямых зависимостей пакета из Maven-репозитория
    repo = MavenRepository(config["repository"])
    group, artifact, version = parse_coordinate(config["package_name"])
    try:
        if version is None:
            version = repo.latest_version(group, artifact)
        deps = repo.direct_dependencies(group, artifact, version)
    except MavenError as e:
        print(f"Ошибка репозитория: {e}", file=sys.stderr)
        return 2

    print(f"Прямые зависимости {group}:{artifact}:{version} ({len(deps)}):")
    for d in deps:
        flags = f" [{d.scope}]" + (" (optional)" if d.optional else "")
        print(f"  {d.coord}{flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
