Scratch rebuild of a plain-English lint. Nothing here comes from any organization's private work. Nothing leaves this repo without the maintainer's review. Park rule: see the maintainer's plan (private).

## Known limits

`ste_lint.py` approximates CommonMark and Jira block structure; it is not a parser (see the stop rule in its docstring). The constructs below are rarer in tickets than the ones it handles, so it does not handle them. Each entry has an example (` / ` separates its lines) and says what the lint does with it. Where the lint is wrong, it errs toward its cheap error: a missed finding, or an extra word counted.

Block structure:

- An indented code block (four spaces, no fence) is read as prose: `Build it with this command.` / (blank line) / `    build --all --jobs 8` counts the command as a sentence.
- A blockquote, heading, table or rule indented under a list item ends the list: `- Verified: the copy ran.` / `  > The owner says it ran twice.` / `- Probably: the timer fired twice.` reads as two lists, so `Probably:` has no sibling.
- A setext underline indented under an item's text is read as a rule, so the heading text is linted as the item's prose: `- Summary of the nightly run` / `  ---`.
- Items at different indents are read as two lists, where CommonMark reads one: `- Verified: the copy ran.` / ` - Probably: the timer fired twice.` makes no label-unknown finding.
- A `` ``` `` fence closes at the next `` ``` ``, even inside a line or inside a longer fence, and the rest of the block is read as prose: `` ``` `` / `` echo ``` > marks.txt; echo done `` / `` ``` `` is a semicolon finding.
- A numbered line that CommonMark reads as paragraph text (a number other than 1 right under a paragraph line) is read as a list item: `The count at the end of the vote was` / `2. Nobody abstained.` ends the paragraph at the number.
- A tab counts as one column of indentation, so a fence indented with one tab under a `- ` item ends the list: `- Verified: the copy ran.` / `` <TAB>``` `` / `<TAB>copy --all` / `` <TAB>``` `` / `- Probably: the timer fired twice.` reads as two lists.
- HTML blocks and comments are read as prose: `<!-- Describe the steps you took; list the commands too -->` is a semicolon finding.
- The dialect is sniffed from Jira `hN.` headings: a closed `{{...}}` span is stripped before the sniff reads the text, so a Jira text with no `hN.` heading is read as Markdown. Its `# ` lines are headings, and a `----` rule right under a paragraph line makes that paragraph a setext heading: `Run the export twice; check the log after each run.` / `----` makes no finding.
- In a Jira text read as Markdown, an indented paragraph after a blank line is part of the item above it, as in Markdown: `* Verified: the copy ran.` / (blank line) / `  Inferred: it ran on the spare host.` is a label-twice finding.
- Jira inline macros such as `{color}` are read as text, so their names count as words: `The {color:red}export failed{color} twice last night on the spare host before the backup window closed and the night shift came in for the late jobs.` reads a 25-word sentence as 28 words.

Word roles (the inventory and `--compare` count a word rather than guess its role):

- `all but`, `anything but` and `nothing but` before a number, a number word or `a few` are not counted, even in a counter-clause that lacks its comma: `We fixed them all but two came back.`
- `however` before a degree word is not counted, even in a counter-clause that lacks its comma: `However much of the data was lost.`
- `however` before a pronoun in mid-clause is not counted, even in a counter-clause that lacks its comma: `The fix works however we need a test.`
- A counter word in another role is counted where its phrase can also start a counter-clause, so it adds a checklist item: `The upgrade was anything but smooth.` counts one counter.
