"""The lint's source: no stale comments, a docstring without provenance,
stdlib imports only, and the word lists as constants. Also: no fixture
text exists twice."""
import ast
import hashlib
import re
import sys
import unittest

from helpers import FIXTURES, load_module, source

HEDGES = {"may", "might", "could", "possibly", "probably", "likely", "only", "just",
          "by itself", "alone", "appears", "seems", "suggests"}
CONDITIONS = {"if", "unless", "only after", "otherwise", "when", "until", "except"}
REASONS = {"because", "so", "since", "therefore", "which means"}
NEGATIONS = {"not", "no", "never", "none", "nothing", "without", "n't"}


class Source(unittest.TestCase):
    def test_no_stale_gate_or_guard_comments(self):
        """RED on v1: v1's comments describe an imperative gate and a colon guard that do not exist."""
        text = source().lower()
        # Report only the phrases found: the source itself must not reach the run's output.
        self.assertEqual([p for p in ("imperative gate", "colon guard") if p in text], [])

    def test_docstring_names_no_corpus_workspace_or_date(self):
        """RED on v1: v1's docstring names a dated corpus and a workspace."""
        doc = ast.get_docstring(ast.parse(source())) or ""
        self.assertTrue(doc.strip(), "no module docstring")
        # Report only counts: the docstring itself must not reach the run's output.
        dates = len(re.findall(r"\d{4}-\d{2}-\d{2}", doc))
        places = len(re.findall(r"corpus|workspace", doc.lower()))
        self.assertEqual((dates, places), (0, 0), "(dates, corpus/workspace mentions)")

    def test_stdlib_imports_only(self):
        """Guard, passes on v1: every import is a standard-library module."""
        tree = ast.parse(source())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertEqual(names - set(sys.stdlib_module_names), set())

    def test_word_lists_are_constants(self):
        """RED on v1: v1 has no word-class constants."""
        mod = load_module()
        self.assertEqual(set(mod.HEDGES), HEDGES)
        self.assertEqual(set(mod.CONDITIONS), CONDITIONS)
        self.assertEqual(set(mod.REASONS), REASONS)
        self.assertEqual(set(mod.NEGATIONS), NEGATIONS)

    def test_default_labels_constant(self):
        """RED on v1: v1 has no label set."""
        mod = load_module()
        self.assertEqual(list(mod.DEFAULT_LABELS),
                         ["Verified", "Reported", "Observed", "Inferred", "Hypothesis", "Unknown"])


class Fixtures(unittest.TestCase):
    def test_no_fixture_text_exists_twice(self):
        """Guard, independent of the lint: each fixture text exists once."""
        seen = {}
        for p in sorted(FIXTURES.iterdir()):
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertNotIn(digest, seen, f"{p.name} repeats {seen.get(digest)}")
            seen[digest] = p.name


if __name__ == "__main__":
    unittest.main()
