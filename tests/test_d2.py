import unittest

from depviz.d2 import to_d2
from depviz.graph import build_graph


class D2Test(unittest.TestCase):
    def test_edges_and_cycle(self):
        edges = {"A": ["B"], "B": ["A", "C"], "C": []}
        text = to_d2(build_graph("A", lambda n: edges[n]))
        self.assertIn('"A" -> "B"', text)
        self.assertIn('"B" -> "C"', text)
        self.assertIn('"B" -> "A": "цикл"', text)

    def test_quotes_escaped(self):
        text = to_d2(build_graph('a"b', lambda n: []))
        self.assertIn('"a\\"b"', text)


if __name__ == "__main__":
    unittest.main()
