# skills

Agent skills, each in its own folder with a `SKILL.md` that agent harnesses can load.

## writing-plain-english

For rewriting a ticket, pull request description or design note so that a reader who wasn't in the session can act on it, without changing what it claims. It also covers writing your own ticket for that reader.

- `SKILL.md` is the skill.
- `ste_lint.py` is the lint it runs. It needs Python 3 and nothing else.
- `README.md` in the folder describes the lint and its known limits.

The skill was tuned by having an open-weights model rewrite real, agent-written tickets with it. After each round, a fresh-context reader and a judge checked every rewrite against its source, and the skill was revised. The rule the judge used: a rewrite changes a ticket materially when a reader without the session would act differently, or believe something different or with different confidence.

To use it, copy the folder into your harness's skills directory.

Nothing here comes from any organization's private work.
