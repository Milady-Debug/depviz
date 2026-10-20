import unittest

from depviz.graph import build_graph, load_order


def make(edges):
    def provider(n):
        if n not in edges:
            raise KeyError(n)
        return edges[n]
    return provider


class BuildGraphTest(unittest.TestCase):
    def test_transitive(self):
        g = build_graph("A", make({"A": ["B"], "B": ["C"], "C": []}), (KeyError,))
        self.assertEqual(g.nodes, ["A", "B", "C"])
        self.assertEqual(g.cycles, [])

    def test_diamond_visited_once(self):
        calls = []
        edges = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        def provider(n):
            calls.append(n)
            return edges[n]
        build_graph("A", provider)
        self.assertEqual(calls.count("D"), 1)

    def test_cycle(self):
        g = build_graph("A", make({"A": ["B"], "B": ["C"], "C": ["A"]}), (KeyError,))
        self.assertEqual(g.cycles, [["A", "B", "C", "A"]])
        self.assertIn(("C", "A"), g.back_edges)

    def test_self_loop(self):
        g = build_graph("A", make({"A": ["A"]}), (KeyError,))
        self.assertEqual(g.cycles, [["A", "A"]])

    def test_missing_package(self):
        g = build_graph("A", make({"A": ["Z"]}), (KeyError,))
        self.assertIn("Z", g.errors)




class LoadOrderTest(unittest.TestCase):
    def check_order(self, edges, root="A"):
        g = build_graph(root, make(edges), (KeyError,))
        order = load_order(g)
        pos = {n: i for i, n in enumerate(order)}
        for node, deps in g.edges.items():
            for d in deps:
                if (node, d) not in g.back_edges:
                    self.assertLess(pos[d], pos[node], f"{d} должен идти раньше {node}")
        self.assertEqual(order[-1], root)
        self.assertEqual(len(order), len(set(order)))
        return order

    def test_diamond(self):
        self.assertEqual(self.check_order({"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}),
                         ["D", "B", "C", "A"])

    def test_cycle(self):
        self.check_order({"A": ["B"], "B": ["C"], "C": ["A", "D"], "D": []})


if __name__ == "__main__":
    unittest.main()
