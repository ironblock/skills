---
name: writing-plain-english
description: Use when writing or rewriting a ticket, pull request description, design note or report for a reader who was not in your session (a teammate, a future agent, a reviewer). Also use when a draft has long sentences, chains of clauses, project terms nobody defined, or references like "the fix above" that only make sense inside the session.
---

# Writing for a reader who wasn't there

The reader of a ticket has the ticket and the project's shared files, but not your session. They need to find out quickly what is wanted, what is known, and when the work is done.

Long sentences are not what makes most tickets hard to act on. Missing structure is, and so are references to things the reader never saw.

This skill covers two jobs: rewriting someone else's text, and writing your own.

## Rewriting someone else's text

Change as little as you can. You are fixing what stops a cold reader, not redoing the ticket. Fix these:
- A sentence that `ste_lint.py --strict` flags as long, or for a semicolon: split it.
- Steps, conditions or branches folded into one paragraph: put them in a list. Give each branch its own short block ("If the cache is warm: …").
- A reference into a session or thread that the ticket's own text resolves: name the thing. For example, "the fix above" becomes the fix's name when the ticket names it two lines up.

Leave everything else as it is, word for word. A sentence the lint doesn't flag keeps its exact words, and that includes the done conditions. Keep each term as the source writes it, without swapping it for a synonym or a more specific name. Also keep the source's headings, checkboxes and links.

If a sentence can be read two ways, keep its words. Don't pick one reading for the reader.

If the lint flags nothing, and nothing is folded or resolvable, the ticket needs no rewrite. Write it out unchanged, and say so in your reply.

When you split a sentence, each new sentence keeps what governed the old one: its condition, its hedge, its scope and its source. For example, take "The sample config says checkpoints resume every 2,048 tokens and are kept in the recurrent cache." Split, it becomes "The sample config says checkpoints resume every 2,048 tokens. The sample config also says they are kept in the recurrent cache."

Each piece is a whole sentence that names its subject. Don't start one with "It" or "This" if the reader could not tell what that means.

When one condition governs several clauses, write the condition once and list the clauses under it. For example, "Below the threshold, the reformat is rejected, the parser's output stands, and an event is logged" becomes "Below the threshold:" followed by a list of the three clauses.

A quotation is someone's exact words. Keep it word for word, with its quotation marks, even when the lint flags it.

Leave a flagged sentence whole when you can't split it safely. That is when you aren't sure how a clause parses, or when one clause happens because of another and a split would cut that link. A long sentence is cheaper than a wrong one.

Add nothing that the source doesn't say. In particular, don't add any of these:
- **A status line,** unless the source has a sentence that states one. A "Kind:" line or an author tag such as "[Dispatch]" is not a status. Keep it as it is.
- **A done condition or steps,** if the source has none.
- **An evidence label** on a claim the source states without one. A flat statement stays flat. A list of suspects or options stays a list of options.
- **Who said something,** if the source doesn't say.
- **A definition of a term.** The reader works on this project. If you don't know what a term means, leave it, and mention it in your reply instead of in the ticket.
- **An "Unknown" bullet** for something you couldn't work out. Use "Unknown" only for open questions the source itself raises.

The meaning stays fixed. Before you start, list what the source contains:

    python3 <this skill's folder>/ste_lint.py inventory OLD.md

It lists the source's numbers, code, links, hedges ("may", "likely", "only"), conditions ("if", "unless"), reasons ("because"), counter-clauses ("but") and negations, each with its line number. Each one should still be in your version, attached to the same claim, with the same strength. Also keep who said or decided something, and where a finding came from.

Some items on the list are false alarms, such as a "but" that means "except". Skip those: the list is a checklist, not a verdict.

## Writing your own

Use this order, and leave out any part that has nothing in it:

1. **Status**, in one sentence, if there is one to state ("This is a partial fix.").
2. **What to do**: the steps. Number them only when the order matters.
3. **Branches**: when the work depends on a condition, give each case its own short block. Don't fold both cases into one list.
4. **Done when**: conditions that are true when the work is finished ("The export includes archived records."). These are not more steps.
5. **What is known**: the evidence, one claim per bullet, each starting with how it is known:
   - **Verified:** it was checked, and you name or link the check.
   - **Observed:** it was seen happening, but not checked.
   - **Reported:** someone said so. Name who.
   - **Inferred:** you reasoned it from other evidence. Name the evidence.
   - **Unknown:** an open question that matters for the work.

   If the project has its own words for these, use them.
6. **Links**: related tickets, what this depends on, and what must land first.

You can use a term bare if it is defined somewhere every worker on the project reads. That means the README, the docs, AGENTS.md, a glossary or the code. If a term exists only in your session or your notes, explain it in one clause the first time you use it. If the project already has a name for the thing, use the project's name instead of yours.

Replace references into your session ("the fix above", "as we found earlier", "this approach") with what they refer to.

## Sentences

- Keep a sentence to about 25 words, and a paragraph to about 4 sentences. Put steps and conditions in lists.
- Put one idea in each sentence. Use active voice with a named actor, unless the actor doesn't matter.
- Write "rules that give each run its own directory", not a stack of nouns like "per-run directory allocation rules".
- Use one word for one thing. Don't switch from "review" to "approval" for variety. If you need to be specific, qualify the word ("code review").

## Check before you hand it on

1. Run `python3 <this skill's folder>/ste_lint.py --strict NEW.md`. It reports long sentences, long paragraphs, semicolon chains and label problems. Fix them, unless a split would separate a claim from its reason or its condition, or you can't tell how a clause parses. Its `noun-cluster` lines are only hints: change the phrase only if it really is a stack of nouns.
2. When you rewrite, run `python3 <this skill's folder>/ste_lint.py --compare OLD.md NEW.md`. It lists what disappeared and what appeared. A hedge, condition or reason that disappeared has changed the claim. Put it back, unless you moved it into another sentence about the same claim.
3. When you rewrite, read your version against the source one last time. Anything in yours that the source doesn't say comes out.
4. Read your version as someone who wasn't there. Can you say what the problem is, and when the work is done, in one sentence each?

A clean lint means the sentences are short and the markers are accounted for. It doesn't mean the ticket is good. Steps 3 and 4 decide that.

## Example of a rewrite

Before:

> Verified: the backup job got slower after the storage migration, and the disk is 95% full; we think the migration's new compression setting is to blame but that's inference, and whether turning it off restores the old speed is unknown. Per the discussion above, try the flag first, then if that doesn't help roll back.

After:

> **What to do**
> 1. Turn off the new compression setting on the backup volume.
> 2. Check whether the backup is back to its old speed.
>
> **If it is still slow:** roll back the storage migration.
>
> **What is known**
> - Verified: the backup job got slower after the storage migration.
> - Verified: the disk is 95% full.
> - Inferred: the migration's new compression setting causes the slowdown.
> - Unknown: whether turning the setting off restores the old speed.

The source's one label covered both of its first two claims, so both bullets keep it. The source itself called the cause an inference and the fix's effect unknown, so those labels come from it too. "The discussion above" pointed into a thread, but the source's next sentence says what was decided, so the steps say it directly. The source has no done condition, so the rewrite adds none.
