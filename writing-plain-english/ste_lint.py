#!/usr/bin/env python3
"""Plain-English lint for Markdown and Jira wiki markup.

Usage:
  ste_lint.py [--json] [--strict] [--labels A,B,C] FILE...
  ste_lint.py [--json] [--strict] --compare OLD NEW
  ste_lint.py [--json] inventory FILE

Lint checks:
  long-sentence   a sentence of more than 25 words
  long-paragraph  a paragraph of more than 4 sentences
  long-item       a list item of more than 4 sentences
  semicolon       a semicolon inside a sentence
  label-twice     a list item where two sentences start with an evidence label
  label-marker    a bracket marker such as [V] left in a list item
  label-unknown   a list item that starts with an unlisted "Word:", in a list
                  where a sibling item starts with a listed label
  noun-cluster    4 or more content words in a row with no known verb

All checks but noun-cluster are deterministic. noun-cluster is a heuristic,
so a person judges each of its findings. The evidence labels are
DEFAULT_LABELS unless --labels names others. A label is read plain
(Verified:) or bold (**Verified:**, **Verified**:, Jira *Verified:*).

Before the checks, the lint skips a leading YAML frontmatter block, unwraps
blockquotes, and removes code (fenced with ``` or ~~~, {code}, {noformat},
`...`, {{...}}), Jira panel tags ({quote}, {panel}, {info}, {note}, {tip},
{warning}), URLs and link targets. Headings, table rows, thematic breaks,
code blocks and whole-line bold labels are not linted. A paragraph or a
list item takes in the paragraph text under it, indented or not (a Markdown
lazy continuation). It ends at a blank line, a list marker ("-", "+", "*",
"1." or "1)", Jira "#" or "**"), a heading (Markdown "#" or setext, Jira
hN.), a table row (led by "|", or under a GFM header row such as "a | b"
over "---|---"), a thematic break (---, ***, ___, Jira ----), a code block
(the line after it starts afresh), a Jira panel tag, a line that opens a
blockquote ("> " one level deeper, or Jira bq.), or a bold label line. A
line inside the same blockquote continues it. A blank line with fewer ">"
ends the blockquote and the lists in it. In Markdown, a line of "-" or
"=" right under a paragraph line makes that paragraph a setext heading;
Jira has no setext headings, so "----" there is a rule.

In Markdown, a list item also holds the code blocks and paragraphs indented
to its content column (where the text after its marker starts), after a
blank line or not. Each one ends the item's paragraph but not the item or
its list: the items before and after it are still siblings, and the
sentences after it count toward the item's long-item and label checks. A
line at a smaller indent that is not a lazy continuation ends the list.
Jira lists have no content column; a Jira item with a longer marker ("**",
"##") is nested in the nearest item above it with a shorter one.

Each finding names the line it came from, as L<n>. Deterministic findings
print first and heuristic ones after, each group in line order.

Error direction. Where a construct is ambiguous, each check errs toward its
cheap error. The prose checks (long-sentence, long-paragraph, long-item,
semicolon, label-*) end a block early rather than join lines into it. A
missed finding is cheaper than a false one, because a false finding makes
the rewriting model change text that was fine. The inventory and --compare
count a word rather than guess its role. A word counted in a role outside
its class only adds a checklist item, but a real counter-clause hidden by a
role guess is a fidelity miss. So a word is left out (NOT_COUNTERS) only in
a fixed phrase that is never a counter-clause, concession, condition,
reason, hedge or negation in any context. Resolving roles by syntax belongs
to an optional parse layer, not to this file.

Stop rule. This lint approximates CommonMark and Jira block structure; it
is not a parser. It handles the constructs that are common in tickets:
lists, nested lists, fences, blockquotes, tables, headings, thematic breaks
and Jira panels such as {code}, {noformat} and {quote}. Rarer constructs
are listed in README.md under "Known limits", each with an example, and are
not handled here.

--compare OLD NEW lists, for each token class, the tokens that disappeared
and the tokens that appeared (a multiset difference). It also counts the
words of each word class (hedges, conditions, reasons, negations and
counter-clauses). Equal lists and counts do not prove equal meaning.

inventory FILE lists each token and each word-class word with its line, as a
checklist for a rewrite. --compare and inventory read the whole file,
frontmatter included.

Exit status: 0 by default. With --strict, 1 if any deterministic finding
exists, or, with --compare, if any token disappeared. 2 for an operational
error (bad invocation, unreadable file), with the reason on stderr.
"""
import bisect
import collections
import hashlib
import json
import re
import statistics
import sys

# Word classes for --compare and inventory. These lists are a baseline, not a
# detector: each is a fixed set of surface words, counted per class over the
# whole text. A word can be counted where it plays another role (the "so" of
# "so many" counts a reason), and an equal count does not prove an equal
# claim. A multi-word entry matches across any whitespace and claims its words
# in every class: "only after" is one condition, not also a hedge, and the
# "so" of "even so" is not a reason. "n't" matches as a word ending ("don't",
# "isn’t").
HEDGES = ("may", "might", "could", "possibly", "probably", "likely", "only", "just",
          "by itself", "alone", "appears", "seems", "suggests")
CONDITIONS = ("if", "unless", "only after", "otherwise", "when", "until", "except")
REASONS = ("because", "so", "since", "therefore", "which means")
NEGATIONS = ("not", "no", "never", "none", "nothing", "without", "n't")
COUNTERS = ("but", "however", "although", "though", "yet", "whereas", "nevertheless",
            "nonetheless", "even so", "despite", "in spite of")
WORD_CLASSES = {"hedges": HEDGES, "conditions": CONDITIONS,
                "reasons": REASONS, "negations": NEGATIONS, "counters": COUNTERS}

# Counter words in fixed phrases that are never a counter-clause (the error-
# direction rule in the module docstring): "not only ... but also" (and),
# "not yet" (still not), "as yet" (so far) and "as though" (as if). Each
# pattern matches one such use and names the counter word as group w; that
# word is not counted. Every other counter word is counted, whatever its
# role, because its phrase can also start a counter-clause: "all but one"
# ("We retried them all but one still hangs"), "yet another" ("We fixed the
# leak, yet another leak appeared"), "however many" ("However many users
# still see the error") and "however we" ("It passes locally however we see
# failures"). "Even though" is counted.
NOT_COUNTERS = (
    r"\bnot\s+only\b[^.!?]*?\b(?P<w>but)\s+also\b",
    r"\bnot\s+(?P<w>yet)\b",
    r"\bas\s+(?P<w>yet)\b",
    r"\bas\s+(?P<w>though)\b",
)

# Evidence labels for the label checks; --labels replaces the set.
DEFAULT_LABELS = ("Verified", "Reported", "Observed", "Inferred", "Hypothesis", "Unknown")

MAX_SENTENCE_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 4

TOKEN_CLASSES = ("numbers", "code-spans", "code-blocks", "paths", "quoted-strings",
                 "links", "hashes", "bracket-labels")
DETERMINISTIC = {"long-sentence", "long-paragraph", "long-item", "semicolon",
                 "label-twice", "label-marker", "label-unknown"}

FUNCTION = set("""a an the and or but nor so yet for of to in on at by with from into onto over under
about after before between through during without within than then as if when while because
that which who whom whose what where why how this these those it its they them their there here
is are was were be been being am do does did done has have had having can could will would shall
should may might must not no all any each every some many more most less least few other such
only also just very too still even already again once both either neither per via i we you he she
our your his her us me my""".split())
# More words that end a noun run; noun_cluster_spans treats them as FUNCTION.
CONNECTORS = set("across against among upon toward beneath beyond despite except plus unlike worth".split())
# Unambiguous high-frequency verbs: a run containing one is a predicate, not a
# noun stack. Words that are also common nouns in technical prose (set, run,
# check, load, record, report, update, log, retry, block, list, map, name,
# note, state, claim, point, means, calls, reads, guarantee, package) and
# words that are often adjectives or modifiers (complete, using) are left out.
VERBS = set("""handles provides contains includes returns requires exposes ignores allows denies
covers applies matches depends differs enables disables sends waits needs uses use keeps gives takes
makes shows writes adds removes deletes creates publishes submits triggers starts stops fails
helps refers belongs relies extends refreshes completes supports holds loses wins avoids prevents
describes explains tells asks remains becomes seems looks sorts
invoke invokes replace replaces add implement remain""".split())

# Markup patterns, shared by the lint and by --compare/inventory.
FRONTMATTER = r"\A\ufeff?---[ \t]*\n(?:.*?\n)?---[ \t]*(?=\n|\Z)"
QUOTE_PREFIX = r"[ \t]{0,3}(?:>[ \t]?)+"
BLOCKQUOTE = r"(?m)^" + QUOTE_PREFIX
# A fence closes only at its own kind of fence, and whichever of ``` and ~~~
# opens first wins, so a ``` inside a ~~~ block is code. A ~~~ fence closes at
# a line of its own that holds 3 or more ~ and nothing else. A pattern's groups
# hold a block's inside, one group per kind of block.
CODE_BLOCKS = (r"\{code[^}]*\}(.*?)\{code\}", r"\{noformat\}(.*?)\{noformat\}",
               r"```(.*?)```|~~~(.*?\n)[ \t]*~~~+[ \t]*(?m:$)")
CODE_SPANS = (r"\{\{(.*?)\}\}", r"`([^`]*)`")
# A Jira panel tag, opening or closing. strip_markup turns it into a line
# break, so the panel's text is a paragraph of its own.
JIRA_PANEL = r"\{(?:quote|panel|info|note|tip|warning)(?::[^}\n]*)?\}"
# A citation or metadata span such as [S: file.py:12; other.py:40] is
# provenance punctuation, not prose. The lint removes it after code (so a "]"
# inside a code span cannot end the match) and before links.
CITATION = r"\[[A-Z][A-Za-z]{0,3}: [^\]]*\]"
WIKI_LINK = r"\[([^|\]]+)\|([^\]]+)\]"
MD_LINK = r"\[([^\]]+)\]\(([^)]+)\)"
URL = r"https?://[^\s<>\"]*[^\s<>\".,;:!?)\]'”’]"
BRACKET_LABEL = r"\[[A-Z][A-Za-z]{0,7}\]"
QUOTES = (r'"((?:[^"\n]|\n(?![ \t]*\n))*)"',
          r"“((?:[^“”\n]|\n(?![ \t]*\n))*)”",
          r"‘((?:[^‘’\n]|’(?=\w)|\n(?![ \t]*\n))*)’(?!\w)")
PATH = r"""(?<![\w./~:@+-])(?:
      (?P<rooted>(?:~|\.\.?)?(?:/[\w.@+-]+)+/?)
    | (?P<relative>[\w@+-][\w.@+-]*(?:/[\w.@+-]*)+)
    | (?P<file>[\w-][\w.-]*\.[a-z][a-z0-9]{0,5})
    )(?<!\.)(?![\w/@+-])"""  # a final "." ends the sentence, not the path
HASH = r"\b[0-9a-fA-F]{7,}\b"
LIST_MARKER = r"(?m)^[ \t]*\d+[.)](?=[ \t])"
# Block-level lines that end a paragraph or a list item (see paragraphs).
THEMATIC_BREAK = r"^(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$"  # also Jira ----
SETEXT_UNDERLINE = r"^(?:=+|-+)$"  # under a paragraph line, in Markdown only
TABLE_DELIMITER = r"^\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?$"  # with a "|" in it
CODE_OPENERS = ("```", "~~~", "{code", "{noformat}")  # where a code block's source starts
CODE_WORD = " CODE. "  # what strip_markup leaves of a code block
JIRA_QUOTE = r"^bq\.\s"
NUMBER = r"(?<![\w.])[vV]?\d(?:\w|[.,:/-](?=\d))*"

# Sentence ends: [.!?], then any closing quotes or brackets, then space, then
# a character that can start a sentence.
SENT_BREAK = r"[.!?][\"”’')\]]*\s+(?=[A-Z0-9\[\"“‘(*])"
# Capital-initial abbreviations keep their period (case-sensitive on purpose:
# a lowercase "no" entry would merge sentences ending in "no.").
ABBREV = r"\b(e\.g|i\.e|etc|vs|approx|Fig|No|Sec)\."
ITEM = r"^([*#-]+|\+|\d+[.)])\s+(.*)"
# A label as written: plain (Verified:) or bold (**Verified:**, **Verified**:,
# or Jira *Verified:*). {w} is the pattern of the label word.
LABEL_FORMS = r"(?:{w}:|\*\*{w}:\*\*|\*\*{w}\*\*:|\*{w}:\*)(?=\s|$)"
WORD_COLON = LABEL_FORMS.format(w=r"([A-Z][A-Za-z]+)")

# strip_markup substitutions, in order. (pattern, replacement, flags, group):
# replacement None with a group emits the group's text instead.
_SUBS = [
    (FRONTMATTER, "", re.S, None),
    (BLOCKQUOTE, "", 0, None),
    (CODE_BLOCKS[0], CODE_WORD, re.S, None),
    (CODE_BLOCKS[1], CODE_WORD, re.S, None),
    (CODE_BLOCKS[2], CODE_WORD, re.S, None),
    (CODE_SPANS[0], "X", 0, None),
    (CODE_SPANS[1], "X", 0, None),
    (JIRA_PANEL, "\n", 0, None),
    (CITATION, " ", 0, None),
    (WIKI_LINK, None, 0, 1),  # keep link text
    (MD_LINK, None, 0, 1),  # keep link text
    (URL, "URL", 0, None),
]


def _sub_map(pattern, repl, text, offs, flags=0, group=None):
    """re.sub that tracks each emitted character's source offset.

    offs[i] is the origin (source offset) of text[i]. Each character of a
    replacement maps to the match's start; when `group` is set, the group's
    text is emitted and each of its characters maps to its own source
    position. Returns (new_text, new_offs).
    """
    out, new_offs, pos = [], [], 0
    for m in re.finditer(pattern, text, flags):
        out += text[pos:m.start()]
        new_offs += offs[pos:m.start()]
        if group is not None:
            for i in range(m.start(group), m.end(group)):
                out.append(text[i])
                new_offs.append(offs[i])
        else:
            origin = offs[m.start()]
            out += repl
            new_offs += [origin] * len(repl)
        pos = m.end()
    out += text[pos:]
    new_offs += offs[pos:]
    return "".join(out), new_offs


def strip_markup_map(text: str):
    """Markup-free text plus a stripped-offset -> source-offset map.

    The map keeps line numbers correct across substitutions that change
    lengths and drop newlines (a fenced block collapses its newlines; a naive
    line count over the stripped text would misnumber everything after it).
    """
    offs = list(range(len(text)))
    for pattern, repl, flags, group in _SUBS:
        text, offs = _sub_map(pattern, repl, text, offs, flags, group)
    return text, offs


def strip_markup(text: str) -> str:
    return strip_markup_map(text)[0]


def paragraphs(text: str, offs=None, raw=None):
    """Yield (kind, text, offs, key) blocks; offs parallels text.

    text is markup-free text, offs maps it to raw (its source), and raw is
    read for what stripping removed: blockquote prefixes and code block
    markup. Without raw, text is its own source. kind is one of:

      para  a paragraph outside every list item. It ends the lists above it.
      item  the first paragraph of a list item. key is its sibling key: items
            with one key are siblings in one list (the same indent, marker,
            blockquote depth and enclosing item, and no paragraph, code
            block, sep or end of a blockquote between them at that level).
      part  a later paragraph of an item, indented to its content column
            after a code block or a blank line. key is the item's number (0
            for the first item yielded).
      sep   a skipped line: a heading, bold label, table row, thematic break,
            or a code block line outside every item. It ends every list.

    A line continues the paragraph above it, indented or not (a Markdown
    lazy continuation), only when it is paragraph text. A list marker starts
    an item. A GFM header row is a "|" line over a delimiter row such as
    "---|---", and the "|" lines under it are rows. A Jira bq. line, or a
    line one blockquote level deeper than the paragraph's first line, starts
    a new paragraph. A line at the same or a shallower level continues it,
    inside one blockquote or lazily after it. A line that starts a paragraph
    or holds a code block belongs to the innermost open item whose content
    column it reaches at the same blockquote depth. With no such item, it
    ends every list. A blank line ends a paragraph, not a list, but a blank
    line with fewer ">" than the open lists ends their blockquote and them.
    A Jira item belongs to the nearest open item above it with a shorter
    marker ("*" above "**", "#" above "##").
    """
    if offs is None:
        offs = list(range(len(text)))
    if raw is None:
        raw = text
    # Dialect sniff: a document with Jira markers treats '# ' lines as
    # ordered-list steps; pure Markdown treats them as headings.
    wiki = bool(re.search(r"(?m)^h[1-6]\.\s", text) or "{{" in text)
    lines, starts, pos = [], [], 0  # (stripped line, indent, offset in text), None for a blank line
    for line in text.split("\n"):
        s = line.strip()
        indent = len(line) - len(line.lstrip())
        lines.append((s, indent, pos + indent) if s else None)
        starts.append(pos)
        pos += len(line) + 1
    code_lead = len(CODE_WORD) - len(CODE_WORD.lstrip())  # a code line's indent, less this, is its fence's
    buf, buf_offs = [], []  # the open paragraph's lines
    owner, key, first, depth = None, None, False, 0  # its item (None: no item), key, first?, quote depth
    open_items = []  # innermost last: {"col": content column, "depth", "level", "no": item number, "breaks"}
    count = run = 0  # items started; ends of every list (paragraph or sep outside items, quote end)
    table = False

    def flush():
        if buf:
            t, o = _join(buf, buf_offs)
            if owner is None:
                yield "para", t, o, None
            elif first:
                yield "item", t, o, key
            else:
                yield "part", t, o, owner["no"]

    def holder(indent, d, level=0):
        """The index in open_items of the innermost item that holds a line
        at indent and blockquote depth d, or -1. In Markdown that is an item
        whose content column the line reaches. Jira lists have no content
        column: an item whose marker has length level is held by an item
        with a shorter marker, and no other line (level 0) is held."""
        for k in range(len(open_items) - 1, -1, -1):
            o = open_items[k]
            if o["depth"] == d and (o["level"] < level if wiki else indent >= o["col"]):
                return k
        return -1

    for i, line in enumerate(lines):
        if line is None:
            yield from flush()
            buf, buf_offs, table = [], [], False
            at = starts[i]
            blank_depth = _quote_depth(raw, offs[at]) if at < len(offs) else 0
            if open_items and blank_depth < open_items[-1]["depth"]:
                open_items.clear()  # fewer ">": the blockquote and its lists end
                run += 1
            continue
        s, indent, soff = line
        src = offs[soff]
        d = _quote_depth(raw, src)
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        table = "|" in s and (table or (nxt is not None and _delimiter_row(nxt[0])))
        code = s == CODE_WORD.strip() and raw.startswith(CODE_OPENERS, src)
        if code:
            k = holder(indent - code_lead, d)
            if k >= 0:  # a code block in an item ends the item's paragraph, not the item
                yield from flush()
                buf, buf_offs = [], []
                del open_items[k + 1:]
                open_items[k]["breaks"] += 1
                continue
        setext = (not wiki and buf and owner is None and d == depth
                  and re.match(SETEXT_UNDERLINE, s))
        if setext or table or code or _skipped(s, wiki) or re.match(THEMATIC_BREAK, s):
            if not setext:  # a setext heading's text is a heading, not prose
                yield from flush()
            buf, buf_offs = [], []
            open_items.clear()
            run += 1
            yield "sep", "", [], None
            continue
        mi = re.match(ITEM, s)
        if mi:
            yield from flush()
            marker = mi.group(1)
            level = len(marker) if re.fullmatch(r"[*#-]+", marker) else 1  # Jira nesting
            k = holder(indent, d, level)
            parent = open_items[k] if k >= 0 else None
            del open_items[k + 1:]
            gap = mi.start(2) - mi.end(1)  # 5 or more spaces: the text is indented code
            owner = {"col": indent + mi.end(1) + (gap if gap <= 4 else 1), "depth": d,
                     "level": level, "no": count, "breaks": 0}
            key = (run, parent and parent["no"], parent and parent["breaks"], indent,
                   re.sub(r"\d+", "1", marker), d)
            open_items.append(owner)
            count += 1
            first, depth = True, d
            t, o = mi.group(2), soff + mi.start(2)
            buf, buf_offs = [t], [offs[o:o + len(t)]]
            continue
        if buf and (d > depth or re.match(JIRA_QUOTE, s)):
            yield from flush()
            buf, buf_offs = [], []
        if not buf:  # a new paragraph: in the innermost item that holds it, or outside every list
            k = holder(indent, d)
            del open_items[k + 1:]
            if k >= 0:
                owner, first = open_items[k], False
                owner["breaks"] += 1
            else:
                owner = None
                run += 1
            depth = d
        buf.append(s)
        buf_offs.append(offs[soff:soff + len(s)])
    yield from flush()


def _skipped(s, wiki):
    """Headings (Jira hN., Markdown # outside wiki), bold labels, table rows."""
    return bool(re.match(r"^h[1-6]\.\s", s) or (not wiki and re.match(r"^#{1,6}\s", s))
                or re.match(r"^\*[^*]+\*:?$", s) or re.match(r"^\*\*[^*]+\*\*:?$", s)
                or s.startswith("|"))


def _quote_depth(raw, src):
    """The blockquote depth (number of ">") of the source line holding src."""
    m = re.compile(QUOTE_PREFIX).match(raw, raw.rfind("\n", 0, src) + 1)
    return m.group(0).count(">") if m else 0


def _delimiter_row(s):
    return "|" in s and bool(re.match(TABLE_DELIMITER, s))


def _join(buf, buf_offs):
    """(text, offs) of paragraph lines joined with spaces; each join space
    maps to the first source offset of the line that follows it."""
    text, offs = "", []
    for i, (t, o) in enumerate(zip(buf, buf_offs)):
        if i:
            text += " "
            offs.append(o[0])
        text += t
        offs += o
    return text, offs


def sentences_map(par: str, poffs):
    """[(sentence, offs)] with <3-word fragments dropped; offs parallels the
    sentence text and carries source offsets."""
    par, poffs = _sub_map(ABBREV, None, par, poffs, group=1)
    out, pos = [], 0
    bounds = [m.end() for m in re.finditer(SENT_BREAK, par)]
    for b in bounds + [len(par)]:
        seg = par[pos:b]
        lead = len(seg) - len(seg.lstrip())
        trail = len(seg) - len(seg.rstrip())
        text = seg.strip()
        if len(text.split()) >= 3:
            out.append((text, poffs[pos + lead:pos + b - trail]))
        pos = b
    return out


def sentences(par: str):
    return [t for t, _ in sentences_map(par, list(range(len(par))))]


def sentence_starts(par: str):
    """(text, [start offsets]) of every sentence in par, fragments included."""
    par = re.sub(ABBREV, r"\1", par)
    return par, [0] + [m.end() for m in re.finditer(SENT_BREAK, par)]


def words(s: str):
    return re.findall(r"[A-Za-z][A-Za-z0-9'’/-]*", s)


def noun_cluster_spans(s: str):
    """[(cluster, start_char)]: 4+ consecutive content words. A run
    containing a verb is a predicate, not a noun stack: skipped."""
    out, run, run_start, has_verb = [], [], 0, False
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9'’-]*|[^\sA-Za-z]", s):
        tok = m.group(0)
        w = tok.lower()
        content = tok[0].isalpha() and w not in FUNCTION and w not in CONNECTORS and not re.search(r"(ed|ly)$", w)
        if content:
            if not run:
                run_start = m.start()
            run.append(tok)
            if w in VERBS:
                has_verb = True
        else:
            if len(run) >= 4 and not has_verb:
                out.append((" ".join(run), run_start))
            run = []
            has_verb = False  # per run: a verb in one run must not mask later runs
    if len(run) >= 4 and not has_verb:
        out.append((" ".join(run), run_start))
    return out


def noun_clusters(s: str):
    return [c for c, _ in noun_cluster_spans(s)]


def _label_re(labels):
    alts = "|".join(re.escape(lb) for lb in sorted(labels, key=len, reverse=True))
    return re.compile(LABEL_FORMS.format(w=f"(?:{alts})"))


def label_findings(items, labels, line_of):
    """label-twice, label-marker and label-unknown findings for list items.

    items: [{"parts": [(text, offs)], "key": key}], where an item's first
    part is its first paragraph and items with one key are siblings (see
    paragraphs). label-twice counts the labelled sentences of all the parts.
    """
    known = _label_re(labels)
    siblings = collections.defaultdict(list)
    for item in items:
        siblings[item["key"]].append(item["parts"][0][0])
    out = []
    for item in items:
        text, offs = item["parts"][0]
        line = line_of(offs[0]) if offs else 0
        found = 0
        for t, _ in item["parts"]:
            ptext, starts = sentence_starts(t)
            found += sum(1 for p in starts if known.match(ptext, p))
        if found >= 2:
            out.append(("label-twice", text[:90], line))
        for t, o in item["parts"]:
            for m in re.finditer(BRACKET_LABEL, t):
                out.append(("label-marker", t[:90], line_of(o[m.start()])))
        w = re.match(WORD_COLON, text)
        word = w and next(g for g in w.groups() if g)  # one group per label form
        if w and word not in labels and not known.match(text):
            others = list(siblings[item["key"]])
            others.remove(text)
            if any(known.match(o) for o in others):
                out.append(("label-unknown", text[:90], line))
    return out


def lint(name: str, raw: str, labels=DEFAULT_LABELS):
    findings, lens, items = [], [], []
    text, offs = strip_markup_map(raw)
    line_starts = [0] + [m.end() for m in re.finditer("\n", raw)]

    def line_of(src):
        return bisect.bisect_right(line_starts, src)

    nsent = 0
    for kind, block, boffs, key in paragraphs(text, offs, raw):
        if kind == "sep":
            continue
        sents = sentences_map(block, boffs)
        if kind == "para":
            if len(sents) > MAX_PARAGRAPH_SENTENCES:
                findings.append(("long-paragraph", f"{len(sents)} sentences: {block[:70]}…",
                                 line_of(boffs[0]) if boffs else 0))
        else:
            if kind == "item":  # "at": where a long-item finding goes, before the item's other findings
                items.append({"parts": [], "key": key, "sentences": 0, "at": len(findings)})
            item = items[-1] if kind == "item" else items[key]
            item["parts"].append((block, boffs))
            item["sentences"] += len(sents)
        for s, soffs in sents:
            n = len(words(s))
            lens.append(n)
            nsent += 1
            sl = line_of(soffs[0]) if soffs else 0
            if n > MAX_SENTENCE_WORDS:
                findings.append(("long-sentence", f"{n}w>{MAX_SENTENCE_WORDS}: {s[:90]}…", sl))
            if ";" in s:
                findings.append(("semicolon", s[:90], sl))
            for c, cstart in noun_cluster_spans(s):
                findings.append(("noun-cluster", c,
                                 line_of(soffs[cstart]) if cstart < len(soffs) else sl))
    for item in reversed(items):  # the paragraph limit, over all of an item's paragraphs
        if item["sentences"] > MAX_PARAGRAPH_SENTENCES:
            block, boffs = item["parts"][0]
            findings.insert(item["at"], ("long-item", f"{item['sentences']} sentences: {block[:70]}…",
                                         line_of(boffs[0]) if boffs else 0))
    findings += label_findings(items, labels, line_of)
    # Deterministic classes first, then heuristics; stable by line (and by
    # original order within a line) so a reader never re-sorts the classes.
    findings.sort(key=lambda t: (0 if t[0] in DETERMINISTIC else 1, t[2]))
    return findings, lens, nsent


def _collapse(s):
    return " ".join(s.split())


def _code_block_token(m):
    inner = next(g for g in m.groups() if g is not None)  # the kind of block that matched
    body = inner.split("\n", 1)[1] if "\n" in inner else inner  # drop the info string line
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "(empty)")
    return f"{hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]} {first[:40]}"


def _path_token(m):
    tok = m.group(0)
    if m.group("rooted"):
        return tok
    if m.group("relative"):
        last = tok.rstrip("/").rsplit("/", 1)[-1]
        return tok if tok.endswith("/") or re.search(r"\.[A-Za-z]\w*$", last) else None
    return tok if len(tok.rsplit(".", 1)[0]) >= 2 else None


def _hash_token(m):
    tok = m.group(0)
    return tok if re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok) else None


def _word_re(entries):
    """One pattern for entries; with no entries, a pattern that never matches."""
    alts = [r"(?!)"] if not entries else []
    for e in sorted(entries, key=len, reverse=True):
        if e == "n't":
            alts.append(r"(?<=[A-Za-z])n['’]t(?![\w'’])")
        else:
            alts.append(r"(?<![\w'’])" + r"\s+".join(map(re.escape, e.split())) + r"(?![\w'’])")
    return re.compile("|".join(alts), re.I)


def extract(raw: str):
    """Tokens and word-class words of one text, each with its source line.

    Returns {"tokens": {class: [(token, line)]}, "words": {class: [(as
    written, entry, line)]}}, each list in source order. Each class is taken
    from what the earlier classes left, so a number inside a code span, path
    or quoted string is not counted twice. Words are counted in prose and
    quoted strings, not in code, link targets or paths.
    """
    text, offs = _sub_map(BLOCKQUOTE, "", raw, list(range(len(raw))))
    line_starts = [0] + [m.end() for m in re.finditer("\n", raw)]

    def line_of(i):
        return bisect.bisect_right(line_starts, offs[i])

    tok, prose = list(text), list(text)
    found = {c: [] for c in TOKEN_CLASSES}

    def blank(buf, a, b):
        for i in range(a, b):
            if buf[i] != "\n":
                buf[i] = " "

    def take(cls, specs, in_prose="blank"):
        """Take one class. specs: [(pattern, flags, token)]. Where matches of
        different patterns overlap, the one that starts first (the outer
        one) wins, so “a "b" c” is one quoted string, not two."""
        buf = "".join(tok)
        cands = sorted(((m, token) for p, flags, token in specs for m in re.finditer(p, buf, flags)),
                       key=lambda c: (c[0].start(), -c[0].end()))
        end = 0
        for m, token in cands:
            if m.start() < end:
                continue
            t = token(m)
            if t is None:
                continue
            end = m.end()
            found[cls].append((m.start(), t))
            blank(tok, m.start(), m.end())
            if in_prose == "blank":
                blank(prose, m.start(), m.end())
            elif in_prose == "text" and m.re.groups:  # keep a link's text as prose
                blank(prose, m.start(), m.start(1))
                blank(prose, m.end(1), m.end())
            elif in_prose == "text":
                blank(prose, m.start(), m.end())

    def link(m):  # link text as written, even where a code span was blanked
        return f"[{_collapse(text[m.start(1):m.end(1)])}]({m.group(2).strip()})"

    take("code-blocks", [(p, re.S, _code_block_token) for p in CODE_BLOCKS])
    take("code-spans", [(p, 0, lambda m: _collapse(m.group(1))) for p in CODE_SPANS])
    take("links", [(MD_LINK, 0, link), (WIKI_LINK, 0, link), (URL, 0, lambda m: f"<{m.group(0)}>")],
         in_prose="text")
    take("quoted-strings", [(p, 0, lambda m: _collapse(m.group(1))) for p in QUOTES], in_prose="keep")
    take("bracket-labels", [(BRACKET_LABEL, 0, lambda m: m.group(0))])
    take("paths", [(PATH, re.X, _path_token)])
    take("hashes", [(HASH, 0, _hash_token)], in_prose="keep")
    for m in re.finditer(LIST_MARKER, "".join(tok)):
        blank(tok, m.start(), m.end())
    take("numbers", [(NUMBER, 0, lambda m: m.group(0))], in_prose="keep")

    tokens = {c: [(t, line_of(pos)) for pos, t in sorted(found[c], key=lambda x: x[0])]
              for c in TOKEN_CLASSES}
    prose_text = "".join(prose)
    # A multi-word entry claims its words in every class: the multi-word
    # entries are matched on the prose and then blanked, and the single-word
    # entries are matched on what is left. A counter word in another role
    # (NOT_COUNTERS) is blanked for the counters class only. Each step is one
    # pass over the text.
    multi = {c: list(_word_re([e for e in entries if " " in e]).finditer(prose_text))
             for c, entries in WORD_CLASSES.items()}
    rest = list(prose_text)
    for ms in multi.values():
        for m in ms:
            blank(rest, m.start(), m.end())
    left = dict.fromkeys(WORD_CLASSES, "".join(rest))
    for p in NOT_COUNTERS:
        for m in re.finditer(p, prose_text, re.I):
            blank(rest, *m.span("w"))
    left["counters"] = "".join(rest)
    word_hits = {}
    for c, entries in WORD_CLASSES.items():
        singles = _word_re([e for e in entries if " " not in e]).finditer(left[c])
        hits = []
        for m in sorted([*multi[c], *singles], key=lambda m: m.start()):
            written = _collapse(m.group(0))
            hits.append((written, written.lower().replace("’", "'"), line_of(m.start())))
        word_hits[c] = hits
    return {"tokens": tokens, "words": word_hits}


def compare(old_raw: str, new_raw: str) -> dict:
    a, b = extract(old_raw), extract(new_raw)
    res = {"old": {}, "new": {}, "delta": {}, "disappeared": {}, "appeared": {}, "words": {}}
    for c in TOKEN_CLASSES:
        ca = collections.Counter(t for t, _ in a["tokens"][c])
        cb = collections.Counter(t for t, _ in b["tokens"][c])
        res["old"][c], res["new"][c] = sum(ca.values()), sum(cb.values())
        res["disappeared"][c] = list((ca - cb).elements())
        res["appeared"][c] = list((cb - ca).elements())
    for c, entries in WORD_CLASSES.items():
        wa = collections.Counter(e for _, e, _ in a["words"][c])
        wb = collections.Counter(e for _, e, _ in b["words"][c])
        res["old"][c], res["new"][c] = sum(wa.values()), sum(wb.values())
        res["words"][c] = {e: {"old": wa[e], "new": wb[e]} for e in entries if wa[e] or wb[e]}
    for c in res["old"]:
        res["delta"][c] = res["new"][c] - res["old"][c]
    return res


def inventory(raw: str) -> dict:
    x = extract(raw)
    return {"tokens": {c: [{"token": t, "line": ln} for t, ln in x["tokens"][c]] for c in TOKEN_CLASSES},
            "words": {c: [{"word": w, "line": ln} for w, _, ln in x["words"][c]] for c in WORD_CLASSES}}


USAGE = ("usage: ste_lint.py [--json] [--strict] [--labels A,B,C] FILE...\n"
         "       ste_lint.py [--json] [--strict] --compare OLD NEW\n"
         "       ste_lint.py [--json] inventory FILE")


class UsageError(Exception):
    pass


def parse_args(argv):
    opts = {"json": False, "strict": False, "compare": False, "labels": DEFAULT_LABELS}
    pos = []
    it = iter(argv)
    for a in it:
        if a == "--json":
            opts["json"] = True
        elif a == "--strict":
            opts["strict"] = True
        elif a == "--compare":
            opts["compare"] = True
        elif a == "--labels" or a.startswith("--labels="):
            value = a.split("=", 1)[1] if "=" in a else next(it, "")
            labels = tuple(x.strip() for x in value.split(",") if x.strip())
            if not labels:
                raise UsageError("--labels needs a comma-separated list")
            opts["labels"] = labels
        elif a.startswith("--"):
            raise UsageError(f"unknown option {a}")
        else:
            pos.append(a)
    mode = "compare" if opts["compare"] else "inventory" if pos[:1] == ["inventory"] else "lint"
    if mode == "inventory":
        pos = pos[1:]
    need = {"compare": 2, "inventory": 1}.get(mode)
    if (need and len(pos) != need) or not pos:
        raise UsageError(None)
    return mode, pos, opts


def read_text(path):
    """The file's text, or None after one line on stderr."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        # directory (IsADirectoryError), missing file, permission, ...
        print(f"ste_lint: cannot read {path}", file=sys.stderr)
    except UnicodeDecodeError:
        print(f"ste_lint: cannot read {path} (not UTF-8 text)", file=sys.stderr)
    return None


def main_compare(paths, opts):
    old_raw, new_raw = read_text(paths[0]), read_text(paths[1])
    if old_raw is None or new_raw is None:
        return 2
    res = compare(old_raw, new_raw)
    failed = opts["strict"] and any(res["disappeared"].values())
    if opts["json"]:
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 1 if failed else 0
    print(f"== compare {paths[0]} {paths[1]}")
    print(f"   {'class':16}{'old':>6}{'new':>6}{'delta':>7}")
    for c in res["old"]:
        print(f"   {c:16}{res['old'][c]:>6}{res['new'][c]:>6}{res['delta'][c]:>7}")
    for c in TOKEN_CLASSES:
        if res["disappeared"][c] or res["appeared"][c]:
            print(f"-- {c}")
            for t in res["disappeared"][c]:
                print(f"   - {t}")
            for t in res["appeared"][c]:
                print(f"   + {t}")
    for c in WORD_CLASSES:
        changed = {e: v for e, v in res["words"][c].items() if v["old"] != v["new"]}
        if changed:
            print(f"-- {c}")
            for e, v in changed.items():
                print(f"   {e} {v['old']} -> {v['new']}")
    return 1 if failed else 0


def main_inventory(path, opts):
    raw = read_text(path)
    if raw is None:
        return 2
    inv = inventory(raw)
    if opts["json"]:
        print(json.dumps({"file": path, **inv}, indent=1, ensure_ascii=False))
        return 0
    print(f"== inventory {path}")
    for group, key in (("tokens", "token"), ("words", "word")):
        for c, entries in inv[group].items():
            if entries:
                print(f"-- {c}")
                for e in entries:
                    print(f"   [ ] L{e['line']} {e[key]}")
    return 0


def main_lint(paths, opts):
    report, errors = {}, 0
    for p in paths:
        raw = read_text(p)
        if raw is None:
            errors += 1
            continue
        f, lens, n = lint(p, raw, opts["labels"])
        kinds = {}
        for k, _, _ in f:
            kinds[k] = kinds.get(k, 0) + 1
        report[p] = {
            "sentences": n,
            "median_words": statistics.median(lens) if lens else 0,
            "max_words": max(lens or [0]),
            "counts": kinds,
            "findings": [{"kind": k, "line": ln, "text": msg} for k, msg, ln in f],
        }
    if opts["json"]:
        print(json.dumps(report, indent=1))
    else:
        for p, r in report.items():
            print(f"== {p}: {r['sentences']} sentences, median {r['median_words']}w, "
                  f"max {r['max_words']}w, {r['counts']}")
            for fd in r["findings"]:
                print(f"   L{fd['line']} {fd['kind']:14} {fd['text']}")
    if errors:
        return 2
    failed = any(fd["kind"] in DETERMINISTIC for r in report.values() for fd in r["findings"])
    return 1 if opts["strict"] and failed else 0


def main(argv):
    try:
        mode, paths, opts = parse_args(argv)
    except UsageError as e:
        if e.args[0]:
            print(f"ste_lint: {e.args[0]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    if mode == "compare":
        return main_compare(paths, opts)
    if mode == "inventory":
        return main_inventory(paths[0], opts)
    return main_lint(paths, opts)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
