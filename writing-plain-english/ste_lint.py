#!/usr/bin/env python3
"""Plain-English lint for Markdown and Jira wiki markup.

Usage:
  ste_lint.py [--json] [--strict] [--labels A,B,C] FILE...
  ste_lint.py [--json] [--strict] --compare OLD NEW
  ste_lint.py [--json] inventory FILE

Lint checks:
  long-sentence   a sentence of more than 25 words
  long-paragraph  a paragraph of more than 4 sentences
  semicolon       a semicolon inside a sentence
  label-twice     a list item where two sentences start with an evidence label
  label-marker    a bracket marker such as [V] left in a list item
  label-unknown   a list item that starts with an unlisted "Word:", in a list
                  where a sibling item starts with a listed label
  noun-cluster    4 or more content words in a row with no known verb

All checks but noun-cluster are deterministic. noun-cluster is a heuristic,
so a person judges each of its findings. The evidence labels are
DEFAULT_LABELS unless --labels names others.

Before the checks, the lint skips a leading YAML frontmatter block, unwraps
blockquotes, and removes code (fenced, {code}, {noformat}, `...`, {{...}}),
URLs and link targets. Headings, table rows and whole-line bold labels are
not linted. Each finding names the line it came from, as L<n>. Deterministic
findings print first and heuristic ones after, each group in line order.

--compare OLD NEW lists, for each token class, the tokens that disappeared
and the tokens that appeared (a multiset difference). It also counts the
words of each word class. Equal lists and counts do not prove equal meaning.

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

# Word classes for --compare and inventory. A multi-word entry matches across
# any whitespace; "n't" matches as a word ending ("don't", "isn’t").
HEDGES = ("may", "might", "could", "possibly", "probably", "likely", "only", "just",
          "by itself", "alone", "appears", "seems", "suggests")
CONDITIONS = ("if", "unless", "only after", "otherwise", "when", "until", "except")
REASONS = ("because", "so", "since", "therefore", "which means")
NEGATIONS = ("not", "no", "never", "none", "nothing", "without", "n't")
WORD_CLASSES = {"hedges": HEDGES, "conditions": CONDITIONS,
                "reasons": REASONS, "negations": NEGATIONS}

# Evidence labels for the label checks; --labels replaces the set.
DEFAULT_LABELS = ("Verified", "Reported", "Observed", "Inferred", "Hypothesis", "Unknown")

MAX_SENTENCE_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 4

TOKEN_CLASSES = ("numbers", "code-spans", "code-blocks", "paths", "quoted-strings",
                 "links", "hashes", "bracket-labels")
DETERMINISTIC = {"long-sentence", "long-paragraph", "semicolon",
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
BLOCKQUOTE = r"(?m)^[ \t]{0,3}(?:>[ \t]?)+"
CODE_BLOCKS = (r"\{code[^}]*\}(.*?)\{code\}", r"\{noformat\}(.*?)\{noformat\}", r"```(.*?)```")
CODE_SPANS = (r"\{\{(.*?)\}\}", r"`([^`]*)`")
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
NUMBER = r"(?<![\w.])[vV]?\d(?:\w|[.,:/-](?=\d))*"

# Sentence ends: [.!?], then any closing quotes or brackets, then space, then
# a character that can start a sentence.
SENT_BREAK = r"[.!?][\"”’')\]]*\s+(?=[A-Z0-9\[\"“‘(*])"
# Capital-initial abbreviations keep their period (case-sensitive on purpose:
# a lowercase "no" entry would merge sentences ending in "no.").
ABBREV = r"\b(e\.g|i\.e|etc|vs|approx|Fig|No|Sec)\."
ITEM = r"^([*#-]+|\d+[.)])\s+(.*)"
WORD_COLON = r"([A-Z][A-Za-z]+):(?=\s|$)"

# strip_markup substitutions, in order. (pattern, replacement, flags, group):
# replacement None with a group emits the group's text instead.
_SUBS = [
    (FRONTMATTER, "", re.S, None),
    (BLOCKQUOTE, "", 0, None),
    (CODE_BLOCKS[0], " CODE. ", re.S, None),
    (CODE_BLOCKS[1], " CODE. ", re.S, None),
    (CODE_BLOCKS[2], " CODE. ", re.S, None),
    (CODE_SPANS[0], "X", 0, None),
    (CODE_SPANS[1], "X", 0, None),
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


def paragraphs(text: str, offs=None):
    """Yield (kind, text, offs, level) blocks; offs parallels text.

    kind is "para", "item" (each list item is its own block) or "sep" (a
    skipped heading, bold label or table line, which ends a list). level is
    an item's (indent, marker), None for the other kinds; the marker is the
    bullet as written ("*", "**", "#", "-") or "1." / "1)" for a number.
    """
    if offs is None:
        offs = list(range(len(text)))
    # Dialect sniff: a document with Jira markers treats '# ' lines as
    # ordered-list steps; pure Markdown treats them as headings.
    wiki = bool(re.search(r"(?m)^h[1-6]\.\s", text) or "{{" in text)
    pos = 0
    for m in re.finditer(r"\n\s*\n", text):
        yield from _block_parts(text[pos:m.start()], offs[pos:m.start()], wiki)
        pos = m.end()
    yield from _block_parts(text[pos:], offs[pos:], wiki)


def _skipped(s, wiki):
    """Headings (Jira hN., Markdown # outside wiki), bold labels, table rows."""
    return bool(re.match(r"^h[1-6]\.\s", s) or (not wiki and re.match(r"^#{1,6}\s", s))
                or re.match(r"^\*[^*]+\*:?$", s) or re.match(r"^\*\*[^*]+\*\*:?$", s)
                or s.startswith("|"))


def _block_parts(block, boffs, wiki=False):
    buf, buf_offs = [], []
    for m in re.finditer(r"[^\n]+", block):
        line = m.group(0)
        if not line.strip():
            continue
        s = line.strip()
        indent = len(line) - len(line.lstrip())
        soff = m.start() + indent
        if _skipped(s, wiki):
            if buf:
                yield _join(buf, buf_offs, "para")
                buf, buf_offs = [], []
            yield "sep", "", [], None
            continue
        mi = re.match(ITEM, s)
        if mi:
            if buf:
                yield _join(buf, buf_offs, "para")
                buf, buf_offs = [], []
            t = mi.group(2)
            o = soff + mi.start(2)
            marker = re.sub(r"\d+", "1", mi.group(1))
            yield "item", t, boffs[o:o + len(t)], (indent, marker)
        else:
            buf.append(s)
            buf_offs.append(boffs[soff:soff + len(s)])
    if buf:
        yield _join(buf, buf_offs, "para")


def _join(buf, buf_offs, kind):
    """Join paragraph lines with spaces; each join space maps to the first
    source offset of the line that follows it."""
    text, offs = "", []
    for i, (t, o) in enumerate(zip(buf, buf_offs)):
        if i:
            text += " "
            offs.append(o[0])
        text += t
        offs += o
    return kind, text, offs, None


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
    return re.compile(rf"(?:{alts}):(?=\s|$)")


def label_findings(items, labels, line_of):
    """label-twice, label-marker and label-unknown findings for list items.

    items: [(text, offs, level, run)]. Siblings share a run (no paragraph,
    heading or label line between them) and a level (indent and marker).
    """
    known = _label_re(labels)
    siblings = collections.defaultdict(list)
    for text, _, level, run in items:
        siblings[(run, level)].append(text)
    out = []
    for text, offs, level, run in items:
        line = line_of(offs[0]) if offs else 0
        ptext, starts = sentence_starts(text)
        found = [m.group(0)[:-1] for p in starts if (m := known.match(ptext, p))]
        if len(found) >= 2:
            out.append(("label-twice", text[:90], line))
        for m in re.finditer(BRACKET_LABEL, text):
            out.append(("label-marker", text[:90], line_of(offs[m.start()])))
        w = re.match(WORD_COLON, text)
        if w and w.group(1) not in labels and not known.match(text):
            others = list(siblings[(run, level)])
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
    run = 0
    for kind, block, boffs, level in paragraphs(text, offs):
        if kind == "item":
            items.append((block, boffs, level, run))
        else:
            run += 1  # a paragraph or a skipped line ends the list
        if kind == "sep":
            continue
        sents = sentences_map(block, boffs)
        if kind == "para" and len(sents) > MAX_PARAGRAPH_SENTENCES:
            findings.append(("long-paragraph", f"{len(sents)} sentences: {block[:70]}…",
                             line_of(boffs[0]) if boffs else 0))
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
    findings += label_findings(items, labels, line_of)
    # Deterministic classes first, then heuristics; stable by line (and by
    # original order within a line) so a reader never re-sorts the classes.
    findings.sort(key=lambda t: (0 if t[0] in DETERMINISTIC else 1, t[2]))
    return findings, lens, nsent


def _collapse(s):
    return " ".join(s.split())


def _code_block_token(m):
    inner = m.group(1)
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
    alts = []
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
    word_hits = {}
    for c, entries in WORD_CLASSES.items():
        hits = []
        for m in _word_re(entries).finditer(prose_text):
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
