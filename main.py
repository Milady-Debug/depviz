#!/usr/bin/env python3
"""Точка входа CLI-приложения depviz.

Использование:  python main.py [путь_к_config.csv]
"""
import sys

from depviz.config import ConfigError, load_config
from depviz.d2 import to_d2
from depviz.graph import build_graph, format_tree, load_order
from depviz.maven import MavenError, MavenRepository, make_provider, parse_coordinate
from depviz.test_repo import TestRepoError, TestRepository


def prepare(config):
    """Возвращает (корневой узел, функция получения зависимостей, типы ошибок)."""
    if config["test_mode"]:
        repo = TestRepository(config["repository"])
        root = config["package_name"]
        repo.dependencies(root)  # пакет должен существовать
        return root, repo.dependencies, (TestRepoError,)
    repo = MavenRepository(config["repository"])
    group, artifact, version = parse_coordinate(config["package_name"])
    if version is None:
        version = repo.latest_version(group, artifact)
    repo.direct_dependencies(group, artifact, version)  # корневой POM должен загружаться
    return f"{group}:{artifact}:{version}", make_provider(repo), (MavenError,)


def main(argv):
    config_path = argv[1] if len(argv) > 1 else "config.csv"
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        return 1

    try:
        root, provider, errors = prepare(config)
    except (MavenError, TestRepoError) as e:
        print(f"Ошибка репозитория: {e}", file=sys.stderr)
        return 2

    graph = build_graph(root, provider, errors)

    mode = config["output_mode"]
    if mode == "d2":
        # Этап 5: описание графа на языке D2
        print(to_d2(graph), end="")
        for cycle in graph.cycles:
            print("Цикл: " + " -> ".join(cycle), file=sys.stderr)
        for node, err in graph.errors.items():
            print(f"Предупреждение: {node}: {err}", file=sys.stderr)
        return 0

    if mode == "load_order":
        # Этап 4: порядок загрузки зависимостей
        print(f"Порядок загрузки зависимостей для {root}:")
        for i, node in enumerate(load_order(graph), start=1):
            note = " (недоступен)" if node in graph.errors else ""
            print(f"  {i:>3}. {node}{note}")
    else:
        print(format_tree(graph))
        print(f"\nУзлов: {len(graph.nodes)}, рёбер: {graph.edge_count()}")
    if graph.cycles:
        print("Обнаружены циклические зависимости"
              " (обратное ребро цикла при упорядочивании пропущено):"
              if mode == "load_order" else
              "Обнаружены циклические зависимости:")
        for cycle in graph.cycles:
            print("  " + " -> ".join(cycle))
    for node, err in graph.errors.items():
        print(f"Предупреждение: {node}: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
