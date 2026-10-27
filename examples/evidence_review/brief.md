# Should Corvane Systems adopt a four-day week?

Corvane Systems is a 600-person B2B software company. Leadership must choose one of three options:

- `adopt_company_wide`: move every department to a 32-hour, four-day week at the same pay
- `pilot_knowledge_teams`: run a pilot in some departments only and keep the others on five days
- `do_not_adopt`: keep the five-day week

## The research question

Produce a short research memo that answers:

1. What does the evidence really say about the effect of a four-day week on productivity, wellbeing and retention?
2. Which sources can be trusted, and which should be discounted?
3. What would it cost Corvane, and which departments would be affected most?
4. Which option should leadership choose?

## Evidence

All evidence is in a read-only evidence room mounted at `/data/`. Read its `README.md` first; it lists every file. Use only what is in the evidence room. Do not use outside knowledge for facts or figures.

## Citation rule

Every factual claim must cite its source file in square brackets, with the path relative to the evidence-room root. Examples: `[README.md]`, `[staff_survey.csv]`, `[staff_survey.csv:row 3]`, `[cost_model.csv]`. Do not write `/data/...` paths; they are rejected.

## How to work with the evidence

Work like a careful researcher:

- Judge each source before you rely on it: design, sample size, peer review, funding and conflicts of interest, and whether it is still valid.
- Check headline claims against the source's own tables.
- Look past overall averages: where a source breaks results down by group, report each group.
- Recompute totals from their line items.
- When you find something that changes another task's conclusion, post it as a FACT note on the board straight away, so the peer working on that task can use it.

## Final output format

Keep the final memo under 450 words (the RESEARCH_SUMMARY block does not count).

The final memo must end with the line `RESEARCH_SUMMARY` followed by a fenced json block with exactly these keys and no others:

RESEARCH_SUMMARY
```json
{
  "verdict": "<adopt_company_wide, pilot_knowledge_teams or do_not_adopt>",
  "retracted_source": "<file path>",
  "inflated_claim_source": "<file path>",
  "harmed_group": "<department>",
  "cost_mismatch_eur": <number>
}
```

Field rules: `verdict` is one of the three options; `retracted_source` and `inflated_claim_source` are file paths relative to the evidence-room root; `harmed_group` is a department name from the evidence room; `cost_mismatch_eur` is a number in EUR, written as a bare JSON number with no quotes (for example 12345). Replace every placeholder with your own finding.
