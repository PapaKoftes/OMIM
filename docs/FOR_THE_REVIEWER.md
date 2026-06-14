# Reviewing OMIM's labels — a guide for cabinet makers & carpenters

You don't need to know anything about code to do this. You're the expert; the
software made its best guesses about a bunch of CNC drawings, and it needs you to
say **"yes, that's right"** or **"no, it's actually X."** That's the whole job.

## What you'll get handed

Two files (open them in **Excel** or **Google Sheets** — they're spreadsheets):

1. **`review_sheet.csv`** — the things to check, one per row.
2. **`review_glossary.csv`** — a cheat-sheet explaining any term you don't
   recognise. Keep it open in another tab.

## What the review sheet looks like

| file | picture | what OMIM thinks this is | how sure (%) | other guesses | is it right? (yes/no) | if no, what is it? | notes |
|---|---|---|---|---|---|---|---|
| door_L.dxf | thumbnails/…svg | hinge cup (35mm bore...) | 90 | — | | | |
| side_R.dxf | thumbnails/…svg | cabinet side (whole panel) | 72 | shelf | | | |
| shelf_2.dxf | thumbnails/…svg | shelf-pin hole (5mm...) | 55 | dowel hole | | | |

The **picture** column is a path to a small drawing of the panel — open it
(double-click, or it previews in most file managers) to *see* the part you're
judging. Seeing the panel is far faster than guessing from the filename.

OMIM only put a row here when it **wasn't confident** — the easy, obvious ones it
already handled. So every row genuinely needs your eye.

## How to fill it in — only two columns

For each row, look at the **file** and **what OMIM thinks this is**, then:

1. **"is it right? (yes/no)"** — type **yes** or **no**.
2. Only if you said **no** → **"if no, what is it?"** — type the correct thing.
   You can use plain words ("shelf", "drawer front", "8mm dowel hole") or leave
   the glossary's term. If it's genuinely junk/not a real feature, write **no**
   and leave the answer blank — it'll be dropped.
3. **"notes"** — optional, anything you want to flag.

**Don't touch** the `row_id`, `file`, or the OMIM-guess columns — `row_id` is how
your answer gets matched back. Leaving a row blank is fine; it just means "I'll
look at that later."

Tips:
- "how sure (%)" is OMIM's own confidence. A low number (e.g. 55) means it's
  basically guessing — those are the most useful for you to correct.
- "other guesses" are its runner-up ideas — sometimes the right answer is sitting
  right there.

## When you're done

Save the file (keep it as **CSV**) and hand it back. One command folds your
answers in and turns them into trusted "gold" labels:

```
omim apply-review <dataset folder>
```

Your **yes** answers confirm OMIM was right; your **no + correction** answers
override it. Either way, your judgement becomes the ground truth the dataset is
built on. That's exactly the point — the software does the boring 90%, you fix the
uncertain 10%, and the result is a dataset grounded in a real maker's knowledge.

## A note on what you're NOT responsible for

You don't need to check the obvious stuff OMIM was sure about, you don't need to
draw anything, and you can't break anything — if you're unsure on a row, just
leave it blank. Your time is best spent on the low-confidence rows where your
experience beats a rule of thumb.
