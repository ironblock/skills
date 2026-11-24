"""--compare OLD NEW: which tokens disappeared and appeared, per class, and
the counts of hedges, conditions, reasons, negations and counter-clauses."""
import unittest

from helpers import run, run_json

TOKEN_CLASSES = ["numbers", "code-spans", "code-blocks", "paths", "quoted-strings",
                 "links", "hashes", "bracket-labels"]
WORD_CLASSES = ["hedges", "conditions", "reasons", "negations"]


def compare(old, new, *flags):
    return run_json(*flags, "--compare", old, new)


class CompareTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.data = compare("cmp_old.md", "cmp_new.md")

    def gone_and_new(self, cls_name):
        return self.data["disappeared"][cls_name], self.data["appeared"][cls_name]

    def test_every_class_is_reported(self):
        """RED on v1: v1 reports counts only, with no disappeared or appeared lists."""
        self.assertEqual(sorted(self.data["disappeared"]), sorted(TOKEN_CLASSES))
        self.assertEqual(sorted(self.data["appeared"]), sorted(TOKEN_CLASSES))

    def test_numbers_as_written(self):
        """RED on v1: v1 counts digits, so 12 -> 21 is a delta of 0."""
        self.assertEqual(self.gone_and_new("numbers"), (["12", "v0.9.0"], ["21", "v0.9.1"]))

    def test_code_spans(self):
        """RED on v1: v1 counts code spans, so `--fast` -> `--slow` is a delta of 0."""
        self.assertEqual(self.gone_and_new("code-spans"), (["--fast"], ["--slow"]))

    def test_code_blocks_by_content_hash(self):
        """RED on v1: v1 counts fenced blocks, so a changed block body is a delta of 0."""
        gone, new = self.gone_and_new("code-blocks")
        self.assertEqual(len(gone), 1)
        self.assertEqual(len(new), 1)
        self.assertRegex(gone[0], r"^[0-9a-f]{12} reset --soft$")
        self.assertRegex(new[0], r"^[0-9a-f]{12} reset --hard$")

    def test_paths(self):
        """RED on v1: v1 has no path class."""
        self.assertEqual(self.gone_and_new("paths"), (["src/import/reader.py"], ["src/import/parser.py"]))

    def test_quoted_strings_straight_and_curly_are_one_class(self):
        """RED on v1: v1 counts straight quotes only and lists no strings."""
        self.assertEqual(self.gone_and_new("quoted-strings"), (["hold on"], ["wait"]))

    def test_links_by_text_and_target(self):
        """RED on v1: v1 counts links, so a changed target is a delta of 0."""
        self.assertEqual(self.gone_and_new("links"),
                         (["[the runbook](https://example.com/runbook)"],
                          ["[the runbook](https://example.com/manual)"]))

    def test_short_hashes(self):
        """RED on v1: v1 counts 40-hex hashes only, so 3fa94c2 -> 3fa94c3 is invisible."""
        self.assertEqual(self.gone_and_new("hashes"), (["3fa94c2"], ["3fa94c3"]))

    def test_bracket_labels(self):
        """RED on v1: v1 counts bracket labels and lists none."""
        self.assertEqual(self.gone_and_new("bracket-labels"), (["[R]"], []))

    def test_word_class_counts(self):
        """RED on v1: v1 has no hedge, condition, reason or negation counts."""
        self.assertEqual([self.data["old"][k] for k in WORD_CLASSES], [1, 1, 1, 1])
        self.assertEqual([self.data["new"][k] for k in WORD_CLASSES], [0, 1, 1, 1])
        self.assertEqual([self.data["delta"][k] for k in WORD_CLASSES], [-1, 0, 0, 0])

    def test_word_counts_per_word(self):
        """RED on v1: v1 has no per-word counts, so `unless` -> `if` is invisible."""
        self.assertEqual(self.data["words"]["conditions"],
                         {"unless": {"old": 1, "new": 0}, "if": {"old": 0, "new": 1}})
        self.assertEqual(self.data["words"]["negations"],
                         {"not": {"old": 1, "new": 0}, "never": {"old": 0, "new": 1}})

    def test_counts_match_the_token_lists(self):
        """RED on v1: v1's class names and counts differ (no paths, no short hashes)."""
        self.assertEqual([self.data["old"][k] for k in TOKEN_CLASSES], [3, 2, 2, 2, 2, 3, 2, 2])
        self.assertEqual([self.data["new"][k] for k in TOKEN_CLASSES], [3, 2, 2, 2, 2, 3, 2, 1])

    def test_exit_status_without_strict(self):
        """Guard, passes on v1: without --strict a difference still exits 0."""
        self.assertEqual(self.code, 0)


class CompareOther(unittest.TestCase):
    def test_curly_double_quotes_equal_straight(self):
        """RED on v1: v1 counts 2 straight-quoted strings and 0 curly ones (delta -2)."""
        _, d = compare("q1.md", "q2.md")
        self.assertEqual(d["delta"]["quoted-strings"], 0)
        self.assertEqual((d["disappeared"]["quoted-strings"], d["appeared"]["quoted-strings"]), ([], []))

    def test_curly_single_quotes_equal_straight(self):
        """RED on v1: v1 does not count ‘…’ strings (delta -2)."""
        _, d = compare("q1.md", "q3.md")
        self.assertEqual(d["delta"]["quoted-strings"], 0)
        self.assertEqual((d["disappeared"]["quoted-strings"], d["appeared"]["quoted-strings"]), ([], []))

    def test_multiset_difference(self):
        """RED on v1: v1 counts digits, and lists nothing when one of two `3`s goes."""
        _, d = compare("dup_old.md", "dup_new.md")
        self.assertEqual((d["disappeared"]["numbers"], d["appeared"]["numbers"]), (["3"], []))

    def test_hedges_dropped_with_no_token_change(self):
        """RED on v1: v1 has no word classes, so dropping `may` and `only` is invisible."""
        _, d = compare("words_old.md", "words_new.md")
        self.assertEqual(d["delta"]["hedges"], -2)
        self.assertEqual(d["words"]["hedges"], {"may": {"old": 1, "new": 0}, "only": {"old": 1, "new": 0}})
        self.assertEqual(d["delta"]["conditions"], 0)

    def test_same_file_has_no_difference(self):
        """RED on v1: v1 has no disappeared or appeared lists to be empty."""
        _, d = compare("cmp_old.md", "cmp_old.md")
        self.assertTrue(all(v == [] for v in d["disappeared"].values()))
        self.assertTrue(all(v == [] for v in d["appeared"].values()))
        self.assertTrue(all(v == 0 for v in d["delta"].values()))

    def test_text_output_lists_tokens(self):
        """RED on v1: v1's text output is a count table with no token lines."""
        code, out, _ = run("--compare", "dup_old.md", "dup_new.md")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("-- numbers", lines)
        self.assertIn("   - 3", lines)

    def test_text_output_lists_word_changes(self):
        """RED on v1: v1's text output has no word classes."""
        _, out, _ = run("--compare", "words_old.md", "words_new.md")
        lines = out.splitlines()
        self.assertIn("-- hedges", lines)
        self.assertIn("   may 1 -> 0", lines)


class CompareCounters(unittest.TestCase):
    def test_dropped_counters_are_counted(self):
        """RED on e885c908: the parent has no counters class, so dropping `but` and `however` is invisible."""
        _, d = compare("counter_old.md", "counter_new.md")
        self.assertEqual((d["old"]["counters"], d["new"]["counters"], d["delta"]["counters"]), (2, 0, -2))
        self.assertEqual(d["words"]["counters"],
                         {"but": {"old": 1, "new": 0}, "however": {"old": 1, "new": 0}})

    def test_dropped_but_of_but_only_is_a_counter_change(self):
        """RED on e885c908: the parent has no counters class, so the dropped `but` of `but only` is invisible."""
        _, d = compare("cmp_old.md", "cmp_new.md")
        self.assertEqual(d["words"]["counters"], {"but": {"old": 1, "new": 0}})

    def test_rewrite_of_all_but_one_is_a_counter_change(self):
        """RED on 56aebf56: the parent leaves out the `but` of `All but one`, so its rewrite to `except one` is no counter change.

        The `not yet` of the same rewrite stays out of the count.
        """
        _, d = compare("role_rewrite_old.md", "role_rewrite_new.md")
        self.assertEqual((d["old"]["counters"], d["new"]["counters"]), (1, 0))
        self.assertEqual(d["words"]["counters"], {"but": {"old": 1, "new": 0}})

    def test_text_output_lists_counter_changes(self):
        """RED on e885c908: the parent's text output has no counters class."""
        _, out, _ = run("--compare", "counter_old.md", "counter_new.md")
        lines = out.splitlines()
        self.assertIn("-- counters", lines)
        self.assertIn("   but 1 -> 0", lines)
        self.assertIn("   however 1 -> 0", lines)


if __name__ == "__main__":
    unittest.main()
