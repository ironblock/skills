"""Evidence-label checks on list items: label-twice, label-marker, label-unknown."""
import unittest

from helpers import kinds, lint_report

LABEL_KINDS = {"label-twice", "label-marker", "label-unknown"}


def label_findings(report):
    return [(f["kind"], f["line"]) for f in report["findings"] if f["kind"] in LABEL_KINDS]


class LabelChecks(unittest.TestCase):
    def test_two_labels_in_one_item(self):
        """RED on v1: v1 has no label checks, so `Verified: … Hypothesis: …` in one item passes."""
        _, r = lint_report("labels_twice.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_bracket_marker_remains(self):
        """RED on v1: v1 has no label checks, so a `[V]` marker in an item passes."""
        _, r = lint_report("labels_marker.md")
        self.assertEqual(label_findings(r), [("label-marker", 2)])

    def test_unknown_label_beside_a_known_one(self):
        """RED on v1: v1 has no label checks, so `Probably:` beside `Verified:` siblings passes."""
        _, r = lint_report("labels_unknown.md")
        self.assertEqual(label_findings(r), [("label-unknown", 2)])

    def test_labels_inside_a_blockquote(self):
        """RED on v1: v1 neither unwraps blockquotes nor checks labels."""
        _, r = lint_report("bq_labels.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_default_set_flags_words_outside_it(self):
        """RED on v1: v1 has no label checks; `Seen:` and `Guessed:` sit beside a `Verified:` sibling."""
        _, r = lint_report("labels_override.md")
        self.assertEqual(label_findings(r), [("label-unknown", 1), ("label-unknown", 2)])

    def test_labels_option_replaces_the_set(self):
        """RED on v1: v1 has no --labels option; it reads the flag and its value as file names."""
        code, r = lint_report("labels_override.md", "--labels", "Seen,Guessed")
        self.assertEqual(code, 0)
        self.assertEqual(label_findings(r), [("label-unknown", 3)])


class LabelKnownGood(unittest.TestCase):
    def test_one_known_label_per_item(self):
        """Guard, passes on v1: one known label per item makes no finding of any kind."""
        _, r = lint_report("labels_good.md")
        self.assertEqual(kinds(r), [])

    def test_word_colon_list_without_labels(self):
        """Guard, passes on v1: `Word:` items are not label-unknown when no sibling has a known label."""
        _, r = lint_report("labels_unknown_no_sibling.md")
        self.assertEqual(kinds(r), [])

    def test_list_after_a_paragraph_is_another_list(self):
        """Guard, passes on v1: a paragraph between two lists makes them separate lists."""
        _, r = lint_report("labels_separate_lists.md")
        self.assertEqual(kinds(r), [])

    def test_nested_items_are_not_siblings_of_their_parent(self):
        """Guard, passes on v1: `Note:` items nested under a `Verified:` item are another list."""
        _, r = lint_report("labels_nested.md")
        self.assertEqual(kinds(r), [])

    def test_jira_nested_items_are_not_siblings_of_their_parent(self):
        """Guard, passes on v1: Jira `**` items under a `*` item are another list."""
        _, r = lint_report("labels_jira_nested.txt")
        self.assertEqual(kinds(r), [])


if __name__ == "__main__":
    unittest.main()
