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
    """A counter word in a fixed phrase that is never a counter-clause is not
    counted. Each fixture's line 2 holds the same word as a counter-clause,
    which is still counted."""

    def test_not_only_but_also(self):
        """RED on b24a2d58: the parent counts the `but` of `not only ... but also` as a counter-clause."""
        self.assertEqual(counters("role_not_only.md"), [("but", 2)])

    def test_not_yet(self):
        """RED on b24a2d58: the parent counts the `yet` of `not yet` as a counter-clause."""
        self.assertEqual(counters("role_not_yet.md"), [("yet", 2)])

    def test_as_yet(self):
        """RED on b24a2d58: the parent counts the `yet` of `as yet` as a counter-clause."""
        self.assertEqual(counters("role_as_yet.md"), [("yet", 2)])

    def test_as_though_but_not_even_though(self):
        """RED on b24a2d58: the parent counts the `though` of `as though` as a counter-clause.

        The control on line 2 is `Even though`, which stays a counter-clause.
        """
        self.assertEqual(counters("role_as_though.md"), [("though", 2)])


class CountedRoles(unittest.TestCase):
    """Where a phrase can also start a counter-clause, its counter word is
    counted, whatever its role in this text: the error-direction rule in
    the lint's docstring. Each fixture's counter words are all counted."""

    def test_all_but_before_a_clause(self):
        """RED on f0892596: the parent leaves out every `all but`, so two counter-clauses written without a comma are not counted."""
        self.assertEqual(counters("role_all_but_clause.md"), [("but", 1), ("but", 2)])

    def test_anything_but_before_a_clause(self):
        """RED on f0892596: the parent leaves out every `anything but`, so `anything but the build still broke` is not counted."""
        self.assertEqual(counters("role_anything_but_clause.md"), [("but", 1)])

    def test_nothing_but_before_a_clause(self):
        """RED on f0892596: the parent leaves out every `nothing but`, so `nothing but the tests failed again` is not counted."""
        self.assertEqual(counters("role_nothing_but_clause.md"), [("but", 1)])

    def test_anything_but_before_an_adjective(self):
        """RED on f0892596: the parent leaves out the `but` of `anything but smooth`, a role guess."""
        self.assertEqual(counters("role_anything_but.md"), [("but", 1), ("but", 2)])

    def test_nothing_but_before_a_noun(self):
        """RED on f0892596: the parent leaves out the `but` of `nothing but timeouts`, a role guess."""
        self.assertEqual(counters("role_nothing_but.md"), [("but", 1), ("but", 2)])

    def test_however_at_a_sentence_start(self):
        """RED on f0892596: the parent leaves out a `However` before a pronoun, so the counter-clause `However we saw the same error` is not counted."""
        self.assertEqual(counters("role_however_initial.md"), [("However", 1)])

    def test_however_after_a_comma(self):
        """RED on f0892596: the parent leaves out a `however` before a pronoun, so the clause-initial `, however we still need` is not counted."""
        self.assertEqual(counters("role_however_comma.md"), [("however", 1)])

    def test_however_manner_at_a_sentence_start(self):
        """RED on f0892596: the parent leaves out the sentence-initial `However you start the service`, which has the shape of a counter-clause."""
        self.assertEqual(counters("role_however_pronoun.md"), [("However", 1), ("however", 2)])

    def test_however_many_in_a_counter_clause(self):
        """RED on 56aebf56: the parent leaves out a `However` before a degree word, so the counter-clause `However many users still see the error` is not counted."""
        self.assertEqual(counters("role_however_degree_clause.md"), [("However", 1)])

    def test_however_we_in_mid_clause(self):
        """RED on 56aebf56: the parent leaves out a mid-clause `however` before a pronoun, so the counter-clause `however we see failures` is not counted."""
        self.assertEqual(counters("role_however_pronoun_clause.md"), [("however", 1)])

    def test_all_but_one_in_a_counter_clause(self):
        """RED on 56aebf56: the parent leaves out the `but` of `all but` before a number word, so the counter-clause `but one still hangs` is not counted."""
        self.assertEqual(counters("role_all_but_number_clause.md"), [("but", 1)])

    def test_yet_another_in_a_counter_clause(self):
        """RED on 56aebf56: the parent leaves out the `yet` of `yet another`, so the counter-clause `yet another leak appeared` is not counted."""
        self.assertEqual(counters("role_yet_another_clause.md"), [("yet", 1)])

    def test_however_opens_a_paragraph_after_a_heading(self):
        """RED on 56aebf56: the parent reads the heading's last word as a word before a mid-clause `however`, so the paragraph-opening `However we found` is not counted."""
        self.assertEqual(counters("role_however_after_heading.md"), [("However", 2)])

    def test_however_opens_a_paragraph_after_a_list_item(self):
        """RED on 56aebf56: the parent reads the last word of an item with no final period as a word before a mid-clause `however`, so the paragraph-opening `However we saw` is not counted."""
        self.assertEqual(counters("role_however_after_item.md"), [("However", 3)])

    def test_all_but_before_a_number_word(self):
        """RED on 56aebf56: the parent leaves out the `but` of `All but one`, a role guess; `all but one` can also start a counter-clause."""
        self.assertEqual(counters("role_all_but.md"), [("but", 1), ("but", 2)])

    def test_anything_but_before_a_few(self):
        """RED on 56aebf56: the parent leaves out the `but` of `anything but a few`, a role guess; `anything but a few` can also start a counter-clause."""
        self.assertEqual(counters("role_anything_but_few.md"), [("but", 1), ("but", 2)])

    def test_nothing_but_before_a_number(self):
        """RED on 56aebf56: the parent leaves out the `but` of `nothing but 3`, a role guess; `nothing but` before a number can also start a counter-clause."""
        self.assertEqual(counters("role_nothing_but_number.md"), [("but", 1), ("but", 2)])

    def test_yet_another_as_a_phrase(self):
        """RED on 56aebf56: the parent leaves out the `yet` of `yet another disk error`, a role guess; `yet another` can also start a counter-clause."""
        self.assertEqual(counters("role_yet_another.md"), [("yet", 1), ("yet", 2)])

    def test_however_before_a_degree_word(self):
        """RED on 56aebf56: the parent leaves out the `However` of `However long the copy takes`, a role guess; `However` before a degree word can also start a counter-clause."""
        self.assertEqual(counters("role_however_degree.md"), [("However", 1), ("However", 2)])

    def test_however_before_a_pronoun_in_mid_clause(self):
        """RED on 56aebf56: the parent leaves out the `however` of `one log file however you call it`, a role guess; a mid-clause `however` before a pronoun can also start a counter-clause."""
        self.assertEqual(counters("role_however_mid_clause.md"), [("however", 1), ("however", 2)])


class MultiWordClaims(unittest.TestCase):
    def test_only_after_is_one_condition(self):
        """RED on b24a2d58: the parent counts the `only` of `only after` as a hedge as well as a condition.

        The control on line 2 is a plain `Only`, which stays a hedge.
        """
        _, d = run_json("inventory", "only_after.md")
        self.assertEqual(pairs(d["words"]["conditions"], "word"), [("only after", 1)])
        self.assertEqual(pairs(d["words"]["hedges"], "word"), [("Only", 2)])


class CodeBlocks(unittest.TestCase):
    def test_tilde_fence_is_a_code_block(self):
        """RED on f0892596: the parent does not read `~~~` as a fence, so it lists no code block and lists the numbers inside the fence as number tokens."""
        _, d = run_json("inventory", "tilde_fence_backticks.md")
        blocks = pairs(d["tokens"]["code-blocks"], "token")
        self.assertEqual(len(blocks), 1)
        self.assertRegex(blocks[0][0], r"^[0-9a-f]{12} step 4 of 4: copy ```")
        self.assertEqual(blocks[0][1], 2)
        self.assertEqual(d["tokens"]["numbers"], [])


class Scale(unittest.TestCase):
    def test_word_counts_scale_linearly(self):
        """Guard, passes on f0892596: the word count is linear, so 4 times the text takes less than 8 times as long.

        The text repeats one fixture line 400 and 1600 times. The two sizes
        are timed in turn, 3 times each, and each keeps its fastest run, so
        the verdict is a ratio on one machine at one time, not a wall-clock
        bound. Where this test was written, the ratio was about 4 here and
        about 12 for b24a2d58, which checks each word hit against every
        counter-clause span.
        """
        mod = load_module()
        unit = (FIXTURES / "scale_unit.md").read_text(encoding="utf-8")
        sizes = (400, 1600)
        best = [float("inf")] * len(sizes)
        for _ in range(3):
            for k, n in enumerate(sizes):
                text = unit * n
                start = time.perf_counter()
                found = mod.extract(text)["words"]["counters"]
                best[k] = min(best[k], time.perf_counter() - start)
                self.assertEqual(len(found), 3 * n)
        self.assertLess(best[1] / best[0], 8)


if __name__ == "__main__":
    unittest.main()
