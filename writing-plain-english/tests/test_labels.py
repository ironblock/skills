"""Evidence-label checks on list items: label-twice, label-marker, label-unknown.
Labels are read plain (Verified:) or bold (**Verified:**, **Verified**:, Jira
*Verified:*), and a list item includes its continuation lines."""
import unittest

from helpers import kinds, label_findings, lint_report


class LabelChecks(unittest.TestCase):
    def test_two_labels_in_one_item(self):
        """RED on v1: v1 has no label checks, so `Verified: … Hypothesis: …` in one item passes."""
        _, r = lint_report("labels_twice.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_bracket_marker_remains(self):
        """RED on v1: v1 has no label checks, so a `[V]` marker in an item passes."""
        _, r = lint_report("labels_marker.md")
        self.assertEqual(label_findings(r), [("label-marker", 2)])

    def test_author_tags_are_not_markers(self):
        """RED on 7b101ef: any [Xxxx] bracket in an item is flagged, so "[Dispatch]" and "[TODO]" give false label-marker findings."""
        _, r = lint_report("labels_marker_author_tags.md")
        self.assertEqual(label_findings(r), [])

    def test_short_codes_and_label_words_are_markers(self):
        """Guard: a 1-3 letter code and a label word in brackets are still flagged after the narrowing."""
        _, r = lint_report("labels_marker_codes.md")
        self.assertEqual(label_findings(r), [("label-marker", 1), ("label-marker", 2)])

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


class SeparateLists(unittest.TestCase):
    """Items in two lists are not siblings. A list inside a blockquote and a
    list outside it are two lists, and so are two blockquotes split by an
    unquoted blank line. In Jira, nested lists under two parents are two
    lists."""

    def test_quoted_list_then_unquoted_item(self):
        """RED on 56aebf56: the parent's sibling key leaves out blockquote depth, so the unquoted `Probably:` item is a sibling of the quoted `Verified:` item."""
        _, r = lint_report("labels_bq_then_item.md")
        self.assertEqual(label_findings(r), [])

    def test_unquoted_item_then_quoted_item(self):
        """RED on 56aebf56: the parent's sibling key leaves out blockquote depth, so the quoted `Maybe:` item is a sibling of the unquoted `Verified:` item."""
        _, r = lint_report("labels_item_then_bq.md")
        self.assertEqual(label_findings(r), [])

    def test_quoted_lists_split_by_a_blank_line(self):
        """RED on 56aebf56: the parent reads an unquoted blank line as a blank line inside the blockquote, so `Likely:` in the second blockquote is a sibling of `Observed:` in the first."""
        _, r = lint_report("labels_bq_lists_blank.md")
        self.assertEqual(label_findings(r), [])

    def test_quoted_blank_line_keeps_the_list(self):
        """Guard, passes on 56aebf56: a `>` blank line is inside the blockquote, so the items around it are siblings and `Perhaps:` is label-unknown."""
        _, r = lint_report("labels_bq_loose_list.md")
        self.assertEqual(label_findings(r), [("label-unknown", 3)])

    def test_jira_star_lists_under_two_parents(self):
        """RED on 56aebf56: the parent gives Jira items no parent, so `** Probably:` under the second item is a sibling of `** Verified:` under the first."""
        _, r = lint_report("labels_jira_nested_parents.txt")
        self.assertEqual(label_findings(r), [])

    def test_jira_hash_lists_under_two_parents(self):
        """RED on 56aebf56: the parent gives Jira items no parent, so `## Maybe:` under the second step is a sibling of `## Verified:` under the first."""
        _, r = lint_report("labels_jira_nested_numbered.txt")
        self.assertEqual(label_findings(r), [])

    def test_jira_siblings_under_one_parent_and_after_a_nested_list(self):
        """Guard, passes on 56aebf56: `**` items under one Jira parent are siblings, and so are the `*` items before and after them."""
        _, r = lint_report("labels_jira_nested_siblings.txt")
        self.assertEqual(label_findings(r), [("label-unknown", 5), ("label-unknown", 6)])


class WrappedLabels(unittest.TestCase):
    def test_second_label_on_indented_continuation(self):
        """RED on e885c908: the parent reads the indented continuation line as a paragraph, so its `Hypothesis:` is not checked."""
        _, r = lint_report("wrap_indent_label.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_second_label_on_lazy_continuation(self):
        """RED on e885c908: the parent reads the lazy continuation line as a paragraph, so its `Inferred:` is not checked."""
        _, r = lint_report("wrap_lazy_label.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_wrapped_item_keeps_its_siblings(self):
        """RED on e885c908: the parent's continuation paragraph ends the list, so `Maybe:` has no `Verified:` sibling."""
        _, r = lint_report("wrap_sibling_unknown.md")
        self.assertEqual(label_findings(r), [("label-unknown", 3)])


class BoldLabels(unittest.TestCase):
    def test_bold_labels_colon_inside(self):
        """RED on e885c908: the parent does not read `**Verified:**` as a label, so two bold labels per item pass."""
        _, r = lint_report("bold_twice_inside.md")
        self.assertEqual(label_findings(r), [("label-twice", 1), ("label-twice", 2), ("label-twice", 3)])

    def test_bold_labels_colon_outside(self):
        """RED on e885c908: the parent does not read `**Verified**:` as a label."""
        _, r = lint_report("bold_twice_outside.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_jira_bold_labels(self):
        """RED on e885c908: the parent does not read Jira bold `*Observed:*` as a label."""
        _, r = lint_report("jira_bold_twice.txt")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_bold_unknown_label_beside_bold_known(self):
        """RED on e885c908: the parent reads neither `**Probably:**` nor its bold siblings as labels."""
        _, r = lint_report("bold_unknown.md")
        self.assertEqual(label_findings(r), [("label-unknown", 2)])

    def test_bold_labels_with_labels_option(self):
        """RED on e885c908: the parent does not read `**Seen:**` as a label, even when --labels names it."""
        _, r = lint_report("bold_custom.md", "--labels", "Seen,Guessed")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_one_bold_label_per_item(self):
        """Guard, passes on e885c908: one bold known label per item, in any of the three forms, is no label finding."""
        _, r = lint_report("bold_labels_good.md")
        self.assertEqual(label_findings(r), [])


if __name__ == "__main__":
    unittest.main()
