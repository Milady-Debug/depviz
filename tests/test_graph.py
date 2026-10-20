import unittest

from depviz.graph import build_graph


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


if __name__ == "__main__":
    unittest.main()
