"""Exit status: --strict fails on deterministic findings and on lost tokens;
operational errors exit 2."""
import unittest

from helpers import run


def status(*args):
    return run(*args)[0]


class StrictLint(unittest.TestCase):
    def test_deterministic_finding_fails(self):
        """RED on v1: v1 has no --strict; it reads the flag as a file name and exits 2."""
        self.assertEqual(status("--strict", "long_sentence_26.md"), 1)

    def test_label_finding_fails(self):
        """RED on v1: v1 has no --strict and no label checks."""
        self.assertEqual(status("--strict", "labels_marker.md"), 1)

    def test_heuristic_finding_does_not_fail(self):
        """RED on v1: v1 has no --strict; it exits 2, not 0, on a noun-cluster-only file."""
        self.assertEqual(status("--strict", "noun_cluster.md"), 0)

    def test_clean_file_passes(self):
        """RED on v1: v1 has no --strict; it exits 2, not 0, on a clean file."""
        self.assertEqual(status("--strict", "labels_good.md"), 0)

    def test_any_file_with_a_finding_fails_the_run(self):
        """RED on v1: v1 has no --strict."""
        self.assertEqual(status("--strict", "labels_good.md", "semicolon.md"), 1)

    def test_long_item_fails(self):
        """RED on b24a2d58: the parent has no long-item class, so a 5-sentence item exits 0 under --strict."""
        self.assertEqual(status("--strict", "long_item_5.md"), 1)

    def test_findings_without_strict_exit_0(self):
        """Guard, passes on v1: findings are advisory without --strict."""
        self.assertEqual(status("long_sentence_26.md", "labels_marker.md"), 0)


class StrictCompare(unittest.TestCase):
    def test_disappeared_token_fails(self):
        """RED on v1: v1 has no --strict for --compare; it exits 2 on the unknown flag."""
        self.assertEqual(status("--strict", "--compare", "append.md", "q1.md"), 1)

    def test_appeared_token_only_passes(self):
        """RED on v1: v1 has no --strict for --compare; it exits 2 on the unknown flag."""
        self.assertEqual(status("--strict", "--compare", "q1.md", "append.md"), 0)

    def test_word_count_drop_alone_passes(self):
        """RED on v1: v1 has no --strict; under it only a lost token fails, not a lost hedge."""
        self.assertEqual(status("--strict", "--compare", "words_old.md", "words_new.md"), 0)

    def test_disappeared_token_without_strict_exits_0(self):
        """Guard, passes on v1: --compare without --strict exits 0."""
        self.assertEqual(status("--compare", "append.md", "q1.md"), 0)


class OperationalErrors(unittest.TestCase):
    def test_missing_file(self):
        """Guard, passes on v1: an unreadable file exits 2."""
        code, out, err = run("no_such_file.md")
        self.assertEqual(code, 2)
        self.assertTrue(err.strip())

    def test_missing_file_under_strict(self):
        """Guard, passes on v1 by accident (v1 cannot read `--strict` either): exit 2 wins over 1."""
        self.assertEqual(status("--strict", "no_such_file.md", "semicolon.md"), 2)

    def test_compare_needs_two_files(self):
        """Guard, passes on v1: --compare with one file exits 2."""
        self.assertEqual(status("--compare", "q1.md"), 2)

    def test_compare_missing_file(self):
        """Guard, passes on v1: --compare with an unreadable file exits 2."""
        self.assertEqual(status("--compare", "q1.md", "no_such_file.md"), 2)

    def test_inventory_needs_one_file(self):
        """Guard, passes on v1 by accident (v1 cannot read `inventory`): inventory alone exits 2."""
        self.assertEqual(status("inventory"), 2)

    def test_inventory_missing_file(self):
        """Guard, passes on v1 by accident (v1 cannot read either name): exit 2."""
        self.assertEqual(status("inventory", "no_such_file.md"), 2)

    def test_no_arguments(self):
        """Guard, passes on v1: no file exits 2."""
        self.assertEqual(status(), 2)


if __name__ == "__main__":
    unittest.main()
