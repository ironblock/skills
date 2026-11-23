"""The checks and output shapes kept from v1. Each pair is a text that must
make the finding and a text that must not."""
import unittest

from helpers import findings_of, kinds, lint_report, run


class KeptChecks(unittest.TestCase):
    def test_26_word_sentence_is_long(self):
        """Guard, passes on v1: a 26-word sentence is a long-sentence."""
        _, r = lint_report("long_sentence_26.md")
        self.assertEqual(kinds(r), ["long-sentence"])

    def test_25_word_sentence_is_not_long(self):
        """Guard, passes on v1: a 25-word sentence makes no finding."""
        _, r = lint_report("long_sentence_25.md")
        self.assertEqual(kinds(r), [])

    def test_5_sentence_paragraph_is_long(self):
        """Guard, passes on v1: a 5-sentence paragraph is a long-paragraph."""
        _, r = lint_report("long_para_5.md")
        self.assertEqual(kinds(r), ["long-paragraph"])

    def test_4_sentence_paragraph_is_not_long(self):
        """Guard, passes on v1: a 4-sentence paragraph with no semicolon makes no finding."""
        _, r = lint_report("long_para_4.md")
        self.assertEqual(kinds(r), [])

    def test_semicolon_in_prose(self):
        """Guard, passes on v1: a semicolon in a sentence is a finding."""
        _, r = lint_report("semicolon.md")
        self.assertEqual(kinds(r), ["semicolon"])

    def test_semicolon_in_code_span_is_not_prose(self):
        """Guard, passes on v1: a semicolon inside a code span makes no finding."""
        _, r = lint_report("semicolon_in_code.md")
        self.assertEqual(kinds(r), [])

    def test_noun_run_is_a_noun_cluster(self):
        """Guard, passes on v1: four content words in a row are a noun-cluster."""
        _, r = lint_report("noun_cluster.md")
        self.assertEqual(kinds(r), ["noun-cluster"])

    def test_run_with_a_verb_is_not_a_noun_cluster(self):
        """Guard, passes on v1: a run that holds a known verb makes no finding."""
        _, r = lint_report("noun_cluster_verb.md")
        self.assertEqual(kinds(r), [])

    def test_line_numbers_survive_a_code_fence(self):
        """Guard, passes on v1: a finding after a fenced block keeps its source line."""
        _, r = lint_report("fence.md")
        self.assertEqual(findings_of(r, "semicolon"), [("semicolon", 8)])


class KeptShapes(unittest.TestCase):
    def test_json_report_shape(self):
        """Guard, passes on v1: the JSON report keeps v1's keys."""
        _, r = lint_report("long_sentence_26.md")
        self.assertEqual(set(r), {"sentences", "median_words", "max_words", "counts", "findings"})
        self.assertEqual(r["counts"], {"long-sentence": 1})
        self.assertEqual(set(r["findings"][0]), {"kind", "line", "text"})

    def test_text_report_shape(self):
        """Guard, passes on v1: the text report keeps v1's header and finding lines."""
        _, out, _ = run("long_sentence_26.md")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("== long_sentence_26.md: 1 sentences, median 26w, max 26w"), lines[0])
        self.assertTrue(lines[1].startswith("   L1 long-sentence  26w>25: "), lines[1])


if __name__ == "__main__":
    unittest.main()
