"""How the lint reads Markdown: sentence ends, blockquotes, frontmatter,
bold label lines, `1)` lists, list items wrapped across lines, the lines
that end an item or a paragraph, and the sentence limit for items."""
import unittest

from helpers import findings_of, kinds, label_findings, lint_report


class SentenceEnds(unittest.TestCase):
    def test_closing_quote_ends_a_sentence(self):
        """RED on v1: v1 splits only right after [.!?], so `run." Then` stays one 28-word sentence."""
        _, r = lint_report("quote.md")
        self.assertEqual(r["sentences"], 2)
        self.assertEqual(kinds(r), [])

    def test_closing_paren_ends_a_sentence(self):
        """RED on v1: v1 does not split after `.)`, so two 16-word sentences read as one of 32."""
        _, r = lint_report("paren_close.md")
        self.assertEqual(r["sentences"], 2)
        self.assertEqual(kinds(r), [])

    def test_closing_quote_before_lowercase_does_not_split(self):
        """Guard, passes on v1: a quote closed before a lowercase word stays in its sentence."""
        _, r = lint_report("quote_no_split.md")
        self.assertEqual(r["sentences"], 1)


class Blockquotes(unittest.TestCase):
    def test_blockquoted_list_items_are_items(self):
        """RED on v1: v1 keeps the `> ` prefix, so five quoted items read as one long sentence."""
        _, r = lint_report("bq_list.md")
        self.assertEqual(r["sentences"], 5)
        self.assertEqual(kinds(r), [])

    def test_nested_blockquote_is_unwrapped(self):
        """RED on v1: v1 reads `> > * ` lines as one paragraph and one long sentence."""
        _, r = lint_report("bq_nested.md")
        self.assertEqual(r["sentences"], 4)
        self.assertEqual(kinds(r), [])

    def test_blockquoted_paragraph_counts_its_sentences(self):
        """RED on v1: v1 does not split before `> `, so five quoted sentences read as one long one."""
        _, r = lint_report("bq_para.md")
        self.assertEqual(r["sentences"], 5)
        self.assertEqual(findings_of(r, "long-paragraph"), [("long-paragraph", 1)])
        self.assertEqual(findings_of(r, "long-sentence"), [])


class Frontmatter(unittest.TestCase):
    def test_leading_yaml_block_is_skipped(self):
        """RED on v1: v1 lints the frontmatter's long description line as prose."""
        _, r = lint_report("frontmatter.md")
        self.assertEqual([(f["kind"], f["line"]) for f in r["findings"]], [("semicolon", 10)])

    def test_rule_after_the_first_line_is_not_frontmatter(self):
        """Guard, passes on v1: a `---` rule inside the body hides nothing after it."""
        _, r = lint_report("hr_not_frontmatter.md")
        self.assertEqual([(f["kind"], f["line"]) for f in r["findings"]], [("semicolon", 5)])


class LabelsAndLists(unittest.TestCase):
    def test_bold_label_line_is_not_prose(self):
        """RED on v1: v1 joins a `**label**` line to the next sentence, making 29 words of 23."""
        _, r = lint_report("bold_label.md")
        self.assertEqual(r["sentences"], 1)
        self.assertEqual(kinds(r), [])

    def test_bold_label_line_is_not_a_sentence(self):
        """RED on v1: v1 counts a 5-word `**label:**` line as a sentence (3, not 2)."""
        _, r = lint_report("bold_label_alone.md")
        self.assertEqual(r["sentences"], 2)

    def test_paren_numbered_lines_are_items(self):
        """RED on v1: v1 knows only `1.` lists, so two `1)` items read as one 29-word sentence."""
        _, r = lint_report("paren_list.md")
        self.assertEqual(r["sentences"], 2)
        self.assertEqual(kinds(r), [])

    def test_clean_document_has_no_finding(self):
        """RED on v1: frontmatter, bold labels, a quoted list and a closing quote all make v1 findings."""
        _, r = lint_report("clean.md")
        self.assertEqual(r["findings"], [])


class WrappedItems(unittest.TestCase):
    def test_indented_continuation_is_one_sentence(self):
        """RED on e885c908: the parent reads an indented continuation line as a new paragraph, so a 26-word sentence reads as two of 13."""
        _, r = lint_report("wrap_indent_long.md")
        self.assertEqual(findings_of(r, "long-sentence"), [("long-sentence", 1)])
        self.assertEqual(r["sentences"], 1)

    def test_lazy_continuation_is_one_sentence(self):
        """RED on e885c908: the parent reads a lazy continuation line as a new paragraph, so a 28-word sentence reads as two."""
        _, r = lint_report("wrap_lazy_long.md")
        self.assertEqual(findings_of(r, "long-sentence"), [("long-sentence", 1)])
        self.assertEqual(r["sentences"], 1)

    def test_blank_line_ends_the_item(self):
        """Guard, passes on e885c908: a line after a blank line is a paragraph, not part of the item above."""
        _, r = lint_report("wrap_blank_ends.md")
        self.assertEqual(kinds(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_next_marker_starts_an_item(self):
        """Guard, passes on e885c908: a list marker after a wrapped item starts a new item, so no 32-word sentence."""
        _, r = lint_report("wrap_next_marker.md")
        self.assertEqual(findings_of(r, "long-sentence"), [])

    def test_heading_is_not_swallowed(self):
        """Guard, passes on e885c908: a Markdown heading right after an item is not part of the item."""
        _, r = lint_report("wrap_heading.md")
        self.assertEqual(findings_of(r, "long-sentence"), [])
        self.assertEqual(r["sentences"], 1)

    def test_table_row_is_not_swallowed(self):
        """Guard, passes on e885c908: a table row right after an item is not part of the item."""
        _, r = lint_report("wrap_table.md")
        self.assertEqual(findings_of(r, "long-sentence"), [])
        self.assertEqual(r["sentences"], 1)

    def test_jira_heading_is_not_swallowed(self):
        """Guard, passes on e885c908: a Jira `h3.` heading right after an item is not part of the item."""
        _, r = lint_report("wrap_jira_heading.txt")
        self.assertEqual(findings_of(r, "long-sentence"), [])
        self.assertEqual(r["sentences"], 1)


class ItemBoundaries(unittest.TestCase):
    """A list item continues only with paragraph text. A line that opens
    another block ends it, and so does the line after a closed code block."""

    def assert_two_sentences_no_finding(self, name):
        _, r = lint_report(name)
        self.assertEqual(kinds(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_dash_rule_ends_an_item(self):
        """RED on b24a2d58: the parent takes a `---` rule and the line after it into the item, so two sentences read as one of 28 words."""
        self.assert_two_sentences_no_finding("item_rule_dash.md")

    def test_star_rule_ends_a_list(self):
        """RED on b24a2d58: the parent takes a `***` rule into the item above, so the list goes on and `Probably:` has a `Verified:` sibling."""
        _, r = lint_report("item_rule_star.md")
        self.assertEqual(kinds(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_underscore_rule_ends_an_item(self):
        """RED on b24a2d58: the parent takes a `___` rule and the line after it into the item, so two sentences read as one of 32 words."""
        self.assert_two_sentences_no_finding("item_rule_underscore.md")

    def test_jira_rule_ends_an_item(self):
        """RED on b24a2d58: the parent takes a Jira `----` rule and the line after it into the item, so two sentences read as one of 30 words."""
        self.assert_two_sentences_no_finding("item_rule_jira.txt")

    def test_rule_ends_a_paragraph(self):
        """RED on b24a2d58: the parent joins the line after a `___` rule to the paragraph above, so two sentences read as one of 29 words."""
        self.assert_two_sentences_no_finding("para_rule.md")

    def test_blockquote_line_ends_an_item(self):
        """RED on b24a2d58: the parent removes the `>` before it splits blocks, so the quoted `Hypothesis:` joins the item as a second label."""
        _, r = lint_report("item_quote.md")
        self.assertEqual(label_findings(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_continuation_inside_one_blockquote_joins(self):
        """Guard, passes on b24a2d58: a continuation line inside the item's own blockquote is still part of the item."""
        _, r = lint_report("item_quote_inside.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_lazy_line_after_a_quoted_item_joins(self):
        """Guard, passes on b24a2d58: an unquoted paragraph line right after a quoted item is a lazy continuation of that item."""
        _, r = lint_report("item_quote_lazy.md")
        self.assertEqual(label_findings(r), [("label-twice", 1)])

    def test_blockquote_line_ends_a_paragraph(self):
        """RED on b24a2d58: the parent removes the `>` before it splits blocks, so a 3-sentence paragraph and a 2-sentence quote read as one long-paragraph."""
        _, r = lint_report("para_quote.md")
        self.assertEqual(kinds(r), [])
        self.assertEqual(r["sentences"], 5)

    def test_jira_bq_line_ends_an_item(self):
        """RED on b24a2d58: the parent takes a Jira `bq.` line into the item above, so its `Reported:` is a second label."""
        _, r = lint_report("item_bq_jira.txt")
        self.assertEqual(label_findings(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_fence_ends_an_item(self):
        """RED on b24a2d58: the parent takes a fenced block and the line after it into the item, so `Hypothesis:` is a second label."""
        _, r = lint_report("item_fence.md")
        self.assertEqual(label_findings(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_fence_under_an_item_adds_no_word(self):
        """RED on b24a2d58: the parent joins a fence under an item as the word CODE, so a 25-word item reads as a 26-word long-sentence."""
        _, r = lint_report("item_fence_indented.md")
        self.assertEqual(findings_of(r, "long-sentence"), [])
        self.assertEqual((r["sentences"], r["max_words"]), (1, 25))

    def test_jira_code_block_ends_an_item(self):
        """RED on b24a2d58: the parent takes a Jira {code} block and the line after it into the item, so `Hypothesis:` is a second label."""
        _, r = lint_report("item_code_jira.txt")
        self.assertEqual(label_findings(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_jira_noformat_block_ends_an_item(self):
        """RED on b24a2d58: the parent takes a Jira {noformat} block and the line after it into the item, so `Inferred:` is a second label."""
        _, r = lint_report("item_noformat_jira.txt")
        self.assertEqual(label_findings(r), [])
        self.assertEqual(r["sentences"], 2)

    def test_table_without_leading_pipe_ends_an_item(self):
        """RED on b24a2d58: the parent reads only `|`-led lines as table rows, so a bare GFM table joins the item as a 28-word sentence."""
        _, r = lint_report("item_table_bare.md")
        self.assertEqual(findings_of(r, "long-sentence"), [])
        self.assertEqual((r["sentences"], r["max_words"]), (1, 19))


class LongItems(unittest.TestCase):
    def test_5_sentence_item_is_long(self):
        """RED on b24a2d58: the parent applies the paragraph limit to paragraphs only, so a 5-sentence item makes no finding."""
        _, r = lint_report("long_item_5.md")
        self.assertEqual([(f["kind"], f["line"]) for f in r["findings"]], [("long-item", 1)])

    def test_4_sentence_item_is_not_long(self):
        """Guard, passes on b24a2d58: a 4-sentence wrapped item is within the limit and makes no finding."""
        _, r = lint_report("long_item_4.md")
        self.assertEqual(kinds(r), [])
        self.assertEqual(r["sentences"], 4)


if __name__ == "__main__":
    unittest.main()
