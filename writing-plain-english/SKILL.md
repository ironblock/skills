---
name: writing-plain-english
description: Use when writing or rewriting a ticket, pull request description, design note, handoff or report for a reader who was not in the session, including readers of English as a second language or through machine translation. Also use when a draft has long sentences, semicolons, arrows used as verbs, idioms, noun stacks, if/else steps in one list, references like "the fix above", or evidence labels (Verified, Observed, Reported, Inferred, Unknown) that must survive a rewrite.
---

# Plain English for a reader who wasn't there

The reader has your text and the project's files, but not your session. Many readers read English as a second language, and some read it through machine translation. Write so that each sentence has only one reading.

This skill has two jobs. If you have a source text to rewrite, its claims are fixed, and only the shape and the sentences change. If you write your own text, you know how you know each claim, so you say it.

## Shape

Use these parts in this order. Leave out a part that has no content. The part names are structure, so add them to a rewrite that needs them.

1. **Status:** one sentence, only if the source or your work states one.
2. **What to do:** the steps. One action in each step, in the imperative. Number the steps only when the order matters.
3. **If <condition>:** one block for each branch, at the top level, with its own steps. Use **Otherwise:** for the other case.
4. **Done when:** each item has the form "[When <trigger>,] <named thing> <observable result>." Write one result in each item.
5. **Rules:** what must stay true for the whole task. In your own writing, use "must" or "must not".
6. **What is known:** one claim in each bullet, with its label (see Evidence).
7. **Links:** related work, what this depends on, and what must land first.

## Sentences

- A step, a Done when item or a rule has at most 20 words. Other sentences have at most 25.
- A paragraph has at most 4 sentences. Put three or more parallel items in a list.
- Use no semicolons. Write an arrow used as a verb as words: "Disk full → upload stopped" becomes "When the disk is full, the upload stops."
- Write whole sentences. Keep the articles and the word "that": "The log shows that the job failed." Write "is not", not "isn't".
- Put the condition first: "If the cache is cold, rebuild it."
- Name the actor: "The scheduler retries the job", not "The job is retried".
- Put at most three nouns in a row: "rules that give each run its own directory".
- Use one name for one thing. Qualify a word instead of changing it: "code review".
- When you split a sentence, keep its link word: "The disk filled. So the upload stopped."
- Start a sentence with its subject's name when "It" or "This" could point to two things.

## Words that a second-language reader can misread

- Replace idioms and slang: "footgun", "yak shave", "low-hanging fruit".
- Replace generic phrasal verbs: "look into" becomes "investigate", and "figure out" becomes "find". Keep a phrasal verb that names a command or an action, such as "roll back" or "check out". Use its noun form as a noun: "the rollback".
- Replace "since", "as", "while" and "once" with a word that has one meaning: "because", "after", "during", "although" or "when".
- Write "for example" and "that is". Name the items instead of "etc.".
- Write "about 200 ms", not "~200ms". Write dates as YYYY-MM-DD and times with a time zone.
- Ask a question in the positive: "Is the job running?", not "Isn't the job running?"

Some text stays exactly as written: code, commands, paths, flags, identifiers, error text and other quotations. Numbers and the terms of the project and the field (API, CI, PR) also stay. Put code in backticks.

## Evidence

In your own writing, each bullet in What is known starts with one label:

- **Verified:** you checked it. Name or link the check.
- **Observed:** you saw it happen, but did not check it.
- **Reported:** someone said so. Name who.
- **Inferred:** you reasoned it from evidence. Name the evidence.
- **Unknown:** an open question that matters for the work.

In a rewrite, a bullet gets a label only when the source says how the claim is known:

| The source says | Label |
|---|---|
| "confirmed by" a named check | Verified |
| "we measured", "the log shows" | Observed |
| "X says", "X reported" | Reported, and name X |
| "likely", "probably", "we think", "that's inference" | Inferred |
| "it is unknown whether", "unclear if" | Unknown |
| a marker such as [V] | the word that the marker stands for |

A claim that the source states with no word from the left column stays a plain bullet. If one source sentence holds two kinds of claim, make one bullet for each label.

## Rewriting

- Each claim keeps its hedge ("may", "likely", "only"), condition, scope, source, number and link, with the same force. Keep "only" next to the word that it limits.
- When you split a sentence, repeat its label, hedge, condition and source on each piece.
- If a word has two possible meanings and the source does not show which, keep the word.
- Every claim, step, status, label and actor comes from the source. Put what you could not resolve in your reply, not in the text.

## Check

1. Run `python3 <this skill's folder>/ste_lint.py --strict NEW.md`. Fix each long-sentence, long-paragraph, long-item, semicolon and label finding. A noun-cluster line is a hint. Leave a quotation as it is, even when the lint flags it.
2. For a rewrite, also run `python3 <this skill's folder>/ste_lint.py --strict --compare OLD.md NEW.md`. Put back each item in the "disappeared" list, attached to the same claim.
3. The lint counts 25 words for every sentence, and it does not check the word rules. Check the 20-word limit and the word rules yourself.
4. Read the result as someone who wasn't there. State the problem and the done condition in one sentence each. If you cannot, fix the shape.

## Example

Before:

> Verified: the backup job got slower after the storage migration, and the disk is 95% full; we think the migration's new compression setting is to blame but that's inference, and whether turning it off restores the old speed is unknown. Per the discussion above, try the flag first, then if that doesn't help roll back.

After:

> **What to do**
> 1. Turn off the new compression setting of the migration.
>
> **If turning the setting off does not help:** roll back the storage migration.
>
> **What is known**
> - Verified: the backup job got slower after the storage migration.
> - Verified: the disk is 95% full.
> - Inferred: the new compression setting of the migration causes the slowdown.
> - Unknown: whether turning the setting off restores the old speed.

## Common mistakes

| Mistake | Fix |
|---|---|
| If/else steps in one numbered list | One **If …:** block for each branch |
| Done when written as actions ("Record the result.") | A condition ("The result is recorded.") |
| A label dropped when a sentence is split | Repeat the label on each bullet |
| "may" changed to "can", or "might cause" to "causes" | Keep the source's hedge |
| A counter-clause dropped ("but the docs also say so") | Keep it in the bullet for the claim that it limits |
| A synonym swapped in for variety | Qualify the word |
| Telegraph style ("Disk full → upload stopped") | A whole sentence with a subject and a verb |
| A project term "simplified" ("roll back" became "undo") | Keep the term |
