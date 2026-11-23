"""inventory FILE: every token and word-class occurrence with its line, as a checklist."""
import unittest

from helpers import run, run_json

TOKEN_CLASSES = ["numbers", "code-spans", "code-blocks", "paths", "quoted-strings",
                 "links", "hashes", "bracket-labels"]
WORD_CLASSES = ["hedges", "conditions", "reasons", "negations"]


def pairs(entries, key):
    return [(e[key], e["line"]) for e in entries]


class Inventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.data = run_json("inventory", "inv.md")

    def test_exit_status(self):
        """RED on v1: v1 has no inventory subcommand; it reads `inventory` as a file name and exits 2."""
        self.assertEqual(self.code, 0)

    def test_tokens_with_lines(self):
        """RED on v1: v1 has no inventory subcommand."""
        t = self.data["tokens"]
        self.assertEqual(sorted(t), sorted(TOKEN_CLASSES))
        self.assertEqual(pairs(t["numbers"], "token"), [("45", 3)])
        self.assertEqual(pairs(t["code-spans"], "token"), [("restore --dry-run", 4)])
        self.assertEqual(pairs(t["paths"], "token"), [("tools/restore.sh", 5)])
        self.assertEqual(pairs(t["hashes"], "token"), [("a1b2c3d", 5)])
        self.assertEqual(pairs(t["quoted-strings"], "token"), [("check twice", 7)])
        self.assertEqual([t[k] for k in ("code-blocks", "links", "bracket-labels")], [[], [], []])

    def test_words_with_lines(self):
        """RED on v1: v1 has no inventory subcommand."""
        w = self.data["words"]
        self.assertEqual(sorted(w), sorted(WORD_CLASSES))
        self.assertEqual(pairs(w["hedges"], "word"), [("only", 3)])
        self.assertEqual(pairs(w["conditions"], "word"), [("if", 4)])
        self.assertEqual(pairs(w["reasons"], "word"), [("because", 7)])
        self.assertEqual(pairs(w["negations"], "word"), [("not", 4)])

    def test_text_is_a_checklist(self):
        """RED on v1: v1 has no inventory subcommand."""
        code, out, _ = run("inventory", "inv.md")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "== inventory inv.md")
        for line in ("-- numbers", "   [ ] L3 45", "   [ ] L5 tools/restore.sh",
                     "-- hedges", "   [ ] L3 only", "   [ ] L7 because"):
            self.assertIn(line, lines)

    def test_curly_quote_counted_and_apostrophes_ignored(self):
        """RED on v1: v1 has no inventory subcommand (and counts no curly quotes)."""
        _, d = run_json("inventory", "q4.md")
        self.assertEqual(pairs(d["tokens"]["quoted-strings"], "token"), [("done", 1)])
        self.assertEqual(len(d["words"]["negations"]), 1)

    def test_text_with_nothing_to_keep(self):
        """RED on v1: v1 has no inventory subcommand to report an empty list."""
        code, d = run_json("inventory", "inv_empty.md")
        self.assertEqual(code, 0)
        self.assertTrue(all(v == [] for v in d["tokens"].values()))
        self.assertTrue(all(v == [] for v in d["words"].values()))

    def test_outer_quote_wins_over_inner(self):
        """RED on v1: v1 has no inventory subcommand (and a naive per-style pass splits “a "b" c” in two)."""
        _, d = run_json("inventory", "quote_nested.md")
        self.assertEqual(pairs(d["tokens"]["quoted-strings"], "token"), [('use "x" now', 1)])

    def test_link_text_keeps_its_code_span(self):
        """RED on v1: v1 has no inventory subcommand (and blanking code first would empty the link text)."""
        _, d = run_json("inventory", "link_code.md")
        self.assertEqual(pairs(d["tokens"]["links"], "token"), [("[`cfg`](https://example.com/cfg)", 1)])
        self.assertEqual(pairs(d["tokens"]["code-spans"], "token"), [("cfg", 1)])

    def test_path_at_a_sentence_end_drops_the_period(self):
        """RED on v1: v1 has no path class (and a path pattern that keeps a final `.` drops `docs/setup.md.`)."""
        _, d = run_json("inventory", "path_end.md")
        self.assertEqual(pairs(d["tokens"]["paths"], "token"),
                         [("docs/setup.md", 1), ("/etc/hosts", 1), ("notes.txt", 1)])


if __name__ == "__main__":
    unittest.main()
