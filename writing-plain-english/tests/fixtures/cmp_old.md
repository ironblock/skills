The import took 12 minutes on version v0.9.0 and used 1.5 GB, but only on the slow runner.

Run `make check` and then `--fast` before you push. Read src/import/reader.py and docs/import.md first.

The log said "retry later" and the operator replied “hold on”.

See [the runbook](https://example.com/runbook) and [the board|https://example.com/board]. The raw feed is at https://example.com/feed.

The bad build was 3fa94c2 and the good one was 9e81b07. Tag each claim [V] or [R].

Do not restart the job unless the queue is empty, because a restart drops queued work.

```
reset --soft
```

```
echo done
```
