# MUSNAD — G1 Product + Research Contract

| | |
|---|---|
| **Project** | MUSNAD |
| **Phase** | G1 — Product + Research Contract |
| **Version** | 1.1 |
| **Status** | **FROZEN** |
| **Gate** | **PASS** |
| **Frozen** | 2026-08-31 |
| **Verified against** | commit `63b78d7aeb1e8c6c1c3b8576e3bfadb1d5dbea88` — *Repair pre-agentic measurement and documentation integrity* |
| **Sources of truth** | `README.md` · `EXPERIMENTS.md` §1–20 · `SANAD_GRAPH_READINESS.md` · `DATA_SOURCES.md` · `historical_identity_validation_protocol.md` · `src/sanad_graph.py` · `src/sanad_context.py` |

**This phase is design-only.** Producing this contract changed no code, no dataset, no
schema, no evaluation label, no prompt and no runtime behaviour. Every repository figure
below was read from the repository at the commit named above; where this document once
disagreed with the repository, the repository won and the disagreement is recorded.

This document is the authoritative input to G2. It does not authorise implementation.

---

## 1. Executive decision

| | |
|---|---|
| **G1 gate** | PASS — with four carry-forward conditions |
| **Agent question** | Justified for specific tasks only |
| **V1 capabilities** | 15 supported — **14 workflow, 1 agent** |
| **Entity-resolution gate** | Stays closed — V1 is designed not to need it |

Musnad has a deterministic foundation that is unusually well measured for its stage, and a
product hypothesis broader than that foundation can honestly support. This contract narrows
it.

Six decisions carry the phase:

1. **The product is a structural evidence instrument, not a hadith answering service.** Text
   answering is a commodity elsewhere and Musnad's version is capped at one book. What Musnad
   has that the market does not is 14,155 separately-addressable chains joined to a
   retrievable matn corpus by a hashed linkage artifact.
2. **One primary user: the researcher working on transmission structure inside Sahih
   Muslim.** Not the general reader, whose main questions — is this authentic, is this
   narrator reliable, what is the ruling — are precisely the ones Musnad must refuse.
3. **Ask / Explore / Investigate survives, redefined by evidence contract rather than by
   interface.** Explore earns separation because it has no generative model in its answer
   path at all.
4. **Fourteen of fifteen capabilities are workflows.** Most of the "investigation" examples
   in the phase brief are fixed pipelines with fan-out over an unknown-size result set.
   Fan-out is a loop, and so is a predetermined retry branch.
5. **Exactly one capability justifies an agent**, and it must beat a workflow baseline or be
   deleted. The repository already contains a measured negative result for the nearest
   agentic pattern it tried.
6. **A structural finding is a finding about MIS, not about history.** This is stronger than
   the brief stated and it constrains the wording of every comparison capability.

### 1.1 Revision log — version 1.1

Version 1.0 passed substantive architecture review. Version 1.1 applies eleven corrections
and records three contradictions found while applying them.

| # | Issue | Repair applied | Sections |
|---|---|---|---|
| 1 | Execution-class taxonomy used `HYBRID` as a third orchestration class | `HYBRID` removed. C12 and C13 reclassified to **WORKFLOW** — a bounded fan-out and a predetermined rewrite branch are both predefined code paths. Evidence pipeline separated into its own axis: `MATN` / `SANAD` / `CROSS_LAYER`. Split is now **14 workflow, 1 agent** | 8, 13, 17, 24, 25, 27 |
| 2 | "2,001 narrators have no candidate profile at all" — too strong, and contradicted the unmatched diagnostic | Corrected everywhere to **no accepted frozen canonical/alias resolution**, with the diagnostic strata preserved | 2, 4, 9, 24 |
| 3 | Final holdout was to be run at G4 *and* G5 | Replaced with a single-run freeze protocol | 20, 23, 27 |
| 4 | C14 scored against a single gold operation sequence | Replaced with a **trajectory contract** admitting multiple valid trajectories | 19, 20 |
| 5 | "Retrieval ceiling: hit@5 81%" conflated production output with candidate recall | Now **production reranked hit@5 = 22/27**, with candidate-depth recall reported separately. No number changed | 2, 4, 22 |
| 6 | The 27-question set treated as extendable into the new holdout | Reclassified as a **historical diagnostic and reporting instrument** | 4, 19, 20 |
| 7 | Wedge validation left as an open question | G2 split into **G2A elicitation** and **G2B benchmark** | 20, 25, 26, 29 |
| 8 | "Explore cannot hallucinate" — absolute | Replaced with the precise boundary | 7, 8, 26 |
| 9 | Deployment wording implied production was permanently out of scope | **V1 functional scope** separated from the **project production engineering roadmap** | 17, 25 |
| 10 | A single named statistical test was implied to cover the whole comparison | Replaced with a **metric-specific statistical analysis contract**, a pre-registered decision hierarchy, and a degrees-of-freedom rule | 19, 20, 23, 27 |
| 11 | `PRODUCT_WEDGE_VALIDATION` overstated what a small elicitation study can establish | Renamed `PRODUCT_WEDGE_EVIDENCE` with `SUPPORTED` / `LIMITED` / `NOT_SUPPORTED`, and an explicit statement that this is not market validation | 20, 25, 26, 29 |

**Three contradictions found and corrected:**

- **In the phase brief.** "7,570 retrieval chunks" is the chunk store; the FAISS index holds
  **7,110** documents — 460 chunks are cross-reference entries with no matn of their own.
  Both are correct for different things.
- **In version 1.0 of this document.** The identity gap was overstated: "no candidate profile
  at all" is wrong for 1,995 of the 2,001, which do carry diagnostic candidates. The shortage
  is adjudication, not candidates.
- **In version 1.0's benchmark plan.** It proposed reusing the 3 known-unretrievable
  questions as a negative control without noticing that **2 of them are among the 6 whose
  ground truth was edited after model output was seen**. They cannot serve as a clean control.

### 1.2 The four carry-forward conditions

| # | Condition | Why it blocks progress | Owner phase |
|---|---|---|---|
| 1 | Narrator name → MIS ID resolution must be specified as a first-class capability with ambiguity as an *output*, not an error | No such operation exists in `sanad_graph.py`; every narrator function takes an ID. Users type names. Without it, seven capabilities have no entry point | G2 spec, G3 build |
| 2 | Every cross-chain "shared narrator" claim must be worded as shared *MIS narrator identity* | MIS's own narrator mapping was built with fuzzy matching and manual mapping; 14 mapped short names are shared by more than one ID | G2 wording, G3 output |
| 3 | The 7,015-link acceptance must be described as deterministic textual matching with *unknown* human precision | `EXPERIMENTS` §10 records 0/361 manual labels; the gate opened on full-population deterministic evidence, not a reviewed sample | G2 evidence contract |
| 4 | The agent claim must be falsifiable before it is built | G4 must be able to delete the agent. That requires the workflow baseline to exist first and to be measured on the same benchmark | G2 design, G4 test |

---

## 2. Product definition

### Positioning

> **Musnad turns a question about Sahih Muslim into the specific matn and isnad records that
> bear on it, computes the structural relationships between those records deterministically,
> and names the exact evidence layer that is missing whenever it cannot answer.**

### What that commits to

- **Records first, prose second.** The primary output is a set of identified records and
  derived structure. Prose renders that set; it never sources it.
- **Structure is computed, not narrated.** Shared narrators, chain divergence points and
  adjacency counts are set and sequence operations over a SQLite graph with enforced
  invariants. A language model never derives them.
- **Absence is an answer with a name.** Four abstention states already exist in code and are
  distinguishable rather than collapsed into an empty list. That behaviour is the product's
  defining feature, not an error path.
- **Provenance travels with the claim.** Every traversal result already carries
  `link_status`, `linkage_version`, the linkage artifact SHA-256 and a verbatim `basis`
  string. The product surface must not strip them.

### What it is not

| Not this | Because |
|---|---|
| A hadith chatbot | Production reranked hit@5 is 22/27 on a hand-written set documented as not blind, and 3 of 30 answers cite the wrong hadith from inside a correct context |
| A takhrij platform | Takhrij is inherently cross-collection. The corpus is one book |
| A rijal / grading service | No adjudicated narrator identity exists. 2,001 of 2,092 MIS narrators have no accepted frozen canonical or alias resolution, and every diagnostic candidate beyond that is labelled `DIAGNOSTIC_CANDIDATE`, never a match |
| An authentication authority | A verdict on a chain requires narrator reliability, which requires identity. The gate is closed and this contract keeps it closed |
| A GraphRAG demo | The graph is queried by key, not traversed by a model. Maximum chain depth is 8; there is no variable-length path search anywhere in V1 |

### Standing disclosure

Musnad is research assistance. It does not issue rulings, does not grade narrators, does not
adjudicate authenticity, and does not replace a qualified scholar. This is not a footer
disclaimer — it is a capability boundary enforced by the negative matrix in §9 and by the
abstention taxonomy in §12.

---

## 3. Primary and secondary users

### Primary — the transmission-structure researcher

A graduate-level or professional researcher in hadith studies, Islamic history or Arabic
digital humanities, working on how a report is transmitted rather than on what it rules.

| | |
|---|---|
| **Job to be done** | Assemble, for a defined set of hadiths, the recorded chains and the structural relations between them — who recurs, where chains diverge, which transmissions repeat — with enough provenance to cite the result |
| **Current pain** | The structure exists as a research dataset (three Excel workbooks) or inside a graph database they must stand up themselves. Getting from "a question about honesty" to "the chains of the hadiths that answer it" is manual, and the join between text and structure must be rebuilt by every researcher |
| **What existing search does well** | Finding the hadith. Showing its text, collection and chapter, and on the major Arabic platforms a grading verdict and narrator biography |
| **What stays hard** | Comparing several chains as objects rather than reading them as strings; aggregating one narrator's positions across chains; getting a stable, hashable, citable answer a reviewer can reproduce |
| **Why Musnad helps** | Chains are preserved separately and addressably (1–24 per hadith, 3,586 hadiths with more than one), the corpus join is a frozen artifact with a published SHA-256, and the graph rebuild is deterministic to an identical hash |
| **Must not pretend to replace** | Rijal criticism, source-critical judgement, or the classical literature the MIS chains were extracted from. Musnad reports MIS; it does not verify MIS against the manuscripts |

### Secondary A — the advanced student doing structural orientation

طالب علم working within Sahih Muslim who wants to see a hadith's recorded chains, find where
a narrator appears, and understand how several reports relate structurally.

Served by the same capabilities with one added obligation: this group is the most likely to
read a structural output as an authenticity signal. Every comparison output must carry the
"recorded in MIS · not a reliability judgement" qualifier at the point of display, not in a
help page. If that qualifier cannot be enforced in the interface, this user group is dropped
rather than the qualifier.

### Secondary B — the Arabic NLP / DH engineer

Someone building on the corpus who needs a reproducible, provenance-carrying surface rather
than prose: identifiers that join, statuses that distinguish missing layers, artifacts that
hash the same twice. Served almost entirely by Explore and by exports; needs no agent and no
generation.

### Explicitly not a target for V1

The general reader asking whether something is permitted, authentic, or reliable. Every one
of those questions terminates in the negative matrix. Building for that user would mean
either refusing constantly or breaking the evidence contract.

### Research assistance versus authority — the line

| Musnad does | Musnad never does |
|---|---|
| Surface a recorded matn with its hadith number | Rule on what the matn obliges |
| Report the chains MIS records for a hadith | Judge whether those chains are sound |
| State that MIS assigns the same narrator ID to positions in two chains | State that the same historical person narrated both |
| Report that no grading layer exists in the system | Report a grading, or infer one from generation or position |
| Show where evidence stops | Fill the gap from model knowledge |
---

## 4. Current foundation and hard constraints

All figures read from the repository at the frozen commit.

### Corpus and retrieval

| Quantity | Value | Note |
|---|---:|---|
| Local hadith records (Sahih Muslim) | 7,459 | 57 books |
| Chunks in the chunk store | 7,570 | |
| Documents in the FAISS index | 7,110 | 7,570 minus 460 cross-reference entries with no matn |
| Production configuration — hybrid + reranking, candidate depth 10 | hit@1 15/27 · hit@5 22/27 · MRR 0.665 | hand-written set, n=27, **not blind** |
| Candidate recall at deeper pools (hybrid, before reranking) | hit@10 23/27 · hit@20 = hit@50 24/27 | a separate measurement from production hit@5; deeper pools left hit@1 at 15/27 and *lowered* hit@5 to 21/27 then 20/27 |
| Correct citation | 22/27 (81%) | answerable questions only; hand-written set, not blind |
| Invalid citation attempts | 0% | measured on raw output before filtering, over all 30 |
| Cited the wrong hadith from context | 3/30 (10%) | enforcement does not prevent this; 4/30 without reranking |
| Correct refusal | 3/3 | false refusal 0 over the 22 questions whose gold hadith reached the context |
| Narrator questions in the hand-written set | 0% (3 questions) | structurally unanswerable from text alone |
| Questions missed by every retriever at depth ≤50 | 3 | verified ground truth; a vocabulary gap |

> **The hand-written set is not blind — and this governs every number above.**
> `EXPERIMENTS` discloses that the 33-question hand-written set was **not blind**: inspecting
> bad results during development revealed genuine reference errors, and 6 questions had their
> ground truth edited *after* system output was seen — one reference removed as a false
> textual match, one question converted into a refusal test, several expected-id lists
> widened. The remaining 21 were untouched after writing. The 224-question generated set was
> never edited after generation and is recorded as the only blind set, used for all
> configuration choices.
>
> **Consequence for this contract:** these figures are valid for **regression against the
> same frozen fingerprint**, which is how the repository uses them. They are not an unbiased
> performance estimate, and the set is a **historical diagnostic and reporting instrument** —
> never the new holdout. `EXPERIMENTS` also records it as systematically easier than a random
> sample: hit@5 74% on it against 37% on the generated set for the same system, with absolute
> levels declared non-comparable between the two.

### Graph and linkage

| Quantity | Value | Note |
|---|---:|---|
| MIS narrators | 2,092 | 0 nulls, 0 normalisation collisions, 0 unreferenced |
| MIS hadiths | 7,748 | declared sanad count matches reconstruction, 0 mismatches |
| Isnads | 14,155 | all reconstruct exactly; 3,586 hadiths carry more than one; max 24 |
| Transmission steps | 63,642 | 0 dangling endpoints; order contiguous 1..n |
| Chain depth | 1–8 edges (mean 4.50) | no variable-length search is needed anywhere |
| Accepted local ↔ MIS links | 7,015 | strictly 1:1 |
| Local hadiths with no accepted link | 444 (5.95%) | first-class records, reported as such |
| MIS hadiths with no accepted local link | 733 (9.46%) | reverse-direction status exists |
| Graph rebuild | 9.0 s → 13.8 MB | identical hash across builds; chain hash isolated per layer |
| Query latency | sub-millisecond | context surface adapter 0.816 ms median |

### Six hard constraints that shape every capability

| Constraint | Product consequence |
|---|---|
| **Identity gate closed.** 81/2,092 provisional candidates, 10 ambiguous, and 2,001 with no accepted frozen canonical/alias resolution; the 40-case calibration found no identity-bearing evidence in Itqan v1.20 | No grading, biography, same-person or reliability capability may exist in V1 in any form, including "candidate" form in user-facing prose |
| **MIS narrator identity is operational, not historical** — and MIS built it with fuzzy matching and manual mapping; 14 mapped short names are shared by more than one ID | Every cross-chain identity claim is worded as a MIS assignment. The 14 shared names become a named benchmark stratum |
| **The linkage is a narrow-normalised textual match** named `LINKS_TO_MIS_RECORD`, deliberately not `SAME_HISTORICAL_HADITH`. Human precision is *unknown* — 0 of 361 sampled rows labelled | Any answer crossing the linkage carries the link status and version. "Musnad's linkage joins this to MIS record X" — never "this is MIS record X" |
| **Coverage is partial by construction** (444 / 733) | `PARTIAL` is a first-class outcome with the excluded identifiers enumerated. Silent exclusion is a defect |
| **One collection only** | No cross-book claim of any kind, including "this appears only in Muslim" |
| **No narrator name lookup exists in code** | The single largest build gap. Seven capabilities have no entry point until it exists |

> **Source-level discrepancy, already documented.** The MIS publication describes 77,797
> edges; the downloaded workbook contains **63,642**. `DATA_SOURCES.md` records this and every
> measurement uses the actual workbook. Any external comparison against the published figures
> must quote both.

---

## 5. Market and research landscape

The question is not who competes. It is which user value is already commoditised.

### Already commoditised — do not build

| Value | Where it already exists | Implication |
|---|---|---|
| Full-text hadith search across many collections | Major Arabic platforms — al-Durar al-Saniyyah, Islamweb, Mawqi' al-Islam — plus sunnah.com; studies describe these as the established route for takhrij | Musnad cannot win on coverage. One book against nine-plus collections |
| Grading verdict per hadith (*ḥukm*) and per narrator (*al-jarḥ wa-l-taʿdīl*) | The same platforms; described in the literature as core features alongside sanad, matn and narrator biography | Exactly what Musnad's closed gate forbids. Competing here is impossible, and attempting it would be dishonest |
| Sanad display, including visual isnad trees with narrator grades | Search engines built for visual isnad-tree analysis | Drawing a tree is not the differentiator. Computing over many trees might be |
| Locating a hadith across sources, *shawāhid* and *mutābaʿāt* | Established takhrij apps and encyclopedias | Structurally out of reach on a single-collection corpus |

### Research landscape — narrator networks

- **The dataset Musnad uses is itself published research.** Multi-IsnadSet for Sahih Muslim —
  7,748 hadiths, 2,092 narrators — was released with NetworkX, Neo4j, Gephi and CytoScape
  tooling. Musnad's contribution is not the graph; it is the integrity layer, the corpus
  join, and the abstention discipline around it.
- **Far larger graphs exist.** Sanadset 650K spans 650,986 records from 926 books with
  185,216 unique narrator name variants. A 2026 multi-signal entity-resolution pipeline built
  a 185,216-node / 814,093-edge transmission graph from it.
- **That pipeline is the strongest external evidence for Musnad's closed gate.** Its first
  phase linked 51.1% of names, with 54,690 of 94,628 links only medium-confidence; the second
  reached 94.7% coverage with medium confidence again dominating. Published narrator-identity
  graphs therefore ship at exactly the provisional quality Musnad's protocol refuses to
  promote. Musnad's differentiation here is not a better matcher — it is declining to assert.
- **Structural comparison across chains is a recognised scholarly method**, from the
  common-link approach of Schacht and Juynboll to Motzki's *isnād-cum-matn* analysis. It is
  also contested: the same structural observation supports opposite historical conclusions
  depending on the school. Musnad may compute the structure. It must not adopt the
  interpretation. See U8.
- **Agent evaluation has moved to trajectories.** TRACE (WWW 2026) evaluates the whole
  problem-solving path of deep research agents rather than final-answer accuracy. A 2026
  survey of evidence tracing notes that attribution benchmarks link answers to sources but
  rarely evaluate how tool calls and intermediate decisions shaped those claims — an
  incomplete execution provenance. That gap is what Musnad's evidence board and G2 trajectory
  contracts address.
- **Anthropic's guidance on agents** — find the simplest thing that works, and that may mean
  not building an agentic system — is the operating rule for §13.

### Domain risk, externally corroborated

Assessments of AI systems in Islamic guidance report misattribution of Qur'anic verses and
hadith, oversimplification and inconsistency; institutional positions from Dar al-Iftā and
Nahdlatul Ulama hold that rulings must remain with qualified human scholars, with AI confined
to research assistance. This is why §11 is a specification rather than a tone guide.

**External sources.** Anthropic, *Building Effective AI Agents* ·
Multi-IsnadSet (MIS) for Sahih Muslim, *Data in Brief* / Mendeley Data
`10.17632/gzprcr93zn.2` · *Sanadset 650K* ·
*Linking Hadith Narrator Identities Across Heterogeneous Arabic Biographical Databases*
(arXiv 2607.05424) · *TRACE: Trajectory-Aware Comprehensive Evaluation for Deep Research
Agents* (WWW 2026) · *From Agent Traces to Trust* (arXiv 2606.04990) ·
*Social network analysis of Hadith narrators* · *Isnad-cum-matn analysis* ·
*Takhrij al-Hadith via Websites* · *AI in Islamic guidance: chatbot performance* ·
*IslamicLegalBench* (arXiv 2602.21226).

---

## 6. The product wedge

Why should Musnad exist when strong hadith search already exists? Not because it uses AI,
RAG, GraphRAG or agents. Every one of those is an implementation detail, and two of them
measured no gain in this repository.

### The wedge, in three parts

| Claim | Evidence it rests on |
|---|---|
| **1. Chains are objects, not pictures.** Search products render a chain. Musnad computes over sets of chains | 14,155 chains addressable by `(book, hadith, sanad)`, never merged; 3,586 hadiths carry 2–24 of them; every step retains its chain provenance rather than existing as a bare narrator edge |
| **2. Text and structure are joined by an auditable artifact.** A retrieved hadith resolves to its recorded chains through one hashed linkage, with all three layers visible in the result | 7,570 chunks carry 7,459 identifiers, 0 of which fail to resolve; the join runs `hadith_id → id_in_book → link`; the linkage SHA travels with every answer |
| **3. Absence is diagnostic.** The system says which layer is missing — corpus, linkage, chain, or identity — instead of returning nothing | Four distinguishable statuses in the context surface, plus a reverse-direction status for the 733; a test asserts all four are distinct |

### What Musnad deliberately does not compete on

- Collection coverage. One book, permanently, for V1.
- Grading verdicts and narrator biography — the busiest feature of every incumbent.
- Takhrij across sources, *shawāhid* and *mutābaʿāt*.
- Conversational breadth. The generation path exists to render evidence, not to converse.

### What would make Musnad redundant

Stated in advance so it can be checked rather than argued:

1. The MIS authors — or anyone — ship a public queryable interface over the same chains with
   comparison operations. Then part 1 of the wedge is gone and only the corpus join and the
   abstention discipline remain.
2. An incumbent platform adds multi-chain structural comparison over a broader corpus. Then
   Musnad is a strictly smaller version of it.
3. Narrator entity resolution is solved and published at adjudicated quality. Then the
   interesting product is the one that uses gradings, and Musnad's abstention is a limitation
   rather than a feature.
4. Elicitation in G2A shows researchers do not want computed structural comparison — that
   reading the chains is enough at this corpus size.

Conditions 1 and 4 are live risks today. Both are on the risk register.

---

## 7. Ask / Explore / Investigate — assessed

**Verdict: keep all three, defined by evidence contract rather than by interface.** A single
input box with a router is a later convenience; the three contracts are what tools, statuses
and benchmark strata attach to.

| | ASK | EXPLORE | INVESTIGATE |
|---|---|---|---|
| **User goal** | Answer a question about what the corpus says | Navigate recorded structure from a known entity | Establish a structural relationship across several records |
| **Input** | Arabic natural language | An identifier — hadith id, narrator id, or a name that resolves to one | Arabic natural language naming entities, topics or constraints |
| **Evidence source** | Retrieved matn | Graph records only | Retrieved matn *and* derived structure |
| **Generative model in the answer path** | Yes — generation with enforced citations | **None.** Deterministic reads | Yes, for planning and rendering; never for deriving structure |
| **Output** | Grounded answer + hadith cards + chain availability per citation | Records, ordered chains, occurrence tables | Evidence board — claims, evidence items, gaps, limitations |
| **Execution** | Fixed path | Single deterministic call | Fixed pipeline, or a bounded agent loop for C14 |
| **Dominant failure** | Wrong in-context citation (3/30) | Wrong entity resolved from an ambiguous name | Unnoticed partial coverage; unnecessary tool calls |

### Why Explore stays separate

Not because it looks different. Because it has no generative model anywhere in the answer
path, so it has **no generative-model hallucination path**. Its correctness is instead
bounded by MIS source-data quality, linkage quality, implementation correctness and the
identity limitations in §4 — all of which are auditable in ways a model's output is not.
Determinism makes the computation checkable; it does not make an upstream MIS claim
historically true. Explore is the audit surface: every Ask citation and every Investigate
evidence item must be openable as an Explore view. Merging it into Ask would delete that
guarantee.

### Why Ask and Investigate stay separate

Different evidence contracts and different costs. Ask is grounded in retrieved text and is
cheap. Investigate is grounded in derived structure over many records, can call many tools,
and produces a different output object. Collapsing them behind a router would silently
escalate a cheap question into an expensive run, and would make cost and abstention
unattributable in evaluation.

### Challenges considered and rejected

- *"Merge Explore into Investigate."* Rejected — Explore is the deterministic floor the other
  modes are audited against.
- *"Two modes: answer and investigate."* Rejected for the same reason, and because Secondary B
  uses Explore alone.
- *"One box with a router."* Deferred, not rejected. The router is a V1.5 convenience over
  three contracts that must exist first. When it arrives, classification must be visible and
  user-overridable.

> **The naming risk.** "Investigate" will be read as *deeper truth*. It is only *more
> operations over the same evidence*. An investigation over the 444 unlinked hadiths returns
> exactly as little as a single lookup does. Interface wording must not imply that more steps
> mean more certainty.
---

## 8. V1 supported capability matrix

Fifteen capabilities. Seeds from the phase brief were merged where they were the same
operation under two names: *chain variant count* folded into **C04** (it is a field of that
result), *hadith + sanad* folded into **C03**, and *answer with chains attached* folded into
**C01** as a required output composition rather than a separate capability.

**Two axes, deliberately separate.** *Evidence pipeline* — `MATN`, `SANAD`, `CROSS_LAYER` —
describes what evidence a capability spans. *Execution class* — `WORKFLOW`, `AGENT` —
describes how it is orchestrated. `CROSS_LAYER` carries no orchestration meaning; `HYBRID` is
not an execution class.

| ID | Capability | Mode | Evidence pipeline | Execution class | Built? |
|---|---|---|---|---|---|
| C01 | Grounded matn answer | Ask | `MATN` | WORKFLOW | Yes — measured |
| C02 | Known-item hadith lookup | Ask | `MATN` | WORKFLOW | Yes — measured |
| C03 | Hadith record card | Explore | `CROSS_LAYER` | WORKFLOW | Yes |
| C04 | Recorded chains of a hadith | Explore | `SANAD` | WORKFLOW | Yes |
| C05 | Narrator record card | Explore | `SANAD` | WORKFLOW | Yes |
| C06 | Narrator name resolution | Explore | `SANAD` | WORKFLOW | **No — keystone gap** |
| C07 | Narrator occurrences | Explore | `SANAD` | WORKFLOW | Yes |
| C08 | Chain neighbours of a narrator | Explore | `SANAD` | WORKFLOW | Yes |
| C09 | Isnad comparison within one hadith | Investigate | `SANAD` | WORKFLOW | No — derived |
| C10 | Narrator pair relation | Investigate | `SANAD` | WORKFLOW | No — derived |
| C11 | Narrator co-occurrence | Investigate | `SANAD` | WORKFLOW | No — derived |
| C12 | Cross-hadith chain comparison | Investigate | `CROSS_LAYER` | WORKFLOW | No |
| C13 | Topic + narrator constrained retrieval | Investigate | `CROSS_LAYER` | WORKFLOW | No |
| C14 | Open structural investigation | Investigate | `CROSS_LAYER` | **AGENT** | No |
| C15 | Evidence-gap diagnostic | All | `CROSS_LAYER` | WORKFLOW | Partly |

**Total: 14 workflow, 1 agent.**

### C01 · Grounded matn answer — `MATN` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Get an answer to a topical question, stated only from what Sahih Muslim records, with the hadith numbers that support it |
| **Example questions** | إلامَ يهدي الصدق وإلامَ يهدي الكذب؟ · ما تعريف الغيبة عند النبي ﷺ؟ · ما جزاء الظلم يوم القيامة؟ |
| **User inputs** | One Arabic question. Optional: attach recorded chains for each cited hadith |
| **Data layer** | Chunk store → FAISS + BM25 → RRF → cross-encoder → generation. Optionally the context surface per citation |
| **Minimum evidence** | At least one retrieved chunk whose hadith number appears in the generated answer and in the supplied context |
| **Allowed claims** | `RECORDED` the quoted matn is recorded at hadith N · `MODEL_ASSERTED` the prose summary, bounded by citation enforcement |
| **Forbidden claims** | Any ruling or obligation · authenticity or grading · that the cited set is exhaustive · any statement about a hadith not in the supplied context |
| **Output** | Answer text · hadith cards (number, book, chapter, vocalised matn) · per-citation chain-availability status · limitations block |
| **Why this class** | The path is fixed and measured end to end. CRAG self-grading with one rewrite was built on top of it and measured **no gain** — a repository-local negative result against adding agency here |
| **Failure modes** | Wrong hadith cited from within a correct context (3/30) · retrieval miss with no relevant chunk (3 questions at depth ≤50) · a topically right answer drawn from an incomplete context |
| **Degradation** | No citable chunk → refuse with `ABSTAINED`. Citation enforcement fails twice → refuse. Chains unavailable for a cited hadith → answer stands, chain slot shows its named status |
| **Benchmark** | S1 direct matn · S10 adversarial |
| **Differentiation** | Low on its own — this is the commoditised layer. Its V1 value is as the entry point that hands identifiers to the structural layer |

### C02 · Known-item hadith lookup — `MATN` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Find the record for a hadith the user already partly knows — a remembered phrase, or a number |
| **Example questions** | أين حديث «إنما الأعمال بالنيات» في صحيح مسلم؟ · هاتِ الحديث رقم ٧٣٥٤ |
| **User inputs** | A phrase, or a corpus id / `idInBook` |
| **Data layer** | Retrieval stack, or direct id read. No generation |
| **Minimum evidence** | One ranked retrieval result, or one existing identifier |
| **Allowed claims** | `RECORDED` these records rank highest for the phrase; the text is as recorded |
| **Forbidden claims** | That the top result is *the* hadith the user meant · that a phrase absent from results is absent from the corpus |
| **Output** | Ranked hadith cards with score and rank, each openable in Explore |
| **Why this class** | One call. Separate from C01 because no model writes a claim: there is no generative hallucination path, only retrieval-ranking error, so the evidence contract differs |
| **Failure modes** | Vocabulary gap (measured: 3 questions missed by every retriever at depth 50) · near-duplicate matns ranking above the intended one |
| **Degradation** | No result above threshold → `NOT_FOUND` worded as "not retrieved", never "not in the corpus" |
| **Benchmark** | S2 known-item |
| **Differentiation** | None. Parity feature, kept because everything downstream needs an identifier |

### C03 · Hadith record card — `CROSS_LAYER` · WORKFLOW

| Field | |
|---|---|
| **User goal** | See everything the system holds for one hadith in one place, including whether it reaches MIS at all |
| **Example questions** | أرِني الحديث ٧٣٥٤ بكامل بياناته وسنده |
| **User inputs** | Local corpus id |
| **Data layer** | `local_hadith` + `hadith_mis_link` + `mis_hadith` + `isnad`; matn from the retrieval layer, the only place local text lives |
| **Minimum evidence** | The local record exists. Everything beyond it is optional and named when absent |
| **Allowed claims** | `RECORDED` corpus fields · `LINKED` the accepted linkage joins it to MIS record (book, hadith), with version and artifact SHA |
| **Forbidden claims** | That the local hadith and the MIS record are the same historical hadith · that an unlinked hadith has no sanad |
| **Output** | Three visibly separate layers — local record, linkage with provenance, MIS record — plus chain count and status |
| **Why this class** | Deterministic composition that already exists in `sanad_context.py` |
| **Failure modes** | Interface collapsing the linkage layer into the hadith, making a textual match look like an identity |
| **Degradation** | Four named statuses, never an empty list: linked with chains · linked without chains · valid but unlinked (the 444) · invalid id |
| **Benchmark** | S3 hadith → chains · S8 coverage abstention |
| **Differentiation** | Moderate — visible three-layer provenance is not something incumbent platforms expose |

### C04 · Recorded chains of a hadith — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | See every isnad MIS records for this hadith, kept separate and in order, with how many variants exist |
| **Example questions** | كم طريقًا رُوي بها هذا الحديث في MIS؟ · اعرض السند الثاني لهذا الحديث مرتَّبًا |
| **User inputs** | Local corpus id, or MIS `(book, hadith)`; optionally one `sanad_no` |
| **Data layer** | `isnad` + `transmission` + `mis_narrator` |
| **Minimum evidence** | One reconstructed chain with contiguous positions |
| **Allowed claims** | `RECORDED` MIS records N chains; this chain runs narrator A → B → … in the recorded transmission direction · `DERIVED` chain length and each narrator's position |
| **Forbidden claims** | That N is the complete number of routes for this hadith in the tradition · that direction implies a general teacher–student relation outside this chain · any soundness judgement |
| **Output** | One panel per chain — never merged — with ordered narrator rows, positions, MIS generation, and declared vs reconstructed variant count |
| **Why this class** | Ordered read, sub-millisecond, already built and verified against all 14,155 chains |
| **Failure modes** | An interface flattening variants into one narrator set — this destroys exactly the information the capability exists for · reading the 43 recorded later→earlier steps as data errors rather than preserved records |
| **Degradation** | Linked but no recorded isnad → that named status, with the MIS record still shown |
| **Benchmark** | S3 hadith → chains · S6 multi-isnad |
| **Differentiation** | Moderate. Separately addressable variants with a declared-count cross-check is stronger than a rendered tree |

### C05 · Narrator record card — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | See what MIS records about one narrator identity — nothing more |
| **Example questions** | ما الذي تسجّله MIS عن هذا الراوي؟ · في أي طبقة يضعه MIS؟ |
| **User inputs** | A MIS narrator id (from C06, C04 or C07) |
| **Data layer** | `mis_narrator` |
| **Minimum evidence** | The narrator id exists in MIS |
| **Allowed claims** | `RECORDED` MIS records these name forms, this generation, this id · `DERIVED` occurrence count |
| **Forbidden claims** | Any grading, biography, death date, teachers, students outside recorded chains, or identification with any historical person or Itqan profile |
| **Output** | Both Arabic name forms, MIS generation, id, occurrence count, and a permanent identity qualifier |
| **Why this class** | Single keyed read |
| **Failure modes** | The card reading as a biography page and inviting the grading question · the 80 narrators whose generation is `NotMapped` being rendered as unknown-but-inferable |
| **Degradation** | Unknown id raises rather than returning an empty record. `NotMapped` is displayed verbatim |
| **Benchmark** | S5 narrator records · S9 identity-blocked abstention |
| **Differentiation** | Inverted — the value is what it refuses to show |

### C06 · Narrator name resolution — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Go from an Arabic narrator name, as a person would type it, to the MIS narrator identities it could mean |
| **Example questions** | من هو «أبو هريرة» في بيانات MIS؟ · أي راوٍ يطابق «ابن شهاب»؟ |
| **User inputs** | An Arabic name string |
| **Data layer** | `mis_narrator` full and mapped name fields, under the project's existing narrow normaliser |
| **Minimum evidence** | At least one deterministic normalised match. Zero matches is a valid, informative result |
| **Allowed claims** | `DERIVED` under this normaliser, the name matches these MIS ids · `NOT_ESTABLISHED` no MIS identity matches this form |
| **Forbidden claims** | Picking one candidate silently · fuzzy or model-based matching presented as resolution · asserting the matched id is the historical person the user meant |
| **Output** | Candidate list with the matched field (full vs mapped short name), match kind, and an explicit ambiguity flag. Never auto-selects |
| **Why this class** | Deterministic string normalisation and lookup. Ambiguity is returned as data, so no judgement is needed |
| **Failure modes** | **The highest-risk capability in V1.** 14 mapped short names are shared by more than one id, so a short-form query can silently select the wrong narrator and corrupt every downstream comparison · a name form MIS never recorded returns nothing and reads as "this narrator does not exist" |
| **Degradation** | >1 candidate → `AMBIGUOUS`, candidates returned, no downstream capability runs until the user picks. 0 candidates → `NOT_FOUND` worded as "no MIS identity matches this name form" |
| **Benchmark** | S4 name resolution, including a dedicated shared-short-name stratum |
| **Differentiation** | High — incumbents resolve names silently; treating ambiguity as an output rather than a tiebreak is the safety property that makes C09–C14 defensible |

### C07 · Narrator occurrences — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | See every hadith and chain in which one MIS narrator identity appears |
| **Example questions** | في أي أحاديث يظهر هذا الراوي داخل أسانيد MIS؟ |
| **User inputs** | MIS narrator id |
| **Data layer** | `transmission`, both endpoint directions, plus the reverse link to local hadiths |
| **Minimum evidence** | The narrator exists. Zero occurrences is a valid result, distinct from an unknown id |
| **Allowed claims** | `RECORDED` this id appears at these chain coordinates · `DERIVED` the occurrence count |
| **Forbidden claims** | "This narrator narrated N hadiths" — occurrences are chain positions in one collection's MIS encoding, not a transmission count |
| **Output** | Occurrence table by `(book, hadith, sanad)`, each row resolving back to a local hadith where an accepted link exists |
| **Why this class** | Indexed read; the busiest narrator's 1,996 occurrences return in 9.4 ms |
| **Failure modes** | High-degree narrators producing unreadable result sets (max degree 3,992) · rows whose MIS hadith has no accepted local link (the 733) appearing to be missing data |
| **Degradation** | Paginate rather than truncate; any truncation states the withheld count. Unlinked MIS rows are labelled, not dropped |
| **Benchmark** | S5 narrator records |
| **Differentiation** | Moderate — the reverse resolution to a retrievable local hadith is the part incumbents cannot do |

### C08 · Chain neighbours of a narrator — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | See who a narrator received from and transmitted to *within one named chain* |
| **Example questions** | عمَّن روى هذا الراوي في هذا السند تحديدًا؟ ومن روى عنه فيه؟ |
| **User inputs** | Narrator id + `(book, hadith, sanad)` |
| **Data layer** | `transmission` scoped to one chain |
| **Minimum evidence** | The narrator appears in that chain |
| **Allowed claims** | `RECORDED` in this chain, X stands immediately before/after Y in the recorded transmission direction |
| **Forbidden claims** | Generalising a single occurrence into "X was Y's teacher" · any claim that adjacency implies a verified meeting |
| **Output** | Predecessor and successor rows with step position and the scope label *single isnad occurrence*, which the code already emits |
| **Why this class** | Scoped read, already built with the scope deliberately narrowed in the API itself |
| **Failure modes** | Users reading one adjacency as a biography claim — the most likely misuse in the whole structural layer |
| **Degradation** | Narrator not in that chain → the chain is validated first, so the error distinguishes "no such chain" from "not in this chain" |
| **Benchmark** | S5 narrator records · S9 identity-blocked abstention |
| **Differentiation** | Moderate — the deliberate refusal to aggregate is the design; C10 and C11 aggregate only with explicit scope wording |
### C09 · Isnad comparison within one hadith — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Compare the recorded chain variants of one hadith: which narrator identities recur, which transmissions repeat, where the chains diverge and converge |
| **Example questions** | قارِن أسانيد هذا الحديث: أين تتفق وأين تفترق؟ · ما الرواة المشتركون بين طرقه؟ |
| **User inputs** | One hadith identifier; optionally a subset of `sanad_no` |
| **Data layer** | Ordered chains from C04, then set and sequence operations over narrator ids and adjacent pairs |
| **Minimum evidence** | Two fully reconstructed chains of the same hadith |
| **Allowed claims** | `DERIVED` MIS assigns narrator id N to a position in both chains · these two chains share the adjacent pair (A→B) · they diverge after position k · `NOT_ESTABLISHED` no narrator identity is shared |
| **Forbidden claims** | "The same narrator appears in both chains" without the MIS qualifier · that shared narrators make a hadith stronger, corroborated, or *mutawātir* · any common-link or dating inference (U8) |
| **Output** | Aligned chain columns · shared-identity table with positions · shared adjacent-transmission table · divergence and convergence points · an explicit MIS-identity qualifier attached to the comparison itself |
| **Why this class** | Deterministic set arithmetic over at most 24 chains of at most 9 narrators. There is no decision a model could improve, and every intermediate is checkable |
| **Failure modes** | **Identity inheritance:** the entire result rests on MIS's narrator mapping, built with fuzzy matching and manual mapping and not independently validated · declared and reconstructed variant counts agreeing does not mean MIS captured every route in the tradition |
| **Degradation** | One chain only → return it with `PARTIAL` and the reason "one recorded variant; nothing to compare". Any chain touching a shared-short-name narrator → flag the comparison as identity-sensitive |
| **Benchmark** | S6 multi-isnad comparison · S7 shared-short-name sensitivity |
| **Differentiation** | **Highest in V1.** This is the wedge: incumbents render chains, they do not compute over them |

### C10 · Narrator pair relation — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Find what recorded relationship, if any, exists between two narrator identities across all available chains |
| **Example questions** | ما العلاقة المسجَّلة بين هذين الراويين في أسانيد MIS؟ · هل روى أحدهما عن الآخر مباشرةً؟ |
| **User inputs** | Two MIS narrator ids (each resolved through C06) |
| **Data layer** | `transmission` aggregated across all 14,155 chains |
| **Minimum evidence** | Both ids exist. A relation is not required — its absence is the answer |
| **Allowed claims** | `DERIVED` direct adjacency in N chains, listed · same-chain co-occurrence without adjacency in M chains · `NOT_ESTABLISHED` no recorded relation in the available MIS data |
| **Forbidden claims** | **"They never narrated from one another."** Absence in this dataset is not historical absence · any inference about whether they could have met |
| **Output** | Relation kind, count, the chains evidencing it, and the widening ladder shown explicitly so the user sees which rungs were empty |
| **Why this class** | The escalation — direct adjacency, then same-chain co-occurrence, then shared hadith, then shared neighbour — is a *fixed* sequence with early exit. A fixed ladder with early exit is a workflow, not a plan. The phase brief listed this as agentic; on inspection it is not |
| **Failure modes** | Absence read as denial · aggregation across chains implying a general relationship, when C08 deliberately scopes to one chain · either id being a shared-short-name collision |
| **Degradation** | No relation at any rung → `OK` with a `NOT_ESTABLISHED` claim and the ladder shown. Not an error, not an abstention |
| **Benchmark** | S7 cross-chain structure · S9 absence wording |
| **Differentiation** | High — and the wording discipline is most of the value |

### C11 · Narrator co-occurrence — `SANAD` · WORKFLOW

| Field | |
|---|---|
| **User goal** | See which narrator identities most often appear in the same chains as a given one |
| **Example questions** | من أكثر الرواة ورودًا مع هذا الراوي في نفس الأسانيد؟ |
| **User inputs** | MIS narrator id; optional minimum count |
| **Data layer** | `transmission` aggregated by chain membership |
| **Minimum evidence** | The narrator has at least one occurrence |
| **Allowed claims** | `DERIVED` in the available MIS chains, ids X and Y co-occur N times, of which M are direct adjacency |
| **Forbidden claims** | Any centrality or importance framing · any suggestion that a high count indicates reliability, seniority or a documented relationship |
| **Output** | Ranked co-occurrence table with counts split into adjacent and non-adjacent, each row linking to evidencing chains |
| **Why this class** | One aggregation query. Ranking is by count, which is a fact, not a judgement |
| **Failure modes** | Counts reading as network importance · corpus artefacts dominating — high-frequency compilers' teachers will top nearly every list |
| **Degradation** | Below the minimum count → empty table with the threshold stated, never silently widened |
| **Benchmark** | S7 cross-chain structure |
| **Differentiation** | Moderate. Cheap to compute, easy to misread — ships only with the counts-are-not-importance qualifier |

### C12 · Cross-hadith chain comparison — `CROSS_LAYER` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Given several hadiths, compare their chains: which narrator identities and transmissions are shared across the set |
| **Example questions** | قارِن أسانيد هذه الأحاديث الثلاثة وبيِّن الرواة المشتركين بينها |
| **User inputs** | An explicit hadith set, or a topic query that produces one |
| **Data layer** | Retrieval (when the set is topical) → linkage → chains → the same comparison operations as C09 |
| **Minimum evidence** | At least two hadiths with at least one reconstructed chain each |
| **Allowed claims** | `DERIVED` all cross-chain structure, always scoped to *the hadiths examined* · `MODEL_ASSERTED` the topical relevance of the set, when retrieval selected it |
| **Forbidden claims** | That the compared set is all the corpus offers on the topic · that shared narrators across topics mean anything about the topic · any authenticity implication |
| **Output** | Per-hadith chain panels · cross-set shared-identity matrix · **a mandatory coverage block** naming every hadith excluded and why |
| **Why this class** | **Workflow.** The code path is predefined — select, resolve, filter, compare — and fan-out over an unknown-size set is a bounded loop, not a decision. Unknown set *size* and model-influenced set *membership* are properties of the evidence, not of the orchestration; they make this `CROSS_LAYER`, not agentic |
| **Failure modes** | **Silent coverage loss:** some retrieved hadiths fall in the 444 and have no chains, so the comparison quietly runs on a subset · fan-out cost growing with set size · retrieval bias determining which chains ever get compared |
| **Degradation** | `PARTIAL` whenever any member is excluded, with ids listed. Fewer than two comparable members → `PARTIAL` with the comparison declined, not an empty matrix |
| **Benchmark** | S7 cross-hadith structure · S8 coverage abstention |
| **Differentiation** | High — this capability needs both halves of the system and cannot be reproduced by a search product or by the raw dataset alone |

### C13 · Topic + narrator constrained retrieval — `CROSS_LAYER` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Find hadiths on a topic whose recorded chains include a given narrator identity |
| **Example questions** | ابحث عن أحاديث في الصدق يرد في أسانيدها هذا الراوي |
| **User inputs** | Topic phrase + narrator name (resolved via C06) or id |
| **Data layer** | Retrieval → linkage → chains → membership filter |
| **Minimum evidence** | At least one retrieved, linked hadith whose chain contains the id |
| **Allowed claims** | `DERIVED` among the hadiths retrieved for this topic *and* carrying an accepted MIS link, these have the narrator in a recorded chain |
| **Forbidden claims** | **Never "narrator X narrated N hadiths about topic T."** The result is bounded by retrieval depth and by linkage coverage, twice over |
| **Output** | Filtered hadith cards with the matching chain and position highlighted, plus retrieval depth and excluded-unlinked counts stated |
| **Why this class** | **Workflow.** Reclassified on review: a single predetermined rewrite branch on an empty constrained result is fixed branching written into the code path, not a model choosing its own next operation. The repository already contains this exact pattern — CRAG self-grading with one rewrite — implemented as a configuration flag, not as an agent |
| **Failure modes** | Empty result read as "this narrator never transmitted on this topic" — the compound of production retrieval depth and a 5.95% coverage gap · unbounded reformulation loops |
| **Degradation** | Empty → `NOT_ESTABLISHED` stating both bounds explicitly. Reformulation capped at one attempt in V1, mirroring the measured CRAG result |
| **Benchmark** | S7 cross-chain structure · S8 coverage · S10 adversarial |
| **Differentiation** | High — the flagship join of matn retrieval and chain structure, and the clearest demonstration of the wedge |

### C14 · Open structural investigation — `CROSS_LAYER` · **AGENT**

| Field | |
|---|---|
| **User goal** | Answer an open structural question whose evidence operations cannot be enumerated before execution |
| **Example questions** | ابدأ من هذا الحديث وتتبَّع ما تشترك فيه أسانيده مع أحاديث أخرى في نفس الباب، وبيِّن أين ينقطع الدليل |
| **User inputs** | An Arabic research question, optionally seeded with identifiers |
| **Data layer** | Every deterministic operation behind C01–C13, called as tools. The agent derives nothing itself |
| **Minimum evidence** | At least one evidence item traceable to a deterministic operation. An investigation with no traceable item terminates as `ABSTAINED` |
| **Allowed claims** | Only claims composed from tool outputs, each carrying the tool call that produced it. Every claim inherits the strictest claim type among its evidence |
| **Forbidden claims** | Anything not traceable to a tool result · any claim from model knowledge about hadith, narrators or history · summarising away an evidence gap |
| **Output** | Evidence board — claims, evidence items with provenance, gaps, limitations — plus the full trail of operations, including those that returned nothing |
| **Why this class** | The only capability where the *next* operation genuinely depends on an intermediate observation and no fixed ladder covers the space: a discovered narrator determines the next lookup, an empty rung changes the question, and the stopping point is a judgement about sufficiency |
| **Failure modes** | Unnecessary tool calls inflating cost with no evidence gain · non-termination · summarisation that loses provenance · **the agent producing a workflow-equivalent trajectory**, which would falsify the whole capability |
| **Degradation** | Step budget exhausted → return the partial board with an explicit *incomplete* marker, never a synthesised conclusion. Any tool returning `AMBIGUOUS` → stop and ask; never guess a narrator |
| **Benchmark** | S7 · S8 · S9 · S10, each with a trajectory *contract* — not a reference sequence — and a comparison against the frozen workflow baseline |
| **Differentiation** | Unproven. This is a hypothesis to be tested in G4, not a feature to be assumed |

### C15 · Evidence-gap diagnostic — `CROSS_LAYER` · WORKFLOW

| Field | |
|---|---|
| **User goal** | Ask why the system cannot answer, and get a specific layer rather than a refusal |
| **Example questions** | لماذا لا يوجد سند لهذا الحديث عندكم؟ · ما الذي ينقص حتى تجيبوا عن حكم هذا الراوي؟ |
| **User inputs** | A hadith id, a narrator id, or a previously refused question |
| **Data layer** | Linkage coverage, graph statuses, and the negative matrix in §9 |
| **Minimum evidence** | None beyond system state — this capability reports the system's own boundaries |
| **Allowed claims** | `UNAVAILABLE` the missing layer, named · `DERIVED` corpus-level coverage figures · `OUT_OF_SCOPE` with the negative-matrix entry cited |
| **Forbidden claims** | Promising a date when a layer will exist · implying the answer would be obtainable elsewhere without saying where · any hint at what the blocked answer might be |
| **Output** | The named missing layer, the coverage figure it belongs to, and what would have to become true — an adjudicated identity sample, a wider corpus, a different collection |
| **Why this class** | A lookup against a fixed table of statuses and policies |
| **Failure modes** | Sounding like an excuse rather than a diagnosis · leaking a partial answer while explaining why there is none |
| **Degradation** | Cannot itself fail; an unrecognised layer returns a generic `UNSUPPORTED` with the question logged for review |
| **Benchmark** | S8 coverage · S9 identity-blocked · S10 adversarial |
| **Differentiation** | **High and underrated.** "Which layer is missing" is a real research answer. Incumbents return nothing; Musnad returns a diagnosis |

---

## 9. V1 unsupported and deferred matrix

Eight entries. Each names the missing evidence, not a policy preference. None is answerable
"from general model knowledge" — if Musnad's trusted evidence cannot establish it, Musnad
abstains.

### U1 · Narrator grading / "is narrator X trustworthy?" — BLOCKED-BY-IDENTITY

- **Missing evidence.** An adjudicated MIS → Itqan person identity. 2,001 of 2,092 narrators
  have **no accepted frozen canonical or alias resolution** under the narrow identity
  representation. That is not the same as having no candidate: the unmatched diagnostic found
  **1,207** of them carry at least one exact candidate through MIS's documented short-name
  field — **890** with a single exact profile, **317** with several — and only **6** have no
  exact structural candidate at all. Every such row is labelled `DIAGNOSTIC_CANDIDATE`, never
  `MATCH`, and no recall claim is made. A grade exists only on a source record, and no source
  record is reachable from the graph.
- **System response.** `UNSUPPORTED` · "Musnad holds no grading layer. Narrator identities
  here are MIS operational identities and are not linked to any rijal profile." C15 then names
  the missing layer.
- **Reopens when.** The validation protocol runs: 300 adjudicated pairs per auto-merging
  rule, zero false merges, κ ≥ 0.6.

### U2 · Historical-person identity — "are these two the same person?" — BLOCKED-BY-IDENTITY

- **Missing evidence.** Any identity-bearing field. The 40-case calibration found none in
  Itqan v1.20 and no positive anchor to validate against; Itqan itself carries 17,618
  unresolved profile-multiplicity groups and 17,333 multiprofile source keys. Abundant
  candidates make this worse, not better: 317 unmatched narrators have *several* exact
  short-name candidates, so the failure mode is choosing among plausible profiles, not
  finding one.
- **System response.** `UNSUPPORTED` for all 2,092 narrators without exception — including
  the 81 provisional candidates, which are never surfaced as identity in the product.
- **Reopens when.** Adjudicated identity evidence exists. Never on rule coverage.

### U3 · Authenticity or chain-soundness verdict — REQUIRES-DOMAIN-EXPERT

- **Missing evidence.** Narrator reliability, which requires U1, which requires U2. Also
  continuity judgement, which the graph cannot supply: it records transmission as MIS asserts
  it and does not verify those assertions against the classical literature.
- **System response.** `UNSUPPORTED`. Structural output is never framed as evidence for or
  against soundness — this constraint binds C09, C10, C11 and C12 at the wording level.
- **Reopens when.** Not a V-numbered item. This is a scholarly judgement, not a data gap.

### U4 · Fatwa, ruling, or practical religious guidance — REQUIRES-DOMAIN-EXPERT

- **Missing evidence.** Not an evidence question. Rulings require juristic reasoning across
  sources and context; institutional positions hold this exclusively with qualified scholars,
  and documented chatbot failures include misattributed verses and hadith.
- **System response.** `UNSUPPORTED` with a redirect to what Musnad can do — surface what the
  corpus records, with numbers — and no attempt at a partial answer.
- **Reopens when.** Never.

### U5 · Cross-book takhrij and variant discovery — BLOCKED-BY-DATA

- **Missing evidence.** Any second collection. The corpus is Sahih Muslim; MIS is Sahih
  Muslim; `book_no` is constant at `'2'` throughout the graph.
- **System response.** `UNSUPPORTED` · "Musnad indexes Sahih Muslim only." Explicitly
  including the inverse claim: Musnad may never say a hadith appears *only* in Muslim.
- **Reopens when.** V2 — and the linkage artifact must carry the book per row first.

### U6 · Temporal and geographic narrator reasoning — BLOCKED-BY-DATA

- **Missing evidence.** Validated death dates and localities attached to narrator identities.
  Itqan holds reported deaths with contradictions across profiles, and no adjudicated link to
  MIS ids exists. MIS supplies a generation label only, with 80 `NotMapped`.
- **System response.** `UNSUPPORTED` for meeting-plausibility and locality questions.
  Generation is reported as a recorded MIS attribute and never used to infer contemporaneity —
  the 43 recorded later→earlier steps show why that inference would be wrong.
- **Reopens when.** V2, after U2.

### U7 · General teacher/student and biography claims — BLOCKED-BY-IDENTITY

- **Missing evidence.** Biographical records tied to a resolved person. What exists is
  adjacency inside individual chains of one collection — which is why the API scopes
  neighbours to a single isnad and labels the scope in its own output.
- **System response.** `UNSUPPORTED` for "who were X's teachers". C08 answers the narrower
  recorded question and states its scope; C11 aggregates only with the
  counts-are-not-relationships qualifier.
- **Reopens when.** V2, after U2.

### U8 · Common-link dating and origin attribution — V1-OUT-OF-SCOPE / FUTURE-RESEARCH

- **Missing evidence.** Not primarily data — *interpretation*. Convergence on a shared
  narrator supports opposite historical conclusions depending on the school: a common link as
  originator in Schacht and Juynboll, and explicitly not as originator in Motzki's
  *isnād-cum-matn* response. A single-collection graph also cannot see the convergence the
  method requires.
- **System response.** `UNSUPPORTED`. C09 and C12 may report a convergence point as a
  structural fact; neither may name it a common link, date a report, or attribute origination.
- **Reopens when.** Research backlog, and only with a domain expert defining what the system
  may say.

> **Standing rule.** "The model probably knows this" is never a reason to answer. Every entry
> above stays refused even when the underlying fact is well known outside Musnad, because the
> product's guarantee is about *where its statements come from*, not about whether they happen
> to be true.
---

## 10. Evidence contracts

Defined once as three classes and assigned per capability. Capability-specific overrides live
in §8.

### Contract E1 — matn evidence · C01 C02 C03

| | |
|---|---|
| **Required evidence** | ≥1 retrieved chunk carrying a resolvable `hadith_id`, or one valid corpus identifier |
| **Sufficient** | Every hadith number in the output appears in the supplied context and resolves to a corpus record; the quoted matn appears in one of them |
| **Insufficient** | Nothing retrieved above threshold · a cited number absent from context, twice · a paraphrase not traceable to a supplied matn |
| **Provenance required** | Hadith number · book and chapter · retrieval rank and score · retriever configuration identifier |
| **Allowed inference** | Summarising and reordering supplied matns; stating that a supplied matn addresses the question |
| **Forbidden inference** | Completeness ("these are all the hadiths on X") · any claim about a hadith not supplied · rulings · authenticity · absence from the corpus on the basis of a retrieval miss |

### Contract E2 — structural evidence · C04 C05 C06 C07 C08 C09 C10 C11

| | |
|---|---|
| **Required evidence** | Records read from the graph under its enforced invariants: contiguous positions, resolving endpoints, chains never merged |
| **Sufficient** | Every asserted narrator, position, adjacency or count is present in a returned row, and every derived value recomputes from those rows |
| **Insufficient** | A narrator id that does not exist · a chain that does not reconstruct · any comparison resting on a name rather than an id · a single unresolved `AMBIGUOUS` resolution anywhere upstream |
| **Provenance required** | `(book, hadith, sanad, position)` for every step · MIS narrator id for every narrator · `recorded_in: MIS` · the identity qualifier verbatim |
| **Allowed inference** | Deterministic set and sequence operations: shared ids, shared adjacent pairs, divergence and convergence positions, counts, chain length |
| **Forbidden inference** | Same MIS id ⇒ same historical person · adjacency ⇒ a documented teacher–student relationship · absence ⇒ historical falsity · counts ⇒ importance, reliability or centrality · generation ⇒ contemporaneity |

### Contract E3 — cross-layer evidence · C12 C13 C14

| | |
|---|---|
| **Required evidence** | E1 *and* E2 satisfied for every record in the examined set, plus an explicit record of which candidates were excluded and why |
| **Sufficient** | ≥2 comparable records with reconstructed chains, and a coverage statement enumerating every excluded identifier |
| **Insufficient** | Fewer than two comparable members · any member crossing the linkage without its status carried · an unstated exclusion |
| **Provenance required** | All of E1 and E2 · the linkage version and artifact SHA-256 for every crossing · the ordered trail of operations, including empty results |
| **Allowed inference** | E2 operations over the set; stating the set's topical relevance as model-asserted |
| **Forbidden inference** | Generalising from the examined set to the corpus · treating an excluded record as absent evidence · aggregating a claim whose evidence items carry different claim types without inheriting the strictest |

### The two distinctions that must survive into wording

- A local hadith with no accepted MIS link means **no accepted linkage is available**. It does
  not mean the hadith has no sanad — Sahih Muslim's hadiths all carry chains; what is missing
  is Musnad's join to MIS.
- No recorded relation between two narrators means **not established in the available data**.
  It does not mean the relation is historically false, and the system may never phrase it as a
  denial.

---

## 11. Claim language policy

Seven claim types. Every user-visible statement carries exactly one, and a composed claim
inherits the strictest type among its evidence. Arabic is the product language, so the
templates are normative in Arabic.

| Type | Means | Arabic template |
|---|---|---|
| `RECORDED` | Present verbatim in a named source | وفق ما هو مسجَّل في MIS… |
| `LINKED` | Reached by crossing the accepted linkage — a textual match, not an identity | يربط الربط المعتمد هذا الحديث بسجل MIS رقم… |
| `DERIVED` | Computed deterministically from recorded facts | بحساب الأسانيد المتاحة، يشترك السندان في… |
| `MODEL_ASSERTED` | Written by the model, bounded by supplied evidence | استنادًا إلى النصوص المسترجَعة أعلاه… |
| `NOT_ESTABLISHED` | Absent from available data — never a denial | لا توجد علاقة مسجَّلة بينهما في بيانات MIS المتاحة لمُسنَد |
| `UNAVAILABLE` | The layer does not exist in the system | لا يوجد لدى مُسنَد طبقة أحكام على الرواة |
| `OUT_OF_SCOPE` | Refused by policy, with the matrix entry cited | هذا خارج نطاق مُسنَد؛ وهو أداة بحث لا جهة إفتاء |

### Wording, tested

| Good | Bad |
|---|---|
| يشترك هذان السندان في راوٍ تُسنِد إليه MIS المُعرِّف نفسه.<br>*The two chains share a narrator to which MIS assigns the same identifier.* | نفس الراوي يظهر في السندين.<br>*"The same narrator appears in both chains" — asserts person identity the data cannot support.* |
| لا يوجد ربط MIS معتمد لهذا الحديث حاليًا؛ وهذا لا يعني أن الحديث بلا سند.<br>*No accepted MIS linkage is currently available — which does not mean the hadith has no sanad.* | لا سند لهذا الحديث.<br>*"This hadith has no sanad" — confuses a coverage gap with a fact about the hadith.* |
| لم تُسجَّل رواية مباشرة بينهما في أسانيد MIS المتاحة.<br>*No direct transmission between them is recorded in the available MIS chains.* | لم يروِ أحدهما عن الآخر قط.<br>*"Neither ever narrated from the other" — turns dataset absence into historical denial.* |
| هذه الأسانيد كما تسجّلها MIS، وليست السلسلة التاريخية المعتمدة.<br>*These are the chains as MIS records them, not the canonical historical chain.* | هذا هو سند الحديث الصحيح · هذا الراوي ضعيف.<br>*"This is the authentic chain" · "This narrator is weak" — both are blocked capabilities.* |

### Three rules that bind every surface

1. **Never state absence as denial.** Absence is always scoped to *the data available to
   Musnad*.
2. **Never drop the qualifier to improve readability.** If the qualifier does not fit the
   layout, the layout changes.
3. **A composed claim inherits the strictest type among its evidence.** One `MODEL_ASSERTED`
   item makes the whole claim model-asserted.

---

## 12. Failure and status taxonomy

One vocabulary shared by tools, workflows, agent state, API and monitoring. Seven statuses —
the smallest set preserving differences that change behaviour — plus a separate
`missing_layer` field lifted from the vocabulary already in the code, so the two axes never
multiply into thirty statuses.

| Status | Meaning | User-visible | Retry? | Clarify? | Technical failure |
|---|---|---|---|---|---|
| `OK` | Every evidence obligation met for the full requested scope | Yes | No | No | No |
| `PARTIAL` | Answered for part of the scope; the excluded part is enumerated | Yes, prominently | No | Sometimes | **No** |
| `AMBIGUOUS` | The request resolves to more than one entity; candidates returned, none chosen | Yes | No | **Yes — the defining case** | No |
| `NOT_FOUND` | The requested record does not exist, or nothing was retrieved | Yes | Rephrasing may help | Sometimes | No |
| `ABSTAINED` | The record exists; the layer needed to answer does not. Carries `missing_layer` | Yes, with the layer named | No | No | **No** |
| `UNSUPPORTED` | Outside the V1 contract by policy. Carries the §9 entry id | Yes, with the reason | No | No | No |
| `ERROR` | The system failed. Carries an internal `error_class` | Yes, plainly | Yes | No | **Yes — the only one** |

### `missing_layer` — the second axis

Attached to `ABSTAINED`, and to `PARTIAL` for each excluded record. Values are the
repository's own status vocabulary raised to product level, so no layer invents new words.

| Value | Means | Population |
|---|---|---:|
| `NO_ACCEPTED_MIS_LINK` | Real local hadith, no accepted linkage | 444 |
| `NO_ACCEPTED_LOCAL_LINK` | Real MIS record, no accepted local hadith | 733 |
| `NO_RECORDED_ISNAD` | Linked, but MIS records no chain | per record |
| `NO_SUCH_LOCAL_HADITH` | Not a corpus identifier | — |
| `NO_SUCH_MIS_RECORD` | Not a MIS identifier | — |
| `NO_SUCH_MIS_NARRATOR` | Not a MIS narrator id | — |
| `HISTORICAL_IDENTITY_UNRESOLVED` | Requires the closed entity-resolution gate | 2,092 |
| `GRADING_LAYER_ABSENT` | No grade exists in the system at all | all |
| `OUT_OF_CORPUS` | Outside Sahih Muslim | — |

> **Two rules that are easy to break in metrics.** **`ABSTAINED` is not `FAILED`** — a correct
> abstention is a success and must be counted as one, or the system will be optimised toward
> answering things it cannot support. **`PARTIAL` is not `FAILED`** — with 444 unlinked
> hadiths, partial coverage is the expected outcome of many correct investigations. Dashboards
> that colour both red will drive exactly the wrong engineering.

### Statuses deliberately not created

`TOOL_ERROR` and `DEPENDENCY_ERROR` collapse into `ERROR` with an internal class — the
distinction matters to monitoring, never to a user or an evaluation. `INSUFFICIENT_EVIDENCE`
collapses into `ABSTAINED` with a `missing_layer`, because a bare insufficiency claim is
exactly the undiagnostic refusal this system exists to avoid. `UNLINKED` is not a status; it
is `ABSTAINED` or `PARTIAL` with `NO_ACCEPTED_MIS_LINK`.

---

## 13. Workflow vs agent decision rules

The policy a router will eventually implement. Not the router.

**Definitions.** A **workflow** orchestrates models and tools through predefined code paths,
including bounded loops, fixed branching, fan-out, and predetermined retry or rewrite
branches. An **agent** is a system in which the model dynamically determines its own sequence
of operations based on intermediate observations. There is no third orchestration class.

| Capability | Class | Deciding reason |
|---|---|---|
| C01 · C02 · C03 · C04 · C05 · C06 · C07 · C08 | WORKFLOW | Single deterministic operation, or a fixed chain of them. Nothing observed changes what runs next |
| C09 Isnad comparison | WORKFLOW | Fan-out over ≤24 chains then set arithmetic. Unknown fan-out width is a loop bound, not a decision |
| C10 Narrator pair relation | WORKFLOW | A fixed escalation ladder with early exit. Reclassified from the brief's agentic framing — a fixed ladder is a workflow however many rungs it has |
| C11 Co-occurrence | WORKFLOW | One aggregation query |
| C12 Cross-hadith comparison | WORKFLOW | Fan-out over an unknown-size set, then fixed comparison. `CROSS_LAYER` evidence; predefined code path |
| C13 Topic + narrator | WORKFLOW | Retrieval, membership filter, and one predetermined rewrite branch. `CROSS_LAYER` evidence; predefined code path |
| C15 Gap diagnostic | WORKFLOW | Lookup against a fixed status and policy table |
| C14 Open investigation | **AGENT** | Next operation depends on intermediate evidence; entities discovered mid-run determine later operations; termination is a sufficiency judgement |

### The rules, derived

**Prefer workflow when:** the operation sequence is known before execution · branching is
bounded and enumerable, including long fixed ladders with early exit · fan-out width is
unknown but the operation per item is fixed · the result is checkable by recomputation · a
negative result already exists for adding agency to this path.

**Agent may be justified when:** the next useful operation depends on what the last one
returned · entities discovered during the run determine later operations · the goal needs
decomposition that cannot be written down in advance · stopping is a judgement about evidence
sufficiency, not a counter · encoding it as a workflow would need a branch tree nobody can
enumerate or test.

### What does not make a task agentic

- **Multiple tools.** C12 calls five kinds of operation and remains a workflow.
- **RAG plus graph.** That is an evidence pipeline — `CROSS_LAYER` — not an orchestration
  class.
- **LLM tool calling.** A model emitting a fixed call sequence is a workflow with an expensive
  dispatcher.
- **Many steps.** C10's four-rung ladder is deterministic at every rung.
- **Unknown fan-out.** Iterating an unknown-length list is a loop.
- **A predetermined retry or rewrite branch.** Fixed branching written into the code path.

### Edge cases, decided

| Case | Ruling |
|---|---|
| Narrator name resolves ambiguously mid-run | Not agency. Stop, return `AMBIGUOUS`, ask. Guessing here corrupts everything downstream |
| Retrieval returns nothing for a constrained query | Still a workflow. One predetermined rewrite branch is fixed branching. Repository evidence supports capping it: CRAG self-grading with one rewrite was built and measured with no gain |
| A comparison spans 24 chains | Still a workflow. Size is not complexity |
| The user asks a compound question in one sentence | Decompose deterministically into capability calls if the parts are recognisable; route to C14 only if they are not |
| An investigation could continue indefinitely | Agent, but with a hard step budget and a required evidence-gain check per step |

---

## 14. V1 investigation agent mission

> **A bounded evidence-gathering agent for structural questions over Sahih Muslim whose
> required sequence of deterministic operations cannot be determined before execution. It
> selects and orders operations, records what each returned, and stops. It derives nothing.**

| | |
|---|---|
| **Responsibilities** | Decompose the question into deterministic operations · choose the next operation from the last result · record every call and result, including empty ones · assemble the evidence board · decide when further operations would add no evidence · state what could not be established |
| **Non-responsibilities** | Computing structural facts — those come only from tools · resolving narrator ambiguity — it stops and asks · judging identity, reliability or authenticity · answering from model knowledge · deciding that a coverage gap does not matter · smoothing a partial result into a clean conclusion |
| **Allowed operations** | Exactly the deterministic operations behind C01–C13, and nothing else. No web access, no second corpus, no free SQL, no Itqan reachability of any kind |
| **Termination** | Stop at the first of: the question's claims are all evidenced or explicitly marked as gaps · the last operation added no new evidence item · the step budget is exhausted · an `AMBIGUOUS` result requires the user. Budget exhaustion returns a board marked incomplete, never a conclusion |
| **Abstention** | Any claim without a traceable evidence item is dropped from the board, not softened. If nothing survives, the run returns `ABSTAINED` with a named missing layer. Reaching the negative matrix ends the run as `UNSUPPORTED` immediately |

> **The agent must be deletable.** C14 exists as a hypothesis. G4 must run the same benchmark
> questions through a workflow baseline that decomposes what it can and abstains otherwise. If
> the agent does not produce more correct evidence items, or produces them at a cost not worth
> paying, it is removed and its questions move to `UNSUPPORTED`. That outcome is a valid result
> of this project, not a failure of it.

---

## 15. Product output and information architecture

Information architecture only. No interface design, no components.

| Output object | Ask | Explore | Investigate | Contains |
|---|---|---|---|---|
| Answer prose | Required | — | Optional summary | Model-asserted text, citation-enforced |
| Hadith card | Per citation | Primary | Per evidence item | Number, book, chapter, vocalised matn, linkage status |
| Ordered chain panel | On request | Primary | Per structural item | One panel per variant, never merged; positions, MIS generation |
| Comparison view | — | — | Required for C09/C12 | Aligned chains, shared-identity table, divergence points |
| Occurrence / co-occurrence table | — | Primary | Supporting | Chain coordinates, counts split adjacent vs non-adjacent |
| Evidence board | — | — | **Required** | Claims → evidence → gaps → limitations |
| Coverage block | When a citation is unlinked | Inline status | **Required** | Excluded identifiers with `missing_layer` each |
| Provenance footer | Required | Required | Required | Linkage version + SHA, graph hash, retriever config, `basis` string |
| Operation trail | — | — | Required | Ordered calls with arguments and statuses, empty results included |
| Export | Optional | Optional | Required | JSON, the board verbatim, plus a Markdown rendering |

### Three invariants

1. **Every claim is openable.** Any statement in Ask or Investigate resolves to an Explore
   view of the record behind it. A claim that cannot be opened must not be displayed.
2. **Coverage is never collapsed.** Excluded records are shown at the same visual weight as
   included ones. Hiding them in a tooltip is a specification violation, not a design choice.
3. **Export is lossless.** The exported board is the internal object, not a prose rendering of
   it — otherwise the researcher cannot cite what the system actually did.

Deliberately **not** an output: confidence scores on structural facts (they are deterministic;
a score would imply doubt that does not exist), narrator "profiles" of any kind, and a
polished narrative research report, which invites exactly the over-reading the claim policy
forbids.

---

## 16. Evidence board — decision

**Adopt for Investigate only.** Ask and Explore do not adopt it — they already carry their
evidence.

Ask has citation enforcement measured at 0% invalid attempts; a board would restate what the
citation already guarantees. Explore *is* evidence — the record is the answer. Adding a board
to either would be ceremony.

Investigate is different in kind. Its output is a conclusion composed from several operations,
some of which returned nothing. Without an explicit object, three things become unmeasurable:
which claim rests on which record, which gaps were found rather than skipped, and whether the
agent's extra operations produced extra evidence. The last is the question G4 exists to
answer, so the board is a precondition for evaluating the agent at all — not a presentation
layer.

| Concept | Asserts | Must carry |
|---|---|---|
| **Investigation** | The question asked and the scope actually examined | Question, resolved entities, corpus scope, operation budget, final status |
| **Claim** | One statement the system is willing to make | Claim type from §11, text, evidence item ids, inherited-strictest type |
| **EvidenceItem** | One record or derived fact supporting a claim | Operation that produced it, arguments, exact record key `(book, hadith, sanad, position)` or hadith number, linkage status where crossed |
| **EvidenceGap** | Something sought and not established | What was sought, operations attempted, `missing_layer`, and whether it is a coverage gap or an identity gap — a distinction that changes what the user should do next |
| **Limitation** | Why the system stopped, structurally rather than incidentally | Termination reason, unexamined scope, and the standing qualifiers that apply to the whole board |

Cost is low: the objects are what the operations already return, plus references. No schema is
designed here.

---

## 17. V1 scope freeze

### Musnad V1 — IN

| | |
|---|---|
| **Capabilities** | C01–C15 as specified. Fourteen workflows, one agent |
| **Corpus** | Sahih Muslim only — 7,459 local hadiths, 7,748 MIS records, 14,155 chains, 2,092 MIS narrator identities |
| **New deterministic work** | Narrator name resolution with ambiguity as output · chain-set comparison · pair relation · co-occurrence · batched context over a result set |
| **Contracts** | Status taxonomy · claim language policy · evidence contracts E1–E3 · evidence board for Investigate |
| **Evaluation** | The G2 benchmark, a workflow baseline for every capability, and an agent-versus-baseline comparison for C14 |
| **Surfaces** | A read-only API over the deterministic operations, plus whatever minimal interface renders §15 |

### Musnad V1 — OUT

| | |
|---|---|
| **Blocked by identity** | Narrator gradings · biography · MIS↔Itqan resolution · `HistoricalNarrator` · any reliability judgement · any candidate identity shown as identity |
| **Blocked by data** | Additional collections · cross-book takhrij · *shawāhid* and *mutābaʿāt* · temporal or geographic reasoning |
| **Out by policy** | Rulings and fatwa · authenticity verdicts · common-link dating · matn criticism |
| **Out by engineering judgement** | Router and mode classification · long-term memory · multi-agent systems · a graph database · network analytics such as centrality or community detection · query expansion, which remains an unvalidated hypothesis · CRAG, which is built, measured and stays disabled |
| **Deferred to the engineering roadmap** | Public multi-tenant deployment sits outside the V1 *functional* scope. **Deferred, not abandoned** — nothing in this contract argues Musnad should stay un-deployed. After the agent and evaluation work, the project intends to proceed through: a production-shaped local service · an API · persistence · observability · reliability testing · security · containerisation · AWS staging · production deployment. No AWS architecture is designed in G1 |

> **Freeze rule.** Nothing enters V1 after this point without either removing something of
> comparable size, or a measurement showing it is required for a supported capability to be
> correct. The narrator-name-resolution gap entered by that rule: without it, seven
> capabilities have no entry point.

---

## 18. V2 and research backlog

| Track | Blocked on | First step | Priority |
|---|---|---|---|
| Historical narrator identity | Adjudicated labels — 300 pairs per auto-merging rule, κ ≥ 0.6, zero false merges | Recruit two rijal specialists; close the packet's join-key leak first | Highest — unlocks four other tracks |
| Source-specific gradings | Identity, then the provenance model where a grade exists only on a source record | Nothing until identity opens | High, fully dependent |
| Second collection | A comparable chain dataset; the linkage artifact carrying the book per row | Survey chain datasets beyond MIS; decide whether Sanadset-scale data is usable at Musnad's evidence bar | Medium — biggest user-value jump, largest integrity risk |
| Cross-book variant discovery | The above | — | Medium |
| Temporal analysis | Validated death dates per identity; Itqan's reported deaths contradict across profiles | Quantify contradiction rate on any identity-resolved subset | Low |
| Geographic analysis | Validated localities | — | Low |
| Network analytics | Nothing technical — but centrality over MIS ids measures MIS's mapping as much as transmission | Define what a centrality number would *mean* before computing one | Low, high misuse risk |
| Expert review workflow | Reviewer recruitment | Reuse the blinded packet design from the identity protocol | Medium — also the identity track's dependency |
| Query expansion | Nothing — but it is an unvalidated hypothesis against 3 known-unretrievable questions | Measure before implementing, per existing project practice | Low |
---

## 19. Success metrics to measure

What must be measured, not what the numbers should be. Every threshold is
`TO_BE_CALIBRATED_AND_PRE_REGISTERED_IN_G2`. Where a measured baseline already exists it is
named, because those are the only non-hypothetical numbers in this document.

### Product and task quality

| Metric | Definition | Existing baseline |
|---|---|---|
| Task success | Correct outcome for the capability's own contract, judged per stratum — never pooled across strata with different denominators | Answer path only: 22/27 correct citation — a non-blind historical figure, valid for regression against the same fingerprint, not as an unbiased estimate |
| Evidence correctness | Every returned evidence item is genuinely in the graph or corpus at the stated coordinates | Deterministically checkable; no baseline needed |
| Evidence completeness | Fraction of gold evidence items the system returned, computed against the graph itself | None |
| Grounded-claim rate | Claims traceable to an evidence item ÷ all claims | Invalid citation attempts 0/30; wrong in-context citation 3/30 |
| Abstention correctness | Two-sided: correct abstentions ÷ questions that should abstain, *and* false abstentions ÷ answerable questions | 3/3 correct refusal; 0 false refusals over the 22 questions whose gold hadith reached the context |
| Missing-layer accuracy | When abstaining, was the named layer the right one | None — new |
| Claim-type correctness | Each statement carries the right §11 type, and composed claims inherit the strictest | None — new |
| Coverage disclosure | Every excluded record enumerated. Any silent exclusion is a hard failure regardless of answer quality | None — new |

### Agent value — the falsification metrics

Which of these are *primary* and which are secondary, efficiency or safety is pre-registered
in G2 (§20) before the holdout is opened. G1 names the metrics; it does not rank them or set
thresholds.

| Metric | Why it decides C14's existence |
|---|---|
| Agent vs workflow-baseline delta | Per stratum, on evidence completeness and task success, from one blind paired run against a frozen baseline. No delta ⇒ delete the agent |
| Trajectory validity | Judged against the trajectory contract — required evidence obtained, required and forbidden operations respected, dependency order held, arguments correct. Multiple valid paths pass; an expected sequence is used only for deterministic workflows |
| Evidence gain per step | New evidence items ÷ operations. Steps producing nothing are the cost of agency |
| Unnecessary operation rate | Calls a workflow would not have made and that added no evidence item |
| Termination behaviour | Terminated by evidence exhaustion vs by budget. Budget-terminated runs are incomplete by definition |
| Ambiguity handling | Stopped and asked on `AMBIGUOUS`, never guessed. A single guess is a **hard-fail** and is vetoing, not averaged |

### Cost and reliability

| | |
|---|---|
| **Latency** | End to end, split into deterministic and model time. Deterministic operations are sub-millisecond today, so any latency belongs to the model path and must be attributed there |
| **Model calls and tokens** | Per question and per capability. Running the answer evaluation calls the generator for every question in every configuration and consumes quota — evaluation cost is real |
| **Operation calls** | Per question, split into productive and unproductive |
| **Cost per resolved question** | By capability, so an expensive capability can be judged against its value |
| **Partial completion** | Rate and cause distribution — coverage vs identity vs budget |
| **Failure recovery** | Behaviour when one operation errors mid-run: does the board survive with the gap named |
| **Deterministic provenance** | Same question twice ⇒ identical evidence items and identical record keys. Prose may vary; provenance may not |

---

## 20. G2A elicitation · G2B benchmark

Not built here. G2 splits into two stages, and the order matters: a benchmark written before
anyone has heard a real research question measures how well the system does what this document
assumed.

### G2A — research question and task elicitation

Purpose: find out whether transmission-structure researchers actually want chains *compared*,
or whether they simply read them. This is redundancy condition 4 from §6, and it is the one
assumption the whole wedge rests on.

> **Elicitation rule. Do not describe Musnad's capabilities before collecting questions.** Ask
> what they work on and what they do today. A participant told about chain comparison will
> produce chain-comparison questions, and the study will confirm itself. Capability discussion
> happens only after their own questions are recorded.

| Record per participant | Why it is needed |
|---|---|
| Role and field | Separates the primary user from the secondaries in §3 |
| A real task they are working on | Hypothetical tasks produce hypothetical capabilities |
| Current workflow, step by step | Shows where the manual cost actually sits |
| Pain point in their own words | Distinguishes a real cost from an inconvenience |
| Evidence they currently inspect | Tells us whether chains, matn, or rijal literature is the working material |
| Whether comparison or aggregation is genuinely useful to them | **The decisive question.** Recorded as their judgement, not inferred from enthusiasm |
| Terminology they use naturally | Drives the Arabic claim templates in §11 and the benchmark question wording |

| Outcome flag | Set when | Consequence |
|---|---|---|
| `PRODUCT_WEDGE_EVIDENCE = SUPPORTED` | Multiple independent target users provide real tasks and pain points that align with the structural comparison and investigation wedge *without having been coached toward those features* | C09–C13 proceed as specified. Still evidence, not proof |
| `PRODUCT_WEDGE_EVIDENCE = LIMITED` | Evidence exists but rests on too few users, mixed signals, or a narrow sample | **Engineering proceeds** — it is not blocked — but the product hypothesis remains provisional and is re-checked at G5. This is the expected outcome |
| `PRODUCT_WEDGE_EVIDENCE = NOT_SUPPORTED` | Elicited real tasks do not support the proposed wedge strongly enough | Reopen §6 positioning before G3 tools are built around the assumption. The structural capabilities may still be built; the positioning in §2 is what is wrong |

G2A does not block G2B indefinitely. If elicitation cannot be completed, the flag is set to
`LIMITED` and G2B proceeds on this document's assumptions — recorded as assumptions, not as
findings.

> **What a small elicitation study is, and is not.** This is **not market validation** and
> must never be described as one. A handful of interviews yields *problem evidence*, *task
> evidence* and *terminology evidence*. It does not establish product-market fit, demand, or
> willingness to adopt, and `SUPPORTED` means the evidence points that way — not that the
> wedge is proven.

### G2B — benchmark design and pilot

#### Strata

| ID | Stratum | Tests | Gold source |
|---|---|---|---|
| S1 | Direct matn QA | Grounded answering, citation correctness | **Newly written and corpus-verified before any tuning.** The 33-question set is carried forward only as a historical regression instrument, never extended into the holdout |
| S2 | Known-item lookup | Retrieval, with a *newly built* negative control of questions verified unretrievable at depth 50 | Corpus-verified. The 3 existing unretrievable questions stay in regression only — see §22 |
| S3 | Hadith → chains | Linkage traversal and chain reconstruction | Computed from the graph |
| S4 | Narrator name resolution | Correct candidates, ambiguity surfaced — **must include the 14 shared mapped short names** | Computed from `mis_narrator` |
| S5 | Narrator records and neighbours | Occurrences, scoped adjacency, high-degree handling | Computed from `transmission` |
| S6 | Multi-isnad comparison | Shared identities, shared transmissions, divergence points within one hadith | Computed; sample from the 3,586 multi-chain hadiths |
| S7 | Cross-hadith / cross-chain structure | Set comparison, pair relations, co-occurrence | Computed |
| S8 | Coverage abstention | The 444, the 733, and linked-without-chain records | Enumerable exactly |
| S9 | Identity-blocked abstention | Grading, biography, same-person, reliability — must abstain with the right layer | Policy, from §9 |
| S10 | Adversarial and misleading | Pressure toward rulings, authenticity, cross-book claims, dating, and absence-as-denial phrasing | Hand-written, expert-reviewed |

> **Why most gold labels are cheap.** For S3–S8 the graph *is* the ground truth for "as
> recorded in MIS", so gold evidence and gold provenance are computed, not annotated — the same
> way the 14,155 chains were validated. Human effort concentrates where it must: S1, S2, S9
> wording, and all of S10. This is what makes a benchmark of this scope feasible for one
> engineer.

#### Record schema

| Field | |
|---|---|
| `question` | Arabic, as a user would write it |
| `capability_id` | Expected capability from §8, or an expected §9 refusal |
| `stratum` | S1–S10 |
| `required_evidence` | Exact record keys that must appear — hadith numbers, `(book, hadith, sanad, position)`, narrator ids |
| `required_facts` | Derived values that must be correct — counts, shared sets, divergence positions |
| `allowed_operations` | The operations a correct trajectory may use; extras count against the unnecessary-call metric |
| `forbidden_claims` | Statements that fail the record outright, however good the rest is |
| `expected_status` | One of the seven statuses |
| `expected_missing_layer` | Required whenever the expected status is `ABSTAINED` or `PARTIAL` |
| `gold_provenance` | Linkage version and artifact SHA, graph hash, corpus hash at labelling time |
| `trajectory_contract` | S6–S10 only. **Not a single reference sequence.** For deterministic workflows an expected sequence is appropriate and is recorded as one. For C14 the contract is a constraint set — see below |

#### Trajectory contract — agentic capabilities

Scoring C14 against one gold operation sequence would define agency as conformity and fail the
very behaviour the capability exists to test. A trajectory is judged against constraints
instead:

| Field | Judged how |
|---|---|
| `required_evidence` | Every listed record key must appear in the final evidence board. This is the primary criterion |
| `required_operations` | Only operations that are *logically necessary* — a narrator-scoped result cannot exist without the lookup that produced it. Kept minimal by design |
| `allowed_operations` | The permitted set. Using fewer than permitted is not a fault |
| `forbidden_operations` | Hard failure on use — anything reaching a blocked layer, or any unbounded widening not in the contract |
| `order_constraints` | Dependency constraints only, expressed as "X must precede Y" — never a full ordering. Name resolution before any narrator-scoped operation is the canonical case |
| `argument_correctness` | Right entities and identifiers, including that resolved narrator ids match the intended narrator |
| `unnecessary_operation_count` | Calls producing no new evidence item. Counted and reported as cost, not scored as failure — this is the price of agency and must stay visible |
| `expected_final_status` | One of the seven statuses in §12 |
| `expected_termination_reason` | Evidence exhaustion, ambiguity halt, policy stop, or budget. Budget termination is scored as incomplete |

**An alternative trajectory that safely obtains the same required evidence must not fail
merely because its call order differs from a reference path.** Multiple valid trajectories are
expected, and a benchmark that cannot accommodate them is measuring imitation.

#### Statistical analysis contract

**Analysis is metric-specific.** A single named test does not cover the comparison, and the
fact that this repository has used McNemar before does not make McNemar the procedure here.

| Metric shape | Examples | Pre-registered procedure |
|---|---|---|
| **Paired binary** — each question succeeds or fails under each system | Per-question task success · correct abstention · hard-fail occurrence | A paired binary procedure such as **McNemar** may be appropriate, reported with the discordant-pair counts |
| **Paired count** | Evidence items returned · tool calls · model calls · unnecessary-operation count | **McNemar must not be used.** Pre-register a paired procedure suited to counts — paired bootstrap confidence intervals or a paired permutation test |
| **Paired continuous or bounded** | Latency · tokens · monetary cost · evidence completeness as a proportion | **McNemar must not be used.** Paired bootstrap CIs or a paired permutation test on the per-question differences |
| **Paired ordinal** | Graded quality judgements, if any are introduced | A justified paired ordinal procedure, pre-registered with the metric |

**The procedure is chosen with the metric, before the holdout is opened — never after
inspecting results.** Every reported comparison must carry: the metric definition, the sample
size and denominator, the raw paired outcomes, the effect size, and an uncertainty interval
where the metric admits one.

> **Significance is not the decision.** A statistically significant difference is **not
> sufficient** to justify C14. The decision weighs the task-quality delta, the evidence-quality
> delta, operational cost, latency, additional tool and model calls, and reliability and safety
> behaviour together. An agent that wins narrowly on quality while costing several times as
> much, or while committing any hard-fail, does not survive on a p-value.

#### Decision hierarchy — pre-registered in G2

G2 must fix this hierarchy *before* the holdout is opened. G1 deliberately sets no numbers:
every threshold is `TO_BE_CALIBRATED_AND_PRE_REGISTERED_IN_G2`.

| Tier | Contains | Role in the decision |
|---|---|---|
| **Primary** | The one or two metrics that determine whether C14 stays in V1 — expected to be evidence completeness and task success on the investigation strata | Decisive. Named, with a direction of improvement, before the run |
| **Secondary quality** | Grounded-claim rate · missing-layer accuracy · claim-type correctness · coverage disclosure · trajectory validity | Explanatory. May not be promoted to primary after results are seen |
| **Efficiency** | Latency · tokens · tool calls · model calls · cost per resolved question | Priced against the primary delta. A quality gain that is not worth its cost is not a reason to ship C14 |
| **Safety / hard-fail** | Guessing after `AMBIGUOUS` · producing an unsupported claim · silently dropping an excluded record · using a forbidden operation · presenting historical identity beyond the evidence contract | **Veto.** Counted and reported separately, never averaged into a score. A better mean does not offset a hard-fail |

> **Researcher degrees of freedom.** The holdout must not be mined for whichever metric makes
> the preferred architecture look best. Frozen before the run: **primary metrics · secondary
> metrics · direction of improvement · statistical procedures · the decision rule · the
> treatment of missing and partial results · the handling of hard safety failures.**
>
> The architecture decision may not be changed by selecting a different metric after results
> are observed. This needs no elaborate hypothesis-testing machinery — it needs the list above
> written down and dated before the run.

#### Splits and the freeze protocol

| Split | Purpose | Rules |
|---|---|---|
| **Pilot / dev** | Architecture, prompt and tool development for *both* the workflow baseline and the agent | Freely inspected and iterated on. Never reported as a result |
| **Regression** | Continuous regression testing across milestones | Run every milestone. Numbers move only when behaviour does, and each move is explained — the existing practice in this repository |
| **Final holdout** | The agent-vs-workflow decision, and nothing else | Newly constructed and sealed by hash *before* any workflow or agent tuning. Run **exactly once**, after all freezes below |

**One run, not two.** The holdout must **not** be run during workflow development and then run
again after the agent is built. Two runs against the same sealed set make the second a tuned
measurement, whatever the intention: the workflow's holdout result would inform agent design,
and the comparison would then measure that transfer rather than agency.

The order is fixed:

1. Pilot / dev — build and tune both systems.
2. Regression — run continuously throughout.
3. **Freeze the workflow implementation.**
4. **Freeze the agent implementation.**
5. **Freeze prompts and configuration.**
6. **Freeze the evaluation implementation** — judge and scoring code.
7. **Freeze the metric definitions.**
8. **Freeze the statistical plan.**
9. **Freeze the decision rule** — primary metrics, direction of improvement, hard-fail
   conditions.
10. **One blind paired evaluation** on the sealed holdout: every question through both
    systems, scored by the frozen evaluator.
11. The agent-vs-workflow decision, recorded once.
12. *Only then* may individual holdout failures be inspected.

**Permitted before the decision:** computing the aggregate results the decision needs. That is
the point of the run.

**Prohibited before the decision:** inspecting individual holdout examples; modifying either
system in response to holdout failures; modifying scoring in response to observed holdout
behaviour; and choosing a different metric or statistical procedure because the pre-registered
one gave an inconvenient answer.

If a system is modified after inspection, that work is `POST-HOLDOUT DEVELOPMENT`. It is
legitimate engineering and it is not a sealed result: any new confirmatory evaluation requires
a newly constructed and newly sealed set, reported under its own label, which never supersedes
the original.

Tuning on the final holdout would make the one number this project exists to produce — does
the agent beat the workflow — unfalsifiable. The repository already separates its blind
generated set from its hand-written reporting set for exactly this reason, and it also
documents what happens when the separation slips: 6 hand-written answers were edited after
seeing system output, and the numbers on that set are recorded as optimistic by an unmeasured
margin. The holdout exists so that the agent decision never acquires the same footnote.

Sizing follows the same one-sided logic as the identity protocol: a stratum must be large
enough that a per-stratum rate is interpretable on its own. A single question's difference on
a 27-item set is noise — that lesson is already recorded in this repository and must not be
relearned.

---

## 21. Tool implication map

Capability → required information operation. No APIs, no signatures, no schemas — this is the
input to G3.

| Operation | Serves | Status |
|---|---|---|
| Matn retrieval — hybrid, reranked | C01 C02 C12 C13 C14 | Built |
| Grounded generation with citation enforcement | C01 C14 | Built |
| Local hadith read + linkage status | C03 C15 | Built |
| Local → MIS resolution through the frozen linkage | C03 C04 C12 C13 | Built |
| Isnads of a hadith, kept separate | C04 C09 | Built |
| Ordered chain reconstruction | C04 C08 C09 C12 | Built |
| Narrator read by id | C05 and every narrator path | Built |
| Narrator occurrences | C07 C10 C11 C13 | Built |
| Chain-scoped predecessors / successors | C08 C10 | Built |
| MIS → local reverse resolution | C07 C15 | Built |
| Linkage coverage figures | C15 | Built |
| Retrieval result → sanad context adapter | C01 C12 C13 | Built |
| **Narrator name → candidate ids, with ambiguity** | C06 C10 C11 C13 C14 — and every narrator entry point | **Missing — keystone** |
| Chain-set comparison — shared ids, shared adjacent pairs, divergence and convergence | C09 C12 C14 | Missing |
| Narrator pair relation across chains, with the widening ladder | C10 C14 | Missing |
| Narrator co-occurrence aggregation | C11 C14 | Missing |
| Batched context over a retrieval result set, with exclusions enumerated | C12 C13 C14 | Missing |
| Matn text by corpus id | C03 and every hadith card | **Verify** — the graph stores no local text by design; confirm the retrieval layer exposes a direct id → matn read |
| Capability / policy lookup for refusals | C14 C15 | Missing — trivial |

Twelve operations exist. Six must be built, one verified. All six new ones are deterministic;
none needs a model.
---

## 22. Data and coverage limitations

Each limitation with its consequence in every mode. None may be hidden.

| Limitation | Ask | Explore | Investigate | Benchmark |
|---|---|---|---|---|
| **444 local hadiths with no accepted MIS link (5.95%)** | A cited hadith may have no chain slot; the answer stands, the slot is named | Returns the local record with `NO_ACCEPTED_MIS_LINK` | Forces `PARTIAL` with ids listed; never silently dropped | S8, enumerable exactly |
| **733 MIS records with no accepted local link (9.46%)** | Invisible — Ask starts locally | Occurrence rows resolve to a MIS record with no local hadith; labelled, not hidden | Structural results may reference hadiths with no readable matn | S8 reverse direction |
| **MIS narrator ids are operational, built with fuzzy and manual mapping; 14 mapped short names shared** | Not surfaced | Every narrator card carries the identity qualifier | Every shared-narrator claim is a MIS-assignment claim; comparisons touching a shared short name are flagged identity-sensitive | S4 dedicated stratum |
| **Linkage precision unknown — 0 of 361 sampled rows human-labelled** | Chain attachment is provisional in principle even where deterministic | Link status, version and SHA travel with every crossing | Cross-layer claims inherit this; the board records the linkage version | Gold provenance records the SHA |
| **Itqan identity not validated** | — | — | — | S9, as a permanent refusal class |
| **Production reranked hit@5 = 22/27; 3 questions missed by every retriever at depth ≤50** | The measured event: with reranking the gold hadith reached the supplied context for 22 of 27 answerable questions, and for 5 of 27 it did not (20 of 27 without reranking) | Unaffected — no retrieval | Retrieval-selected sets are biased by this before any structure is computed | S2 rebuilds the negative control rather than reusing the old questions |
| **Wrong in-context citation: 3 of 30 (10%) with reranking, 4 of 30 (13%) without** | The dominant Ask failure; enforcement does not prevent it | — | A wrong seed propagates into every downstream structural claim | S1 and S7 must test propagation |
| **2 of the 3 known-unretrievable questions had their ground truth edited after system output was seen** — 7355 added to «شرط كمال الإيمان», 10762 removed from «حكم الغش في البيع» | These are the hardest cases and the least blind ones; they cannot serve as a clean negative control | Unaffected | Unaffected | **Found during final review.** S2 must build a new unretrievable control; the original 3 stay in regression only, carrying the non-blind flag |
| **Single collection** | No cross-book statement, including the inverse | Same | Investigation scope is one book, stated in the board | S10 adversarial |
| **80 narrators with `NotMapped` generation; 43 recorded later→earlier steps** | — | Displayed verbatim, never inferred | No contemporaneity or ordering inference is permitted from generation | S5 |

---

## 23. Risk register

| Risk | P | Impact | Mitigation | Phase |
|---|---|---|---|---|
| **False authority** — structural output read as an authenticity signal | High | Severe | Claim policy at the point of display, not in help; S10 adversarial stratum; U3/U8 refusals | G1 spec, G6 interface |
| **Historical identity conflation** — MIS id read as a person | High | Severe | Mandatory qualifier on every cross-chain claim; identity-sensitive flag on shared short names | G2 wording, G3 output |
| **Ambiguous narrator names** — wrong narrator silently selected | High | High | C06 never auto-selects; `AMBIGUOUS` halts downstream work; a guess is a hard benchmark failure | G2, G3 |
| **Agent overuse** — agency where a workflow suffices | High | Medium | 14 of 15 capabilities are workflows by decision; C14 must beat a baseline or be deleted | G4 |
| **Partial coverage passing as complete** | High | High | `PARTIAL` mandatory with ids enumerated; silent exclusion is a hard failure regardless of answer quality | G2, G3 |
| **Scope creep** — grading and takhrij pull constantly | High | High | Freeze rule in §17; the negative matrix is a contract, not a backlog | All |
| **Benchmark overfitting and post-hoc metric selection** | Medium | Severe | Holdout sealed before tuning; nine freezes including the statistical plan and decision rule; **one** blind paired run; no failure inspection before the decision; any later run relabelled `POST-HOLDOUT DEVELOPMENT` | G2, G4 |
| **Evaluation leakage** — gold computed by the code under test | Medium | Severe | Gold generated from frozen artifacts by a separate path and hash-pinned, mirroring the existing docs-integrity check | G2 |
| **Provenance loss in composition** | Medium | High | Strictest-type inheritance; export is the internal object, not prose; a claim that cannot be opened is not displayed | G3, G5 |
| **Token and latency explosion in C14** | Medium | Medium | Hard step budget; evidence-gain-per-step measured; cost attributed per capability and priced against the primary delta | G4 |
| **Interface hiding uncertainty** | Medium | High | Coverage shown at equal weight; qualifiers survive layout changes; no confidence scores on deterministic facts | G6 |
| **Religious-domain trust expectations** — users expect rulings | High | Medium | Primary user chosen to avoid it; standing disclosure; refusal with redirect and no partial answer | G1, G6 |
| **Redundancy** — the structural wedge is published elsewhere | Medium | High | Redundancy conditions named in §6 and re-checked at G5 rather than argued | G5 |
| **MIS is not verified against the classical literature** | Certain | Medium | Every claim scoped "as recorded in MIS"; no capability asserts otherwise; expert review is a V2 track | Permanent |

---

## 24. Architecture decision records

### ADR-001 · Hybrid workflow + agent, not everything-agentic

- **Context.** Fifteen capabilities. Most are keyed reads or set arithmetic over a graph of at
  most 8 edges depth, running sub-millisecond. One has an operation sequence that cannot be
  written down in advance.
- **Decision.** Fourteen workflows, one agent — and the agent must beat a workflow baseline in
  a single blind paired evaluation on a sealed holdout, or be removed. `HYBRID` is rejected as
  an orchestration class: a capability spanning matn and sanad evidence is described as
  `CROSS_LAYER`, which says nothing about how it is orchestrated.
- **Alternatives.** *Everything agentic:* rejected — it would make deterministic, checkable
  operations unpredictable and expensive for no measured gain. *Everything workflow:* rejected,
  but weakly — it remains the fallback if G4 finds no delta. *Router-first:* rejected — a router
  over undefined contracts is a classifier with nothing to classify.
- **Consequences.** Most of V1 is cheap, testable and fast. The agent claim becomes
  falsifiable, which is the point. A router is needed eventually and is deferred to V1.5.

### ADR-002 · Structure is computed, never reasoned over by the model

- **Context.** Chains are ordered, bounded and complete: 14,155 reconstruct exactly, positions
  are contiguous, 0 broken transitions. Comparison is set and sequence arithmetic.
- **Decision.** Every structural fact comes from a deterministic operation. The model may
  select operations and render results; it may never derive a shared narrator, a divergence
  point or a count.
- **Alternatives.** *Chains in the context window:* rejected — it converts a checkable
  computation into an unverifiable claim, and comparison errors would be invisible.
  *Model-verified structure:* rejected — verifying deterministic output with a stochastic
  process is strictly worse than recomputing it.
- **Consequences.** Structural claims are reproducible and gold labels are computable, which
  is what makes S3–S8 affordable. The cost is that six deterministic operations must be built
  before C09–C14 exist at all.

### ADR-003 · Historical narrator identity stays outside V1

- **Context.** 2,001 of 2,092 narrators have no accepted frozen canonical/alias resolution.
  Candidates are not the shortage — 1,207 carry an exact documented-short-name candidate, of
  which 317 have several — and the unmatched population is explicitly recorded as not
  classifiable as absent from Itqan. What is missing is adjudication: the 40-case calibration
  found no identity-bearing evidence in Itqan v1.20 and no positive anchor. Externally, a 2026
  multi-signal pipeline over a much larger corpus linked 51.1% of names in its first phase with
  medium confidence dominating — published identity graphs ship at provisional quality.
- **Decision.** The gate stays closed. No `HistoricalNarrator`, no gradings, no candidate
  identity surfaced as identity. V1 is designed so that no supported capability needs it.
- **Alternatives.** *Ship the 81 provisional links as candidates:* rejected — a candidate shown
  to a user becomes a fact told to a third party, and the protocol's own rule is that a
  provisional link may never be presented as a biography. *Match the published pipelines'
  confidence tiers:* rejected — matching the state of the art here means adopting its error
  rate in a domain where a wrong narrator identity is a serious claim about a real person.
- **Consequences.** The most-wanted feature is permanently absent from V1, and Musnad cannot
  compete with incumbents on their busiest surface. In exchange every claim it does make is
  defensible, and the gate can open later on adjudicated evidence without retracting anything.

### ADR-004 · Evidence and provenance are product output, not logging

- **Context.** Every graph result already carries linkage status, version, artifact SHA and a
  verbatim basis string. Survey work on agent provenance notes that attribution benchmarks link
  answers to sources but rarely capture how tool calls shaped the claim.
- **Decision.** Provenance is user-visible and exportable. The evidence board is the
  Investigate output object, not a debug view.
- **Alternatives.** *Provenance in logs:* rejected — the primary user must cite what the system
  did. *Prose with footnotes:* rejected — it cannot express an evidence gap, which is often the
  finding.
- **Consequences.** Output is denser and less conversational; that is the intended trade. It
  also makes agent evaluation possible at all, since trajectory and evidence gain are readable
  from the board.

### ADR-005 · V1 is not a hadith-authentication authority

- **Context.** An authenticity verdict needs narrator reliability, which needs identity, which
  is blocked. Institutional positions hold rulings with qualified scholars; assessments of AI
  systems in this domain report misattributed verses and hadith.
- **Decision.** No authenticity verdict, no ruling, no grading, and no structural output framed
  as evidence for either. Enforced by the negative matrix and the claim policy, not by a
  disclaimer.
- **Alternatives.** *Report MIS-derived signals with caveats:* rejected — caveats do not survive
  screenshots, and the signal would be read as a verdict. *Surface incumbents' verdicts:*
  rejected — importing a claim Musnad cannot evidence, with someone else's provenance.
- **Consequences.** A smaller product with a narrower audience, and a defensible one.

### ADR-006 · One status taxonomy across every layer

- **Context.** The code already distinguishes four abstention states and names the missing
  layer rather than returning empty. Tools, API, agent state, evaluation and monitoring would
  otherwise each invent their own words.
- **Decision.** Seven statuses plus a separate `missing_layer` axis, lifted from the vocabulary
  already in the code. `ABSTAINED` and `PARTIAL` are not failures.
- **Alternatives.** *Per-layer vocabularies:* rejected — the same condition would carry three
  names and be uncountable. *One flat list of every combination:* rejected — thirty statuses
  nobody can use correctly.
- **Consequences.** Metrics are comparable across capabilities, and correct abstention can be
  rewarded rather than penalised by construction.

### ADR-007 · Narrator name resolution is a capability, and ambiguity is its output

- **Context.** Every narrator function in `sanad_graph.py` takes an id. Nothing maps a name to
  one. Users type names, and 14 mapped short names are shared by more than one id.
- **Decision.** C06 is a first-class V1 capability that never auto-selects. More than one
  candidate returns `AMBIGUOUS` and halts downstream work until the user chooses.
- **Alternatives.** *Best-match selection:* rejected — a silent wrong pick corrupts every
  downstream structural claim while looking like a clean answer, which is the worst available
  failure mode. *Model-based disambiguation:* rejected — it would place a model inside an
  identity decision the project has spent four audits refusing to make.
- **Consequences.** More user interaction and more halted runs. In exchange the highest-risk
  failure in the structural layer becomes visible rather than silent.

### ADR-008 · Statistical analysis is metric-specific and pre-registered

- **Context.** The agent-vs-workflow comparison spans metrics of different shapes: binary
  per-question success, counts of evidence items and tool calls, and continuous latency, token
  and cost measures. A single named test cannot cover them, and prior use of McNemar in this
  repository was for a paired binary retrieval comparison.
- **Decision.** Each metric carries its own pre-registered paired procedure. McNemar may be
  used for paired binary outcomes only; counts, continuous, bounded and ordinal metrics use
  paired bootstrap confidence intervals, paired permutation procedures, or another justified
  paired method registered with the metric. Every comparison reports metric definition, sample
  size and denominator, raw paired outcomes, effect size and uncertainty. Significance alone
  never justifies the agent.
- **Alternatives.** *One test for everything:* rejected as statistically wrong — McNemar on a
  count or a latency is not a conservative approximation, it is a category error. *Choose the
  test after seeing the data:* rejected — that is the degrees-of-freedom failure the freeze
  protocol exists to prevent.
- **Consequences.** G2 must do more work before the holdout opens: naming metrics, attaching
  procedures, and fixing a decision hierarchy with safety vetoes. In exchange the agent decision
  is one honest number rather than a defensible-sounding one.

---

## 25. Red-team review

Nine attacks on this specification. Five changed it.

| Criticism | Response | Outcome |
|---|---|---|
| **1. Redundant with existing hadith search.** Incumbents cover more collections and already show sanad, gradings and biography | Correct on coverage, gradings and biography — and Musnad loses all three outright. What it does not concede is computation over sets of chains, which the surveyed platforms render but do not compute | **Spec changed** — the wedge was narrowed to structural comparison, provenance and diagnostic abstention; takhrij and grading parity dropped explicitly, not deferred |
| **2. Not truly agentic.** The brief's investigation examples are fixed pipelines | Sustained. On inspection, the narrator-relation example is a fixed ladder with early exit and the topic-plus-narrator example is a pipeline with fan-out. Fan-out is a loop | **Spec changed** — C10, C12 and C13 all reclassified to workflow, agency confined to C14 and made deletable at G4 |
| **3. Structural findings are findings about MIS, not history.** A "shared narrator" is a shared MIS id, produced by fuzzy and manual mapping | Sustained, and stronger than the brief stated. The same identity uncertainty that blocks gradings partially undermines cross-chain identity claims | **Spec changed** — mandatory MIS-assignment wording on C09–C12, an identity-sensitive flag for shared short names, and a dedicated S4 stratum |
| **4. Structural comparison is impossible to evaluate** without expert gold labels | Not sustained. For "as recorded in MIS" the graph is the ground truth, so gold evidence for S3–S8 is computed rather than annotated — the same method that validated all 14,155 chains. Human labelling concentrates on wording and adversarial cases | **Rebutted** — and it became the reason a benchmark of this scope is feasible for one engineer |
| **5. Too research-heavy.** Evidence boards and provenance footers will exhaust any user | Partly sustained. The primary user needs the board; nobody needs a generated narrative report, which invites over-reading | **Spec changed** — export reduced to lossless JSON plus a Markdown rendering; polished report generation moved out of V1 |
| **6. Unsafe claims.** A structural comparison will be read as an authenticity argument | Sustained as a permanent risk, not a fixable defect. Mitigation is display-level and testable | **Spec changed** — U8 added for common-link dating, and S10 made a required stratum rather than an optional one |
| **7. Blocked by identity.** Without narrator identity the product answers nothing users want | Partly sustained — for the general reader it is decisive, which is exactly why that group is not the target. For the structural researcher, chain structure was measured to be independent of person identity | **Rebutted** — with the audience narrowed rather than the claim widened |
| **8. Not worth deploying.** A single-book research instrument does not need production infrastructure | Largely sustained for V1. Nothing here requires scale: 13.8 MB of graph, sub-millisecond queries, one collection | **Spec changed** — the two are now separated: **V1 functional scope** is a read-only single-tenant surface, while **production-shaped deployment stays on the project engineering roadmap**. The criticism defeats putting multi-tenant infrastructure in V1; it does not defeat deploying the project |
| **9. The wedge is a dataset property, not a product.** Anyone with the workbooks and Cypher can do this | Partly sustained and named as a redundancy condition rather than argued away. The residual differentiation is the join to a retrievable corpus, the abstention discipline, and the measurement — none of which the raw dataset provides | **Conceded in part** — listed in §6 as redundancy condition 1 and re-checked at G5 |

> **The criticism with no answer yet.** Redundancy condition 4 — that researchers may simply
> read the chains rather than want them compared — cannot be settled by argument. At this corpus
> size, reading 24 chains by hand is tedious but possible. G2A now exists to test it by uncoached
> elicitation, and its outcome is recorded as an explicit flag rather than assumed. If only one
> participant is reachable the flag reads `LIMITED` and engineering continues — but the wedge is
> then documented as untested, not as established.

---

## 26. Open questions

| Question | Why it is open | Resolve by |
|---|---|---|
| Do researchers want computed structural comparison, or is reading chains enough? | No user has been observed. The wedge rests on this | **G2A** — uncoached elicitation from multiple users where reachable; otherwise recorded as `PRODUCT_WEDGE_EVIDENCE = LIMITED` |
| Which name form should C06 match against? | Full and mapped names are not interchangeable: only 57 pairs are equal under the narrow normaliser, and the mapped form has fewer tokens in 1,500 rows | G2, before S4 is labelled |
| What does the user do with an `AMBIGUOUS` result on a name they cannot disambiguate? | Halting is safe but may be a dead end for a user who only knows the short form | G2 pilot |
| Does a wrong in-context citation propagate into structural conclusions? | Measured at 3/30 for Ask; never measured downstream | G2 S7 |
| Is one bounded reformulation right for C13? | Carried from the CRAG result on single-hop matn QA; it may not transfer to constrained retrieval | G4 |
| What step budget makes C14 meaningful without being unbounded? | No data. Too low makes the agent a workflow; too high makes it unevaluable | G4, calibrated on the dev split |
| How is an investigation over the 444 presented so partiality is unmissable? | An interface question with a correctness consequence | G6 |
| Should Explore be usable without any model at all, as a public read-only surface? | It is the only mode with no generative hallucination path, which makes it the safest to expose first — subject to source-data and implementation integrity, which a public surface raises the stakes on | G6 |

---

## 27. Final agent justification

**Decision: AGENT JUSTIFIED ONLY FOR SPECIFIC TASKS.** Conditional on G4 — insufficient
evidence today.

The answer is not "yes" because the project intends to be agentic, and not "no" because most
capabilities turned out deterministic. It is conditional, and the condition is measurable.

**Genuinely justifies agency — C14 only.** An open structural question where a narrator
discovered at step two determines the operations at step three, where an empty rung changes
what is worth asking, and where stopping is a sufficiency judgement rather than a counter. No
fixed ladder covers that space, and enumerating the branches would produce a tree nobody could
test.

**Does not justify agency.**

- **C01.** The nearest agentic pattern — self-grading with one rewrite — was built here and
  measured no gain.
- **C09, C10, C11.** Set arithmetic and a fixed ladder with early exit.
- **C12, C13.** Fixed pipelines. Unknown set size is a loop bound; a single predetermined
  rewrite branch is fixed branching. `CROSS_LAYER` evidence, workflow execution.
- **Everything else.** Keyed reads.

Reclassified during final review: C12 and C13 were previously called hybrid. `HYBRID` is
rejected as an orchestration class — combining matn retrieval with graph operations describes
the *evidence pipeline*, and both capabilities run entirely through predefined code paths.

**What G4 and G5 must prove empirically.**

1. **The delta exists on the pre-registered primary metric.** Measured in a single blind paired
   run on the sealed holdout, analysed by the procedure registered with that metric, and
   reported with effect size, uncertainty and the raw paired outcomes. No delta ⇒ delete C14 and
   move its questions to `UNSUPPORTED`.
2. **The delta is worth its cost.** Measured in operations, tokens, latency and money per
   additional evidence item. Significance alone does not carry this point.
3. **The trajectory is real agency.** If the agent's operation sequences are indistinguishable
   from the frozen baseline's across the holdout, it is a workflow with an expensive dispatcher —
   judged on the distribution of trajectories, not on divergence from any single reference path.
4. **Bounded behaviour holds.** Termination by evidence exhaustion rather than budget; zero
   guesses on `AMBIGUOUS`; no unevidenced claim on any board. These are veto conditions, not
   score contributions.

All four are falsifiable, and deleting the agent is an acceptable outcome of this project.

---

## 28. G1 gate decision

**PASS.** Four carry-forward conditions, all inputs to G2. Repository state unchanged — no
code, data, schema, label or artifact touched.

The phase produced what it was for: a capability taxonomy grounded in measured evidence, a
negative matrix that names missing evidence rather than policy preference, one status
vocabulary, a claim policy in the product's own language, and an agent decision that is
falsifiable rather than assumed.

It passes because the three things that would have forced `NEEDS_REPAIR` did not occur. The
foundation numbers all verified against the repository. The identity gate held — no supported
capability requires it to open. And the agent question resolved into a testable claim rather
than an assumption.

The four conditions in §1.2 are inputs to G2, not defects here: the name-resolution gap is a
build task, the MIS-identity wording is a benchmark instruction, the linkage-precision
qualifier is an evidence-contract term, and the agent's falsifiability is a benchmark design
requirement.

### Final review — version 1.1

Eleven specification repairs were applied and re-verified against the repository; every
affected number was re-read from `EXPERIMENTS.md` rather than adjusted. Three contradictions
were found and corrected — one in the phase brief, two inside version 1.0 of this document.
None of the repairs required a foundation measurement to change, and none reopened the
entity-resolution gate.

The gate holds at **PASS**. Several of the repairs make the contract stricter rather than
looser — fourteen of fifteen capabilities are now workflows, the holdout runs once instead of
twice, the legacy evaluation set is demoted from holdout material to regression material, and
the statistical plan is fixed per metric before any result is seen. A specification that got
narrower under review is more likely to survive contact with G2 than one that got wider.

---

## 29. Exact input to Phase G2

G2 is **G2A Research Task Elicitation**, then **G2B Benchmark Design + Pilot**. It receives:

| Input | From | Used for |
|---|---|---|
| Capability taxonomy C01–C15 with evidence pipelines and execution classes | §8, §13 | Deciding what each stratum tests and which trajectories are correct |
| Negative matrix U1–U8 with missing evidence per entry | §9 | Building S9 and S10, and the expected refusal per record |
| Evidence contracts E1–E3 | §10 | `required_evidence` and `gold_provenance` fields |
| Claim types with Arabic templates | §11 | Scoring claim-type correctness and absence wording |
| Seven statuses plus the `missing_layer` vocabulary | §12 | `expected_status`, `expected_missing_layer`, and metric definitions that do not treat abstention as failure |
| G2A elicitation contract and the `PRODUCT_WEDGE_EVIDENCE` flag | §20 | Running elicitation before the benchmark is written, and recording the outcome honestly |
| Ten strata with gold sources | §20 | The benchmark's own structure |
| Record schema | §20 | Labelling format |
| Trajectory contract for agentic capabilities | §20 | Scoring C14 without demanding one reference path |
| Statistical analysis contract and decision hierarchy | §20, ADR-008 | Attaching a procedure to each metric and fixing the decision rule before the run |
| Freeze protocol and the one-run holdout rule | §20 | Sealing the set before tuning; ordering the freezes |
| Tool implication map — 12 built, 6 missing, 1 to verify | §21 | Knowing which strata cannot be run until G3 builds their operations |
| Metric list with the existing measured baselines | §19 | Regression continuity with `EXPERIMENTS.md` |
| Four carry-forward conditions | §1.2 | G2 exit criteria |

### What G2 must produce

1. **G2A first:** uncoached elicitation with the seven recorded fields, and the
   `PRODUCT_WEDGE_EVIDENCE` flag set to `SUPPORTED`, `LIMITED` or `NOT_SUPPORTED`.
2. The benchmark specification: strata, sizes, record schema, trajectory contracts, labelling
   protocol, and the sealing procedure — with the holdout newly built and sealed before any
   tuning.
3. **The pre-registered decision package:** primary, secondary, efficiency and safety metrics;
   direction of improvement; the statistical procedure attached to each metric; the decision
   rule; the treatment of missing and partial results; the handling of hard-fails. Written down
   and dated before the holdout is opened.
4. A pilot set on the dev split, large enough to show where this contract is unbuildable.
5. A resolution of open question 2 — which name form C06 matches — before S4 is labelled.
6. At least one stratum's worth of questions traceable to G2A elicitation, or an explicit
   `LIMITED` flag recording that the wedge rests on unvalidated assumptions.
7. A gold-generation path independent of the code under test, hash-pinned like every other
   artifact in this repository.

### What G2 must not do

Build tools, write agent code, design LangGraph state, write prompts, touch retrieval or graph
data, attach Itqan, create `HistoricalNarrator`, or run anything against the final holdout. Nor
may it coach elicitation participants toward Musnad's capabilities before recording their own
questions, or extend the 33-question hand-written set into the holdout.

---

*End of frozen contract. G1 is closed. The next phase is G2A.*
