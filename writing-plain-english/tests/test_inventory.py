"""inventory FILE: every token and word-class occurrence with its line, as a checklist."""
import time
import unittest

from helpers import FIXTURES, load_module, run, run_json

TOKEN_CLASSES = ["numbers", "code-spans", "code-blocks", "paths", "quoted-strings",
                 "links", "hashes", "bracket-labels"]
WORD_CLASSES = ["hedges", "conditions", "reasons", "negations", "counters"]


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
        """RED on v1: v1 has no inventory subcommand.

        Also RED on e885c908, which has no counters class: the class list here now names it.
        """
        w = self.data["words"]
        self.assertEqual(sorted(w), sorted(WORD_CLASSES))
        self.assertEqual(pairs(w["hedges"], "word"), [("only", 3)])
        self.assertEqual(pairs(w["conditions"], "word"), [("if", 4)])
        self.assertEqual(pairs(w["reasons"], "word"), [("because", 7)])
        self.assertEqual(pairs(w["negations"], "word"), [("not", 4)])
        self.assertEqual(pairs(w["counters"], "word"), [])

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


class InventoryCounters(unittest.TestCase):
    def test_every_counter_entry_with_its_line(self):
        """RED on e885c908: the parent has no counters class in its inventory."""
        _, d = run_json("inventory", "counters_all.md")
        self.assertEqual(pairs(d["words"]["counters"], "word"),
                         [("but", 1), ("However", 2), ("Although", 3), ("though", 4), ("yet", 5),
                          ("whereas", 6), ("nevertheless", 7), ("nonetheless", 8), ("Even so", 9),
                          ("despite", 10), ("in spite of", 11)])

    def test_even_so_is_a_counter_not_a_reason(self):
        """RED on e885c908: the parent counts the `so` of `Even so` as a reason."""
        _, d = run_json("inventory", "even_so.md")
        self.assertEqual(pairs(d["words"]["reasons"], "word"), [])
        self.assertEqual(pairs(d["words"]["counters"], "word"), [("Even so", 1)])



def counters(name):
    _, d = run_json("inventory", name)
    return pairs(d["words"]["counters"], "word")


class CounterRoles(unittest.TestCase):
    """A counter word in another role is not a counter-clause. Each fixture's
    line 2 holds the same word as a counter-clause, which is still counted."""

    def test_all_but(self):
        """RED on b24a2d58: the parent counts the `but` of `All but one` as a counter-clause."""
        self.assertEqual(counters("role_all_but.md"), [("but", 2)])

    def test_anything_but(self):
        """RED on b24a2d58: the parent counts the `but` of `anything but` as a counter-clause."""
        self.assertEqual(counters("role_anything_but.md"), [("but", 2)])

    def test_nothing_but(self):
        """RED on b24a2d58: the parent counts the `but` of `nothing but` as a counter-clause."""
        self.assertEqual(counters("role_nothing_but.md"), [("but", 2)])

    def test_not_only_but_also(self):
        """RED on b24a2d58: the parent counts the `but` of `not only ... but also` as a counter-clause."""
        self.assertEqual(counters("role_not_only.md"), [("but", 2)])

    def test_not_yet(self):
        """RED on b24a2d58: the parent counts the `yet` of `not yet` as a counter-clause."""
        self.assertEqual(counters("role_not_yet.md"), [("yet", 2)])

    def test_yet_another(self):
        """RED on b24a2d58: the parent counts the `yet` of `yet another` as a counter-clause."""
        self.assertEqual(counters("role_yet_another.md"), [("yet", 2)])

    def test_as_yet(self):
        """RED on b24a2d58: the parent counts the `yet` of `as yet` as a counter-clause."""
        self.assertEqual(counters("role_as_yet.md"), [("yet", 2)])

    def test_as_though_but_not_even_though(self):
        """RED on b24a2d58: the parent counts the `though` of `as though` as a counter-clause.

        The control on line 2 is `Even though`, which stays a counter-clause.
        """
        self.assertEqual(counters("role_as_though.md"), [("though", 2)])

    def test_however_before_a_degree_word(self):
        """RED on b24a2d58: the parent counts the `However` of `However long the copy takes` as a counter-clause."""
        self.assertEqual(counters("role_however_degree.md"), [("However", 2)])

    def test_however_before_a_pronoun_and_verb(self):
        """RED on b24a2d58: the parent counts the `However` of `However you start the service` as a counter-clause."""
        self.assertEqual(counters("role_however_pronoun.md"), [("however", 2)])


class MultiWordClaims(unittest.TestCase):
    def test_only_after_is_one_condition(self):
        """RED on b24a2d58: the parent counts the `only` of `only after` as a hedge as well as a condition.

        The control on line 2 is a plain `Only`, which stays a hedge.
        """
        _, d = run_json("inventory", "only_after.md")
        self.assertEqual(pairs(d["words"]["conditions"], "word"), [("only after", 1)])
        self.assertEqual(pairs(d["words"]["hedges"], "word"), [("Only", 2)])


class Scale(unittest.TestCase):
    def test_word_counts_scale_linearly(self):
        """RED on b24a2d58: the parent checks each word hit against every counter-clause span, so a 370 KB text takes more than 2.5 s.

        The text repeats one fixture line 3600 times. Where this test was
        written, the parent took about 11 s and the linear count about 0.6 s,
        so the bound sits a factor of about 4 from each.
        """
        mod = load_module()
        text = (FIXTURES / "scale_unit.md").read_text(encoding="utf-8") * 3600
        start = time.perf_counter()
        words = mod.extract(text)["words"]
        elapsed = time.perf_counter() - start
        self.assertEqual(len(words["counters"]), 3 * 3600)
        self.assertLess(elapsed, 2.5)


if __name__ == "__main__":
    unittest.main()
