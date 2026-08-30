# Historical identity validation protocol

How a real domain-expert sample must be built before any identity rule is
allowed near production. Nothing here has been executed: there is currently no
adjudicated historical-person label set, and this document exists so that the
first one is not built badly.

The protocol assumes the calibration result: **no identity-bearing evidence
exists in Itqan v1.20**. Every candidate rule therefore rests on supporting
evidence alone, and the only way to learn whether a rule is safe is to have a
rijal specialist adjudicate a sample of what it would merge.

---

## 1. The statistical goal, stated before the sample size

The question is not "how accurate is the rule". It is:

> If we let this rule merge profiles automatically, how often would it merge
> two different historical people?

That is a **false-merge rate**, and the decision is one-sided: a rule is
adopted only if its false-merge rate is credibly below a stated ceiling.

Sample size follows from the ceiling, using the rule of three. If a specialist
adjudicates `n` triggered pairs and finds **zero** false merges, the 95%
upper bound on the true false-merge rate is approximately `3/n`:

| adjudicated pairs, zero false merges | 95% upper bound on false-merge rate |
|---:|---|
| 60 | 5.0% |
| 100 | 3.0% |
| 150 | 2.0% |
| 300 | 1.0% |

A single observed false merge changes the picture sharply and is treated as a
stop condition, not as a rate to be averaged away.

**Adopted ceiling: 1%, therefore n = 300 per rule** for any rule that would
merge automatically. A rule that only raises a review flag — never merging on
its own — is validated at n = 60, because its failure costs reviewer time
rather than corrupting the identity layer.

This is why coverage is never the sizing input. R-07 triggers on 19,253 groups
and would need the same 300 adjudications as R-04's 9; the cost of validation
is set by the risk, not by the reach.

---

## 2. Strata

Sampling uniformly from triggered pairs would fill the sample with easy cases
and estimate nothing useful. The sample is stratified so that each stratum can
fail differently, with a minimum of 30 per stratum so a stratum-level rate is
interpretable on its own.

| stratum | source population | why it is separate |
|---|---|---|
| likely duplicate | `DUPLICATE_PROFILE_STRONGLY_SUPPORTED` (570 groups) | tests whether "strongly supported" survives expert scrutiny |
| likely distinct | `DISTINCT_PERSON_STRONGLY_SUPPORTED` (1,569 groups) | the false-merge trap; any rule triggering here is disqualified |
| ambiguous | `UNRESOLVED_PROFILE_MULTIPLICITY` (17,618 groups) | the population that actually decides coverage |
| exact-name collision | R-07 triggers | isolates the known collision driver |
| short-name candidate | the 890 exact-short-name targets | abbreviated forms are the hardest name question |
| source-attachment contradiction | the 17,333 multiprofile source keys | separates data corruption from identity |
| relationally compatible | R-06 triggers | tests whether shared teachers mean anything |

Allocation is proportional to stratum size **after** the 30-case floor is met,
so the rare-but-dangerous strata are never crowded out by the large ambiguous
one.

---

## 3. Blinding

The reviewer must not be able to infer the expected answer.

**Visible:** both profiles' full names, aliases and `namings`, kunya, nasab,
laqab, city, every reported death with its source, tabaqat and generation,
teacher and student lists, the classical sources and their source-specific
entries, explicit contradictions, and an explicit list of what is missing.

**Hidden:** the mechanical status, the rule that selected the row, any
triggered rule ID, the stratum, group IDs, the audit's conceptual class, any
score, rank, ordering or confidence, and whether other reviewers have seen the
row. Rows are shuffled under a recorded seed so position carries no signal.

The existing 40-row packet already meets this bar: reviewer columns are blank,
and no automatic label, score or expected answer is among its visible columns.
One gap must be closed before scaling — `source_review_id` is a join key back
to `itqan_profile_duplication_strict_mechanical_triage.csv`, which holds
`assistant_mechanical_triage`. The label is not visible in the packet, but it
is one join away. Future packets must carry an opaque row ID whose mapping is
held separately from the reviewer.

---

## 4. Verdicts

Exactly four, and no free-text substitute:

- `SAME_HISTORICAL_PERSON`
- `DIFFERENT_HISTORICAL_PERSON`
- `UNCERTAIN`
- `INSUFFICIENT_SOURCE_EVIDENCE`

`UNCERTAIN` means the specialist could decide with more sources.
`INSUFFICIENT_SOURCE_EVIDENCE` means the records as given cannot support any
verdict. Collapsing the two would hide whether the problem is our data or the
historical record, so they stay distinct.

**Minimum evidence to label.** A `SAME_HISTORICAL_PERSON` verdict requires the
reviewer to cite at least one specific source entry supporting it. A verdict
asserted without a citation is recorded as `UNCERTAIN`. This is the only
defence against a reviewer pattern-matching on name similarity, which is
exactly the failure mode the rules are being tested for.

---

## 5. Adjudication and disagreement

Every sampled pair goes to **two independent specialists** who cannot see each
other's verdicts. Agreement is measured before anything else is computed, and
reported as raw agreement plus Cohen's kappa with its confidence interval.

- Both agree → verdict stands.
- One `UNCERTAIN`, one decisive → recorded as `UNCERTAIN`; the decisive verdict
  is retained as a note, never promoted.
- Direct disagreement (`SAME` vs `DIFFERENT`) → a third specialist adjudicates
  blind to both. If the third does not break the tie, the pair is permanently
  `UNCERTAIN` and is excluded from the rate denominator, with the exclusion
  count reported.

If kappa is below 0.6 the sample is not used to validate any rule. Low
agreement means the question as posed is not answerable from the evidence
shown, and the packet — not the rule — is what needs fixing.

---

## 6. What the result licenses

A rule may move to `SAFE_FOR_FURTHER_VALIDATION` only with zero observed false
merges at its required `n`, kappa ≥ 0.6, and no trigger on any pair adjudicated
`DIFFERENT_HISTORICAL_PERSON`.

Even then the rule does not merge anything. It produces `PROVISIONAL` identity
assertions carrying their evidence, which remain reversible. The
entity-resolution gate opens on adjudicated identity evidence, never on rule
coverage.
