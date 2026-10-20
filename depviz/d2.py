"""Текстовое представление графа на языке диаграмм D2 (https://d2lang.com)."""


def _q(text):
    """Идентификатор D2 в кавычках (двоеточия и точки в именах Maven)."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_d2(graph, direction="down"):
    lines = [
        f"# Граф зависимостей пакета {graph.root}",
        f"direction: {direction}",
        "",
        f"{_q(graph.root)}: {{",
        "  style.fill: \"#fde68a\"",
        "  style.bold: true",
        "}",
    ]
    for node in graph.errors:
        lines += [f"{_q(node)}: {{",
                  "  style.stroke: \"#dc2626\"",
                  "  style.stroke-dash: 4",
                  "  tooltip: \"не удалось получить зависимости\"",
                  "}"]
    lines.append("")
    isolated = True
    for node, deps in graph.edges.items():
        for dep in deps:
            isolated = False
            if (node, dep) in graph.back_edges:
                lines += [f'{_q(node)} -> {_q(dep)}: "цикл" {{',
                          "  style.stroke: \"#dc2626\"",
                          "  style.stroke-dash: 3",
                          "}"]
            else:
                lines.append(f"{_q(node)} -> {_q(dep)}")
    if isolated:
        lines.append(f"# у пакета {graph.root} нет зависимостей")
    return "\n".join(lines) + "\n"
