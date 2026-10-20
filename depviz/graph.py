"""Построение графа зависимостей с учётом транзитивности (DFS с рекурсией)."""
import sys

WHITE, GRAY, BLACK = 0, 1, 2  # не посещён / в стеке рекурсии / обработан


class DependencyGraph:
    def __init__(self, root):
        self.root = root
        self.edges = {}        # узел -> список зависимостей (в порядке объявления)
        self.cycles = []       # найденные циклы: [A, B, ..., A]
        self.back_edges = set()  # рёбра, замыкающие цикл
        self.errors = {}       # узел -> текст ошибки получения его зависимостей

    @property
    def nodes(self):
        return list(self.edges)

    def edge_count(self):
        return sum(len(v) for v in self.edges.values())


def build_graph(root, get_dependencies, errors=(Exception,)):
    """Обходит граф в глубину рекурсивно.

    get_dependencies(узел) -> список узлов-зависимостей.
    Цвет GRAY означает «узел на текущем пути»: встреча GRAY-узла —
    это обратное ребро, т.е. циклическая зависимость. Такой узел повторно
    не обходится, поэтому рекурсия всегда завершается.
    """
    graph = DependencyGraph(root)
    color = {}
    path = []
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))

    def dfs(node):
        color[node] = GRAY
        path.append(node)
        try:
            deps = list(get_dependencies(node))
        except errors as e:
            graph.errors[node] = str(e)
            deps = []
        graph.edges[node] = deps
        for dep in deps:
            state = color.get(dep, WHITE)
            if state == WHITE:
                dfs(dep)
            elif state == GRAY:
                graph.cycles.append(path[path.index(dep):] + [dep])
                graph.back_edges.add((node, dep))
            # BLACK: узел уже полностью обработан (общая зависимость, «ромб»)
        path.pop()
        color[node] = BLACK

    dfs(root)
    return graph


def format_tree(graph):
    """Дерево зависимостей в стиле `mvn dependency:tree`.
    (*) — узел уже раскрыт выше, (цикл) — циклическая зависимость."""
    lines = [graph.root]
    expanded = {graph.root}

    def walk(node, prefix, stack):
        deps = graph.edges.get(node, [])
        for i, dep in enumerate(deps):
            last = i == len(deps) - 1
            branch = "\\- " if last else "+- "
            mark = ""
            if dep in stack:
                mark = " (цикл)"
            elif dep in expanded:
                mark = " (*)"
            if dep in graph.errors:
                mark += " [ошибка]"
            lines.append(prefix + branch + dep + mark)
            if not mark.strip() or mark == " [ошибка]":
                expanded.add(dep)
                walk(dep, prefix + ("   " if last else "|  "), stack + [dep])

    walk(graph.root, "", [graph.root])
    return "\n".join(lines)


def load_order(graph):
    """Порядок загрузки: каждая зависимость идёт раньше зависящего от неё
    пакета (обратный топологический порядок, post-order DFS).
    Корневой пакет загружается последним. Если есть цикл, обратное ребро
    пропускается, т.е. цикл «разрывается» в месте его обнаружения."""
    order, visited = [], set()

    def visit(node):
        visited.add(node)
        for dep in graph.edges.get(node, []):
            if dep not in visited:
                visit(dep)
        order.append(node)

    visit(graph.root)
    return order
