# Sanad graph readiness

> **STATUS: PROPOSED / NOT IMPLEMENTED.**
> No graph, node, edge, database or loader exists. Nothing in this document is
> built. It records what the data can support so the design can be reviewed
> before anything is constructed.

The question this answers is narrow: **can a truthful sanad graph be built on
MIS narrator identities while Itqan historical-person identity stays
unresolved?** The answer is derived from measurement, not from architectural
preference.

---

## 1. MIS narrator node semantics — measured

All figures below are read directly from the frozen MIS workbooks.

| property | measured |
|---|---|
| narrator nodes | **2,092** |
| populated `NarratorID_Mapped` | 2,092 |
| null / empty IDs | **0** |
| unique raw IDs | 2,092 |
| unique after normalisation | 2,092 (**0 collisions**) |
| nodes never referenced by an edge | **0** |
| distinct full names across IDs | 2,092 — **no full name is shared by two IDs** |
| short/mapped names shared by >1 ID | 14 |

Generation coverage: Follower (Tabiʿ) 1,013 · Successor (Tabaʿ Tabiʿ) 438 ·
Companion 290 · 3rd Century AH 271 · NotMapped 80.

**MIS narrator IDs are stable, complete and non-colliding inside the frozen MIS
snapshot.** That is the only claim being made. They are *MIS narrator
identities*, not canonical historical-person identities: MIS assigns them by its
own mapping, and whether one MIS ID corresponds to exactly one historical person
is outside what this dataset can establish. The 14 shared short/mapped names are
the visible edge of that limit.

## 2. Edge and order semantics — measured

| property | measured |
|---|---|
| edges | **63,642** |
| edges with an unknown source narrator | **0** |
| edges with an unknown target narrator | **0** |
| distinct chains `(BookNo, HadithNo, SanadNo)` | **14,155** |
| `intractionLabel` values parsed | 63,642 / 63,642 |
| label `S…` agreeing with the `SanadNo` column | 63,642 / 63,642 |
| chains whose order index is not contiguous `1..n` | **0** |
| chains with a duplicate order index | **0** |
| chain transitions where `target[i] == source[i+1]` | 49,487 |
| broken transitions | **0** |

`intractionLabel` (`B2-H0001-C01-U01-S01-i1`) encodes book, hadith, chapter,
unit, **sanad** and **position**, and it agrees with the columns in every row.
Order is therefore explicit in the source and needs no inference.

**Direction is `source → target` = earlier → later = teacher → student.**
Established from generation flow, not assumed:

| source generation | target generation | edges |
|---|---|---:|
| Companion | Follower | 13,898 |
| Follower | Successor | 14,059 |
| Successor | 3rd Century AH | 13,689 |

with same-generation edges also present (Follower→Follower 14,354,
Successor→Successor 5,543, Companion→Companion 1,357) and 75 `NotMapped→Follower`.
A worked chain confirms it end to end: `i1` starts at the Companion and `i5`
ends at the 3rd-century compiler's immediate teacher.

Chains are short and bounded: **1–8 edges (2–9 narrators), mean 4.50**.
Distribution: 4 edges 6,323 · 5 edges 5,091 · 6 edges 1,340 · 3 edges 1,161 ·
7 edges 162 · 8 edges 17 · 2 edges 41 · 1 edge 20.

## 3. Multi-isnad semantics — measured

7,748 MIS hadiths carry 14,155 chains. Chain counts per hadith run **1 to 24**
(1 chain 4,162 · 2 chains 2,132 · 3 chains 780 · 4 chains 406 · then a tail).

The declared `SanadCount` column was cross-checked against the reconstructed
chain count for all 7,748 hadiths: **0 mismatches.**

Each chain is independently addressable by `(BookNo, HadithNo, SanadNo)` and
must stay that way. Flattening two chains into one narrator set would destroy
exactly the information a sanad question asks about.

## 4. Can the graph proceed without HistoricalNarrator?

**Yes — measured, not asserted.**

Everything a sanad question needs is already closed inside MIS: every edge
resolves to an existing node, every chain reconstructs exactly, order is
explicit, direction is determined, and multiple chains stay separate. None of
that depends on knowing which Itqan profile — or which historical person — a MIS
narrator corresponds to.

The dependency runs the other way. Itqan identity is required only for questions
*about the narrator as a historical person*: their gradings, their biography,
their appearances outside Sahih Muslim. Those are precisely the questions the
closed entity-resolution gate blocks, and they are separable from chain
structure.

Local-corpus attachment is also solid: the frozen linkage carries **7,015
accepted Hadith ↔ MIS links, strictly 1:1** (7,015 distinct local ids, 7,015
distinct MIS ids). Hadiths outside that set simply have no MIS chain attached
and must be reported as such.

## 5. Capability matrix

### A — safe without any Itqan identity completion

| capability | why it is safe |
|---|---|
| ordered isnads of a hadith | order explicit, 0 broken transitions |
| MIS narrators in a given chain | 0 dangling references |
| hadiths containing MIS narrator Y | edges carry hadith provenance |
| predecessor / successor of Y in recorded chains | direction determined |
| hadiths sharing a MIS narrator | node identity stable within MIS |
| number of chain variants for a hadith | `SanadCount` cross-checked, 0 mismatches |
| narrator generation as recorded by MIS | node attribute, no inference |
| chain length and position of a narrator | contiguous `1..n`, no duplicates |

All of these are answerable as **"as recorded in MIS"** — the honest framing,
and the one the graph should use in its own output.

### B — requires identity qualification

| capability | blocked on |
|---|---|
| all classical gradings for a narrator | MIS → Itqan identity |
| biography of a chain narrator | MIS → Itqan identity |
| is MIS narrator X the same person as Itqan profile Y | adjudicated identity |
| are two differently-named profiles one person | adjudicated identity |
| narrator reliability across the whole chain | identity + grading provenance |

These may be answered **only** with an explicit status qualifier, never as a
bare fact. A provisional candidate link may be surfaced as a candidate; it may
not be presented as the narrator's biography.

### C — must abstain

- any grading question about a narrator whose Itqan link is `UNRESOLVED`,
  `AMBIGUOUS_CANDIDATE` or `SHORT_NAME_DIAGNOSTIC`;
- any "is this the same person" question, for all 2,092 MIS narrators, since
  none has an adjudicated identity;
- any question about a hadith with no accepted MIS link;
- any request for a single narrator grade, which does not exist as a fact.

Abstention must state *which* layer is missing — chain, link, or identity — so
the answer is diagnostic rather than a bare refusal.

## 6. Proposed schema

Names derived from what the data actually holds.

**Nodes**

| node | key | source |
|---|---|---|
| `Hadith` | local corpus id | `muslim.json` |
| `MisHadith` | `(BookNo, HadithNo)` | MIS content sheet |
| `Isnad` | `(BookNo, HadithNo, SanadNo)` | MIS edge sheet |
| `MisNarrator` | `NarratorID_Mapped` | MIS nodes sheet |
| `ItqanProfile` | `itqan_id` | Itqan shards |
| `SourceRecord` | `(source_namespace, source_record_id)` | Itqan classical sources |

**Edges**

| edge | from → to | carries |
|---|---|---|
| `LINKED_TO_MIS` | Hadith → MisHadith | similarity, candidate status, accepted flag |
| `HAS_ISNAD` | MisHadith → Isnad | sanad number |
| `HAS_NARRATOR` | Isnad → MisNarrator | **position** ordinal |
| `TRANSMITTED_TO` | MisNarrator → MisNarrator | `(book, hadith, sanad, i)`, direction teacher → student |
| `CANDIDATE_PROFILE` | MisNarrator → ItqanProfile | tier status, never confirmed identity |
| `ATTESTED_BY` | ItqanProfile → SourceRecord | namespaced key, field paths |
| `RECORDS_GRADE` | SourceRecord → grade value | critic/source, grade text, entry id |

`TRANSMITTED_TO` is the prompt's `NARRATED_TO` with its direction fixed by
measurement. It is **not** a global teacher/student assertion: it is scoped to
the chain it came from, which is why it carries `(book, hadith, sanad, i)`
rather than existing as a bare narrator-to-narrator relation.

No `HistoricalNarrator` node is proposed for construction.

**Candidate link status** — reusing the frozen tier vocabulary rather than
inventing stronger claims:

`EXACT_PROVISIONAL` (30) · `ALIAS_PROVISIONAL` (51) · `AMBIGUOUS_CANDIDATE` (10)
· `SHORT_NAME_DIAGNOSTIC` (the 890, unpromoted) · `UNRESOLVED` (the remainder of
the 2,092).

Every one of these is provisional. `CANDIDATE_PROFILE` never means "is".

## 7. Grading provenance model

A grade belongs to the record that issued it, and the chain from narrator to
grade must stay traversable in full:

```
MisNarrator --CANDIDATE_PROFILE[status]--> ItqanProfile
             --ATTESTED_BY--> SourceRecord(namespace, entry_id)
             --RECORDS_GRADE--> grade text + critic/source
```

A query must be able to return *"Taqrib entry 5024 records ثقة; Mizan entry 1173
records something else"* with both retained and attributed. Disagreement is the
output, not a problem to resolve.

Forbidden by construction: `MisNarrator.grade`, `ItqanProfile.grade`,
`HistoricalNarrator.grade`, or any single collapsed verdict.

## 8. Invariants to enforce at build time

Derived from the measurements above; each is already true of the source data,
so a build that breaks one has a bug.

1. Every edge endpoint resolves to an existing `MisNarrator` (currently 0 failures).
2. Narrator IDs stay unique with no nulls and no normalisation collisions (2,092).
3. Every chain's position index is contiguous `1..n` with no duplicates.
4. `target[i] == source[i+1]` within every chain (currently 0 broken).
5. Reconstructed chain count per hadith equals the declared `SanadCount` (0 mismatches).
6. Chains from one hadith are never merged; `(book, hadith, sanad)` stays the chain key.
7. Every edge retains its source hadith and chain provenance — no bare narrator-to-narrator edge.
8. `CANDIDATE_PROFILE` always carries a status; a link without one is rejected.
9. No provisional link is ever written as a confirmed identity.
10. No grade exists except on a `SourceRecord`.
11. No `HistoricalNarrator` node is created.
12. Source-attachment contradictions stay visible and are never silently resolved.
13. The build is deterministic from the frozen artifacts — same inputs, same graph hash.
14. Hadiths with no accepted MIS link are representable as unlinked, not dropped.

## 9. Technology comparison

Scale is small and fixed: 2,092 narrator nodes, 63,642 edges, 14,155 chains,
7,748 MIS hadiths, 7,015 links, plus 115,735 Itqan profiles and ~320k source
attachments. Chains are at most 8 edges deep. The busiest narrator has degree
3,992.

| | NetworkX | SQLite | Neo4j |
|---|---|---|---|
| fits the data size | yes | yes | yes, far over-provisioned |
| persistence | none — rebuilt per process | single file | server + store |
| ordered chains | edge attributes, order re-derived | `position` column, ordering native | ordered rel properties |
| provenance & status columns | ad-hoc dict attributes | first-class columns + constraints | properties, no constraints by default |
| enforcing the 14 invariants | manual assertions | `UNIQUE` / `FOREIGN KEY` / `CHECK` | mostly manual |
| deep traversal | good | needs recursive CTE | best |
| reproducibility | none — no artifact to hash | one file, hashable like every other artifact | hard to hash |
| deployment | none | none (stdlib) | service, ports, auth, version pinning |
| future tool access | in-process only | any language, any process | driver + running server |

The decisive point is that this workload is **not** traversal-heavy. Chains are
explicitly ordered and bounded at 8; there is no variable-length path search, no
shortest-path, no community detection. What the design actually demands is
integrity: unique keys, foreign keys, mandatory status on provisional links, and
grades that cannot exist detached from a source record. Those are relational
constraints, and they are exactly what Neo4j does not enforce for free.

## 10. Recommendation

**SQLite for the deterministic foundation.**

It enforces the invariants declaratively, adds no dependency and no service, and
produces a single file that can be hashed and pinned like every other artifact
in this project — which matters, because invariant 13 requires the graph to be
reproducible from frozen inputs. Deep traversal, the one thing a property graph
would do better, is not required at a maximum depth of 8.

If a later stage genuinely needs variable-length traversal across the narrator
network, the SQLite build remains the reproducible source of truth and a graph
store becomes a derived index — which is the safe direction for that dependency
to run.

## 11. What is still blocked

- Every capability in section 5B and 5C.
- Any grading answer for any of the 2,092 MIS narrators.
- Promotion of the 81 or the 890.
- Instantiation of `HistoricalNarrator`.

**ENTITY-RESOLUTION GATE: CLOSED.** Building the chain layer does not open it,
and is deliberately designed not to need it.
