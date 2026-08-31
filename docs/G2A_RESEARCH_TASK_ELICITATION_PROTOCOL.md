# MUSNAD — G2A Research Task Elicitation Protocol

| | |
|---|---|
| **Project** | MUSNAD |
| **Phase** | **G2A — Research Task Elicitation** |
| **Type** | **Research protocol** — instrument only, no findings |
| **Status** | **READY_FOR_ELICITATION** |
| **G1 baseline** | `musnad-g1-v1.1` — commit `a2da81ad0f4c327ca71d3d5a4ef4d19233ea0ee6` |
| **Product evidence** | **`PRODUCT_WEDGE_EVIDENCE = NOT_YET_ASSESSED`** |
| **C14 evidence** | **`C14_USER_TASK_EVIDENCE = NOT_YET_ASSESSED`** |
| **Participants run** | **0** |
| **Authority** | Subordinate to `docs/G1_PRODUCT_RESEARCH_CONTRACT.md`. Where the two disagree, G1 wins |

**This document contains no participant data.** No interview has been conducted, no
participant has been recruited, and no task record has been filled. Every template below is
blank by design. Producing this protocol changed no code, no dataset, no schema, no evaluation
label, no prompt and no runtime behaviour, and did not edit the frozen G1 contract.

**Protocol-ready is not elicitation-complete.** G2A closes only when real participants have
been interviewed under this protocol and the synthesis in §17 has been produced, or when §22
records an explicit, dated decision that elicitation could not be completed.

---

## 0. What this phase is, and what it is not

| G2A is | G2A is not |
|---|---|
| Problem evidence — do the pains this product assumes actually occur | Market validation, demand estimation, or product–market fit |
| Task evidence — what concrete operations real researchers perform | A feature-preference survey |
| Workflow evidence — where the manual cost actually sits | A Musnad demo, or any demo |
| Terminology evidence — the words participants use unprompted | An agent evaluation |
| A falsification attempt against Musnad's own wedge | Benchmark construction — that is G2B |

G2A runs **before** benchmark construction, tool design, LangGraph, agent implementation, UI,
production API and deployment. G1 §20 fixes this order for a stated reason: *a benchmark
written before anyone has heard a real research question measures how well the system does
what the contract assumed.*

> **What a small elicitation study can and cannot yield.** Carried in force from G1 §20: a
> handful of interviews yields *problem evidence*, *task evidence* and *terminology evidence*.
> It does not establish product–market fit, demand, or willingness to adopt. `SUPPORTED` means
> the evidence points that way — not that the wedge is proven. The words `VALIDATED`,
> `MARKET_VALIDATED` and `PRODUCT-MARKET-FIT` are prohibited in every G2A output.

---

## 1. Objective and hypotheses under test

### 1.1 Primary research question

> **What real research tasks do target users perform around hadith text, isnad, narrator
> occurrences, and the comparison of transmission structure — and where, if anywhere, does
> manual inspection become difficult enough that deterministic structural computation or
> multi-step investigation would provide meaningful value?**

The second clause is the one that decides. The first clause is answerable from the literature;
only elicitation answers the second.

### 1.2 The hypotheses, written so a real task can refute them

G1 §6 defines the wedge in three parts and names, in advance, four conditions that would make
Musnad redundant. Condition 4 is this study.

| # | Hypothesis under test | Refuted by | G1 anchor |
|---|---|---|---|
| **H1** | Target users treat chains as **objects to compare**, not only as strings to read | Real tasks in which chains are read individually and never set against one another; or comparison that does occur but at a scale handled comfortably by eye | §6 part 1 · §6 redundancy 4 |
| **H2** | The **join between matn and structure** is a real cost users pay today | Users who never cross that boundary; users for whom text and chain already arrive together; users whose working material is rijal literature rather than chains | §6 part 2 · §3 |
| **H3** | **Named absence is useful output** — knowing *which layer* is missing changes what the user does next | Users who treat an empty result as an empty result and move on; users for whom partial coverage disqualifies a tool outright rather than informing them | §6 part 3 · §12 |
| **H4** | **Provenance at record granularity** is needed — record coordinates, versions, hashes — rather than a prose summary | Users who cite the printed edition and never a dataset; users who would never reproduce or audit a structural result | §2 · §10 |
| **H5** | Some real task has the property that **the next useful operation depends on an intermediate observation** and cannot be enumerated beforehand | Every elicited task decomposing into a sequence writable in advance, or covered by a bounded enumerable workflow on the §11.2 check | §13 · §14 · §27 |
| **H6** | Restricting V1 to **one collection** still leaves a useful task surface | Tasks inherently cross-collection at their core, such that a one-book instrument answers nothing the researcher needed | §4 · §9 U5 · §22 |

**H1 is load-bearing.** H2–H4 qualify the wedge. H5 is C14's precondition, not C14's proof.
H6 is a scope check G1 §22 already flags as a live limitation.

### 1.3 What a null result means

Refuting H1 does not mean the structural capabilities are wrong to build. It means the
**positioning** in G1 §2 is wrong, and G1 §6 must be reopened before G3 builds tools around the
assumption. That distinction is G1's own — §20, `NOT_SUPPORTED` row — and §14 preserves it
exactly.

---

## 2. Relationship to the frozen G1 contract

G1 §20 specifies seven fields per participant. This protocol records a superset. The mapping
below is the compliance check: **every G1 field has a home here, and nothing here contradicts
G1.**

| G1 §20 required record | Where it lives in this protocol |
|---|---|
| Role and field | Screener S1–S3 · `participant_role` · `participant_field` |
| A real task they are working on | Stage B · `task_description_verbatim` · `task_recency` |
| Current workflow, step by step | Stage C · `current_workflow_steps` |
| Pain point in their own words | Stages E–F · `pain_points` · `pain_severity` |
| Evidence they currently inspect | Stage D · `evidence_inspected` · `resources_used` |
| Whether comparison or aggregation is genuinely useful to them — *the decisive question* | Stage H probe **CP1** · `concept_reaction` · recorded as **their judgement**, never inferred from enthusiasm (§12) |
| Terminology they use naturally | Stage I · `natural_terminology` (§13) |

**Two G1 constraints bind this document and are repeated because they are easy to break under
interview pressure:**

1. **G1 §20 elicitation rule.** Do not describe Musnad's capabilities before collecting the
   participant's own tasks. A participant told about chain comparison will produce
   chain-comparison questions and the study will confirm itself. Operationalised in §6.
2. **G1 §4 identity gate.** MIS narrator identity is *operational inside MIS*, never a
   canonical historical-person identity. No recruitment message, consent script, probe or
   summary may imply Musnad supports narrator grading, historical identity, authenticity
   verdicts, fatwa, cross-book takhrij, temporal or geographic reasoning, common-link dating,
   or teacher/student biography. Those are G1 §9 U1–U8 and they stay closed.

**Not reopened by this document:** the G1 capability taxonomy (G1 §8), negative matrix (G1 §9),
evidence contracts (G1 §10), claim language (G1 §11), status taxonomy (G1 §12),
workflow-vs-agent rules (G1 §13), agent mission (G1 §14) and scope freeze (G1 §17). G2A *tests*
the positioning in **G1 §2 and G1 §6**; it does not amend them.

> **Reference convention for the rest of this document.** A bare `§N` means a section of *this*
> protocol. A section of the frozen contract is always written `G1 §N`. The one exception is the
> **G1 anchor** column in the table above, whose header carries the qualifier.

---

## 3. Methodology sources reviewed

Reviewed 2026-08-31, with what each contributes, so that method, design choice and
Musnad-specific inference stay separable. §3.2 makes that separation binding.

| Source | What it contributes here |
|---|---|
| Beyer & Holtzblatt, *Contextual Inquiry* / *Contextual Design*; NN/g's summary | The **master–apprentice stance** and four principles — context, partnership, interpretation, focus. The interviewer is the apprentice; the participant is the expert on their own work. Drives Stage C and interviewer rules IR-03, IR-07 |
| Flanagan, *The Critical Incident Technique* (1954); NN/g's UX treatment | Collect **specific incidents, not generalisations** — "tell me about a particular time when…". Also its warnings: recall bias, over-representation of extreme events, leading wording. Drives Stage B and the §8 specificity test |
| Fitzpatrick, *The Mom Test* | Talk about their life, not your idea; ask about **specifics in the past**, not opinions about the future; talk less. Also the failure mode where a participant protects the interviewer's feelings. Drives §6 and the §7.10 prohibited list |
| Moesta & Spiek, JTBD **switch / timeline interview**; Klement's framing | Reconstructing a **timeline around a struggling moment** — first thought, passive looking, active looking, deciding. Drives Stage B's trigger question and Stage E's workaround probes. *Adapted, not adopted:* there is no purchase event here, so the "switch" is reframed as the moment the participant's existing method stopped being sufficient |
| Malterud, Siersma & Guassora, *Sample Size in Qualitative Interview Studies: Guided by Information Power* (2016) | Sample size is **information sufficiency, not headcount**, across five dimensions — study aim, sample specificity, established theory, quality of dialogue, analysis strategy — and a dense, highly specific sample needs fewer participants. Drives §4.4 |
| NN/g on **leading questions** and on **confirmation bias in UX** | Leading questions embed the desired answer, and the interviewer is read as the authority in the room, so participants mimic rather than disagree. Mitigations adopted: neutral open wording, a review pass over the wording before use, and deliberately including questions designed to *disprove* the hypothesis. Drives §6, §7.10, §16 |

### 3.1 Two methodology facts that changed this design

- **Critical-incident recall is biased toward extremes.** NN/g warns the technique
  under-represents routine work. Musnad's wedge is a claim about *routine difficulty*, not
  about disasters — so Stage B asks for the **most recent** relevant task rather than the most
  memorable one, and Stage E asks separately what was *tedious*, not only what *failed*.
- **A highly specific sample lowers the required N.** This is what makes a 3–5 participant
  study defensible at all — and it is also why recruiting is hard. §4.4 spends that argument
  honestly rather than using it to excuse an N of 1.

### 3.2 The four evidence classes — binding on every G2A output

**Four classes, ranked. They are never merged in a table, a count, or a sentence**, and the rank
decides what each may be used to conclude.

| Rank | Class | Means | Example |
|---|---|---|---|
| **1** | `FIRST_HAND_TASK_EVIDENCE` | A task the participant **personally performed or directly participated in**, tied to a specific occasion | "I opened three chains for that hadith and wrote the repeated names on paper" |
| **2** | `PROXY_CONTEXT_EVIDENCE` | An account of work **someone else** did — the profile B3 lecturer/supervisor case (§4.2), or a participant describing colleagues | "My students have to open each chain and list the names" |
| **3** | `CONCEPT_REACTION` | A response to a §12 concept probe — i.e. to something **the interviewer introduced** | Anything said after CP1–CP5 is read out |
| **4** | `RESEARCHER_INFERENCE` | Musnad's own reading of the above | "This maps to C09" |

A participant's unprompted judgement — "at this size, comparing by eye is fine" — is annotated
`PARTICIPANT_OPINION`. It is not one of the four classes and cannot establish that a task or a
pain point exists. It **can** corroborate a negative finding (§16) and qualify a conclusion.

### 3.2.1 What each class may and may not establish

| | Establishes a **recurring task** | Establishes a **pain point** | Establishes **structural-comparison demand** | Can raise wedge to `SUPPORTED` | Can set `C14_USER_TASK_EVIDENCE = OBSERVED` |
|---|---|---|---|---|---|
| `FIRST_HAND_TASK_EVIDENCE` | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| `PROXY_CONTEXT_EVIDENCE` | No | No | No | **No** | **No** |
| `CONCEPT_REACTION` | No | No | No | **No** | **No** |
| `RESEARCHER_INFERENCE` | No | No | No | **No** | **No** |

**`PROXY_CONTEXT_EVIDENCE` is genuinely useful — for four things only:** identifying
recruitment leads, revealing terminology, suggesting hypotheses worth testing with a first-hand
participant, and supplying contextual background. It is *not* a weaker grade of task evidence
that accumulates into a strong one; it answers a different question, because the reasons behind
each step — the material §11 and §14 actually depend on — do not survive second-hand retelling.

**`CONCEPT_REACTION` may never be counted as task evidence**, and a positive reaction is the
specific thing this study is built not to be persuaded by (§14.4 rule 1). **`RESEARCHER_INFERENCE`
is never evidence at all.**

---

## 4. Participant strategy

### 4.1 Ideal participant profile — profile A

Maps to G1 §3 **primary user**: the transmission-structure researcher. All four must hold.

| # | Criterion | Why it is required |
|---|---|---|
| A1 | Graduate-level or professional work in hadith studies, Islamic history, or Arabic digital humanities | G1 §3 defines the primary user at this level. Below it, the "task" is usually coursework reading |
| A2 | Has worked directly with **isnads** — not only with matn — recently enough to reconstruct the work concretely (§4.7) | The wedge is structural. A matn-only researcher cannot refute or support H1 |
| A3 | Has, on at least one real occasion, held **more than one chain or more than one report** in view at once for the same enquiry | This is the minimum behavioural precondition for H1. It does not presume comparison was *useful*, only that the situation arose |
| A4 | Can name a **specific, recent, real** task — trigger, resources, output — not a description of what researchers generally do | §8. A hypothetical task produces a hypothetical capability |

**Highest-information sub-profiles** (Malterud sample specificity — prioritise these when
choosing among candidates):

- A researcher who has worked with an **isnad dataset** — MIS/MIDS, or any narrator-network
  or graph dataset — because they can speak to H2 and H4 from experience rather than
  imagination.
- A researcher working **inside Sahih Muslim specifically**, because H6 is testable with them
  rather than around them.
- A supervisor or lecturer who has **watched students** perform these tasks, because they can
  distinguish routine difficulty from personal habit — but note that what they contribute about
  *others'* work is `PROXY_CONTEXT_EVIDENCE` and is bounded by §3.2.1.

### 4.2 Acceptable participant profile — profile B

B1 and B2 map to G1 §3's **secondary users**. Recorded as secondary and never aggregated with
profile A without the distinction being visible in the count.

| Sub-profile | Accept when | Recorded as |
|---|---|---|
| **B1 — advanced student** (طالب علم) doing structural orientation | Has a real assignment or thesis chapter that required looking at chains, with a specific occasion and output | `SECONDARY_STUDENT` |
| **B2 — Arabic NLP / DH engineer** | Has actually processed hadith or isnad data — parsing, entity work, network construction — for a real project, not a tutorial | `SECONDARY_ENGINEER` |
| **B3 — lecturer / teaching assistant** | Has set or supervised real structural tasks and can describe what learners actually did, distinguishing observation from assumption | `SECONDARY_TEACHING` |

> **B3 is not a user segment, and B3 accounts are proxy evidence.** G1 §3 defines one primary
> user and two secondaries; a lecturer or teaching assistant is **not** among them and this
> protocol does not add one. B3 is admitted only as a **proxy informant** about A and B1 work.
> Three consequences bind the record:
>
> 1. A B3 account of what *students* or *supervisees* did is tagged `PROXY_CONTEXT_EVIDENCE`,
>    never `FIRST_HAND_TASK_EVIDENCE` (§3.2). Per §3.2.1 it cannot on its own establish a
>    recurring task, a pain point, structural-comparison demand, `SUPPORTED`, or
>    `C14_USER_TASK_EVIDENCE`.
> 2. Where B3 describes their **own** research task — one they personally performed — that task
>    *is* first-hand, and is recorded under whichever of A or B1 they occupied while doing it
>    (§5.3). The distinction is per task, not per participant.
> 3. "Students usually…" and "researchers generally…" are not tasks at all, whoever says them.
>    They fail §8.1 before the proxy question arises.

B1 carries the obligation from G1 §3: this group is the most likely to read a structural output
as an authenticity signal. In interviews this matters twice — the interviewer must not let a
structural probe drift into a soundness question (§7.10), and any B1 statement about
authenticity is recorded as `PARTICIPANT_OPINION`, never as a task requirement.

### 4.3 Non-qualifying profile — profile C

Screened out. Recording *why* someone was excluded is itself evidence, so exclusions are logged
(§5.4) even though no interview follows.

| Not qualified | Reason |
|---|---|
| General reader asking whether a hadith is authentic, whether a narrator is reliable, or what the ruling is | G1 §3 — explicitly not a V1 target. Every such question terminates in the negative matrix |
| Someone whose only relevant activity is reading hadith, however extensively | No task, no workflow, no evidence to elicit |
| Someone interested because the product sounds interesting, or because they work in AI | Enthusiasm is not task evidence. This is the single most likely contaminant of a study run by its own engineer |
| Someone whose relevant work is entirely **rijal grading / jarḥ wa taʿdīl** with no chain-structure component | Their real need is U1/U7, which V1 cannot serve. **Record the encounter** — it is negative evidence for the wedge (§16 NE-4) — but do not run the full task interview |
| A close colleague, friend, or anyone with an interest in the project succeeding | Acquiescence bias. If unavoidable, record the relationship in the participant record and weight accordingly |
| Anyone who has already been shown Musnad, its capabilities, its repository, or this document | Contaminated. G1 §20 elicitation rule. **Not recoverable** — they cannot be un-told |

### 4.4 How many participants, and how to report scarcity

**Target: 3–5 participants, at least 2 of them profile A, and at least 2 independent of each
other in the operational sense of §4.6.** Independence is a recorded property of the evidence,
not an assumption made from the fact that two people are two people.

Justification, following Malterud et al.'s five dimensions rather than a rule of thumb:

| Dimension | This study | Effect on N |
|---|---|---|
| Study aim | Narrow — six named hypotheses, not an open exploration of the field | Lowers N |
| Sample specificity | Very high — profile A is tightly defined | Lowers N |
| Established theory | Moderate — G1 supplies a capability taxonomy the tasks are mapped onto | Lowers N |
| Quality of dialogue | Uncertain — a solo, non-specialist interviewer working across a language and a discipline boundary | **Raises N**, and is the honest weak point |
| Analysis strategy | Cross-case pattern-finding, not deep single-case interpretation | Raises N |

Two dimensions push up and three push down; 3–5 is the defensible band, and 2 is the floor
below which cross-case claims are not made at all.

**Reporting rules, non-negotiable:**

- Participant count is stated in the first line of every G2A finding, **with its dependence
  structure** — *"3 participants, 2 independent sources"* (§4.6).
- Counts are written as *"3 of 4 participants in this elicitation"* — never as a percentage,
  never as a claim about researchers in general (§17.C).
- First-hand and proxy counts are never added together (§3.2.1).
- **Scarcity is disclosed, not padded.** If only one participant is reachable, the correct
  output is one carefully recorded task set plus `PRODUCT_WEDGE_EVIDENCE = LIMITED`, not a
  fourth interview with someone who does not qualify.
- G1 §20 already permits proceeding: *G2A does not block G2B indefinitely.* §22 defines the
  exact form that exit takes.

### 4.5 Recruitment channels — realistic for a solo engineer

Listed roughly by expected yield per unit of effort. No individual is named in this repository.

| Channel | Approach | Notes |
|---|---|---|
| University departments of hadith / Islamic studies / Islamic history in the researcher's own country and region | Email a department or a named course convenor with the §19 message; ask to be forwarded to graduate students and staff working on transmission | Highest concentration of profile A. Slow; academic calendars matter |
| Arabic **digital humanities** and Islamic-studies DH networks, mailing lists and Slack/Discord communities | Post the §19 English message where posting is permitted | Reaches A and B2 together |
| Authors and users of **published isnad datasets**, reached through the contact channel published with the dataset itself | A short, specific message citing the dataset by DOI | Highest-information participants for H2 and H4. Low response rates are normal; do not chase |
| **Arabic NLP** research groups and communities | §19 English message | Mostly B2 |
| Postgraduate researchers presenting at hadith-studies or Islamic-manuscript conferences and workshops | Approach after a talk, or by the contact address in a public programme | Good for A4 — they have a live task |
| Existing academic contacts, snowball from a completed interview | Ask at the end of each session (§7 Stage I close) | Cheapest. **Threatens independence** — record who referred whom, and count referred pairs as one source of variation, not two |

**Ethical constraint on every channel.** The approach describes the *study*, never the
*product*, and must not promise grading, authenticity, identity, or cross-book capability
(§2 constraint 2). A recruitment message that oversells is not only a bias problem — it
recruits the wrong people.

### 4.6 Participant independence — operational definition

**Different people are not automatically independent sources.** Two participants who learned
the same method from the same supervisor, or who are recounting the same shared incident from
two seats at the same table, are one observation described twice. Counting them as two
confirmations manufactures agreement, and it is the easiest way for a small qualitative study to
convince itself.

**Dependence is recorded, not used to exclude anyone.** A dependent participant's task record is
kept in full; what changes is how it is counted.

| Field | Values |
|---|---|
| `EVIDENCE_DEPENDENCE` | `NONE` · `POSSIBLE` · `KNOWN` |
| `DEPENDENCE_WITH` | The other participant id(s) |
| `DEPENDENCE_BASIS` | Which indicator below applies |

**Indicators to check for every pair of participants**, and to ask about directly at Stage I:

| Indicator | Sets at least |
|---|---|
| Same research project, grant, or publication | `KNOWN` |
| Same immediate research team, lab, or reading group | `KNOWN` |
| One supervises, or supervised, the other | `KNOWN` |
| One taught the other the exact method being reported | `KNOWN` |
| Two accounts of **one shared incident** — the same task, seen from two seats | `KNOWN` |
| Same assignment, seminar, or prescribed workflow | `KNOWN` |
| Referred to the study by one another (§4.5 snowball) | `POSSIBLE` — raise to `KNOWN` if any row above also applies |
| Same department or institution, no shared work | `POSSIBLE` |
| No known connection | `NONE` |

**Counting rules, binding on §14 and §17:**

1. **Multiple retellings of one shared task count once.** The synthesis reports "one task,
   described by two participants", never "two participants reported this".
2. For `PRODUCT_WEDGE_EVIDENCE = SUPPORTED`, "multiple independent participants" means **at
   least two with `EVIDENCE_DEPENDENCE = NONE` relative to each other.** A cluster of
   `KNOWN`-dependent participants counts as **one** source of variation regardless of headcount.
3. `POSSIBLE` is reported as `POSSIBLE`. It is not rounded to `NONE` to reach a threshold, and
   the synthesis states what the flag would have been under either reading.
4. Every count in the synthesis carries its dependence structure — *"3 participants, 2
   independent sources"* — rather than a bare headcount.

> **This is not statistical independence and must not be described as one.** It is a
> qualitative safeguard against double-counting a single origin. No G2A output may treat these
> flags as licensing a significance claim, a sample-size calculation, or any inferential
> statistic (§17.1).

### 4.7 Recency — a quality signal, not an eligibility rule

**There is no 12-month cutoff.** An arbitrary window would exclude a well-reconstructed,
directly relevant task from three years ago while admitting a vague one from last month, and
the vague one is worthless (§8.1). What actually matters is whether the participant can
reconstruct the workflow, the evidence and the decisions **concretely**.

**Admission criterion.** A task is admissible when it is first-hand, passes the §8.1 specificity
test, and is relevant — whenever it happened.

**Recency is recorded as data**, on every task, and never silently converted into an eligibility
rule:

| Field | Values |
|---|---|
| `task_recency` | `WITHIN_1_MONTH` · `WITHIN_6_MONTHS` · `WITHIN_12_MONTHS` · `OLDER_THAN_12_MONTHS` · `ONGOING` |
| `reconstruction_quality` | `CONCRETE` — steps, resources and decisions recalled specifically · `PARTIAL` — outline recalled, details lost · `GENERIC` — recalled only as a pattern |

**How recency is used:**

- **Prefer recent tasks when choosing among candidates**, since NN/g's warning about recall
  applies and detail decays. Recency breaks ties; it does not decide eligibility.
- **Retain an older task when it is high-information** — first-hand, directly relevant, and
  `reconstruction_quality = CONCRETE`.
- **`reconstruction_quality = GENERIC` fails §8.1** whatever the date. This is the real filter,
  and it catches the case a date cutoff was a crude proxy for.
- The synthesis reports the recency distribution of admissible tasks, and names recall
  reliability as a stated limitation wherever `PARTIAL` or `OLDER_THAN_12_MONTHS` carried
  weight in a conclusion.

---

## 5. Screening protocol

A short exchange — email, message, or the first three minutes of a call. **It reveals nothing
about Musnad's proposed features.** Its only job is to establish role, real isnad contact, and
the existence of a specific recent task.

### 5.1 Screener questions

Ask in this order. Arabic wording is normative for Arabic-speaking candidates; the English is
for DH/NLP candidates.

| # | Purpose | Arabic wording | English wording |
|---|---|---|---|
| **S1** | Role and level | ممكن تحكي لي باختصار عن طبيعة عملك أو دراستك الحالية؟ | Could you tell me briefly what you work on or study at the moment? |
| **S2** | Contact with hadith texts | هل شُغلك بيتعامل مع نصوص الحديث بشكل مباشر؟ وفي أي سياق؟ | Does your work involve hadith texts directly? In what context? |
| **S3** | Contact with isnads — the qualifying question | وهل تعاملت مع الأسانيد نفسها، مش المتون بس؟ | And have you worked with the isnads themselves, not only the matn? |
| **S4** | Multiplicity — precondition for H1, asked without naming comparison | هل حصل واحتجت تشتغل على أكثر من رواية أو أكثر من طريق في نفس الوقت؟ | Has there been a time when you needed to work with more than one report, or more than one chain, at the same time? |
| **S5** | Recency and concreteness | آخر مرة اشتغلت فيها على حاجة زي دي كانت إمتى تقريبًا؟ | Roughly when was the last time you worked on something like that? |
| **S6** | Resources — establishes the working material | وقتها كنت بتشتغل على إيه بالظبط؟ كتب؟ مواقع؟ ملفات؟ | What were you actually working with at the time — books, websites, files? |
| **S7** | Real vs hypothetical | وده كان لشغل فعلي — بحث، رسالة، تدريس، مشروع — ولا حاجة مررت عليها بس؟ | Was that for actual work — research, a thesis, teaching, a project — or something you came across in passing? |

### 5.2 Qualifying, borderline, and excluding criteria

| Outcome | Condition |
|---|---|
| **QUALIFIES — profile A** | S1 at graduate/professional level in a §4.1 A1 field · S3 yes · S4 yes with a specific instance they personally performed · S7 real. **S5 is recorded, not used as a cutoff** (§4.7) |
| **QUALIFIES — profile B** | S3 yes and S7 real, but S1 is student, teaching, or engineering rather than research-primary. Record the sub-profile |
| **BORDERLINE — decide with §5.3** | S4 yes but the participant cannot yet locate a specific instance · S1 straddles categories · the only isnad contact was through a dataset, with no reading of chains · the only relevant work described is someone **else's** (proxy — §3.2) |
| **EXCLUDE** | S3 no · S7 hypothetical or "in general" after one clarification attempt · candidate matches any §4.3 row · candidate has already seen Musnad |

### 5.3 Borderline rule

One clarification attempt, then decide, then record the decision and its reason.

- **An older task** — admit whenever it is first-hand, relevant, and reconstructable in concrete
  detail. Record `task_recency` and `reconstruction_quality` per §4.7, and name recall
  reliability as a limitation in the participant summary. Do not exclude on the date alone.
- **Only someone else's work described** — admit as a `PROXY_CONTEXT_EVIDENCE` source and set
  expectations accordingly (§3.2.1): useful for terminology, leads and hypotheses, and unable to
  establish a task, a pain point, or `SUPPORTED`. Before settling for that, ask once whether the
  participant has done such work themselves (S4 anchored to *their own* hands).
- **No specific instance yet** — ask S4 once more anchored to a document rather than a memory:
  *"آخر ملف أو ورقة اشتغلت فيها على أكثر من طريق — تفتكر إيه كان؟"* If a specific artifact
  surfaces, admit. If the answer stays general, exclude — this is exactly the failure §8 exists
  to prevent.
- **Dataset-only contact, never read a chain** — admit as **B2**, not A. They are informative
  for H2 and H4 and uninformative for H1, and the record must say so.
- **Straddling roles** — classify by the role they occupied *during the task being elicited*,
  not by their title.

### 5.4 Exclusion log

Every screened-out candidate is logged, de-identified, in one line: date, channel, the criterion
that excluded them, and — where they volunteered it — what they actually wanted. This log is
evidence. A pattern of researchers whose real need is grading or cross-book takhrij is a direct
reading on the wedge (§16, NE-4 and NE-5) and would otherwise vanish silently.

---

## 6. Anti-bias safeguards

The single largest threat to this study is that it is designed, run and interpreted by the
person who wants the product to exist. NN/g's account of confirmation bias applies directly:
it shapes which questions are asked, which probes are pursued, which quotes are remembered, and
how the data is read. The safeguards below are structural rather than attitudinal.

### 6.1 The disclosure ladder — what may be said, and when

**No level may be entered before the level above it is complete and recorded.**

| Level | May be disclosed | When |
|---|---|---|
| **L0 — recruitment** | "A study of how people currently do research tasks involving hadith texts and isnads." Nothing about a system, comparison, AI, graphs, or capabilities | §19 |
| **L1 — consent and opening** | That the interviewer is building research software in this area, that no product will be shown, and that the interviewer wants the participant's current way of working | §20 |
| **L2 — Stages A–G** | Nothing new. Only the participant's own words are reflected back | §7 |
| **L3 — Stage H concept probes** | Neutral, capability-free descriptions of *possible* assistance, read from the fixed CP1–CP5 wording | §12 |
| **L4 — Stage I close and after** | If asked directly, a plain description of the project and its limits — including that it does not grade narrators or judge authenticity | §7 Stage I |

**Nothing in L3 or L4 is ever counted as task evidence.** Reaching L3 before Stages B–G are
recorded voids the participant's task evidence — the record is kept and flagged
`PROTOCOL_BREACH = CONCEPT_LEAK`, and it may still be used for terminology, never for the wedge.

### 6.2 The mandatory sequence

    THEIR RECENT REAL TASK  (Stage B)
        ↓
    THEIR CURRENT WORKFLOW  (Stage C)
        ↓
    THEIR EVIDENCE          (Stage D)
        ↓
    THEIR PAIN              (Stage E)
        ↓
    THEIR FAILURES          (Stage F)
        ↓
    THEIR REQUIRED OUTPUT   (Stage G)
        ↓
    ── disclosure boundary ──
        ↓
    CONCEPT PROBES          (Stage H)
        ↓
    TERMINOLOGY             (Stage I)

### 6.3 Never ask these first — the self-confirming set

Each of the following, asked before Stage H, invalidates the participant's task evidence. They
are listed because they are the questions the interviewer most wants to ask.

- "Would chain comparison be useful?"
- "Would you use an AI that compares isnads?"
- "Do you need to find the shared narrators between chains?"
- "Would a graph of the chains help?"
- "Is it hard to compare the chains manually?"
- "Do you need to know where the chains diverge?"
- Any question containing *compare*, *shared narrator*, *divergence*, *convergence*, *graph*,
  *agent*, *automatic*, *AI*, or *investigation*, applied to the participant's work rather than
  quoted from the participant.

### 6.4 Six structural safeguards

| # | Safeguard | Guards against |
|---|---|---|
| **AB-1** | **Pre-registered negative findings.** The nine findings in §16 are written down *before* the first interview. Each must be explicitly marked found / not found in the synthesis | Burying disconfirming evidence by never naming it |
| **AB-2** | **Disconfirming probes are mandatory, not optional.** Stage E includes a probe designed to elicit "this is not actually hard", and Stage H includes CP5, whose expected useful answer is *no* | Asking only questions whose yes-answer helps |
| **AB-3** | **Verbatim-first recording.** Task descriptions are captured in the participant's words before any mapping. `task_description_verbatim` is filled before `musnad_capability_mapping` is even considered | Retro-fitting the task to the capability |
| **AB-4** | **Wording review before use.** The Stage A–I wording is read once, in full, against the §6.3 list and the §7.10 list before the first interview, and again if any question is changed mid-study. Where a second reader is available, they do it | Leading wording the author cannot see |
| **AB-5** | **Mapping is done after the session, from the record, not during the interview.** The word "agentic" is never used in a session (IR-11) | Live interpretation steering later questions |
| **AB-6** | **Quote discipline.** Every quotation in any output is marked verbatim or paraphrase, and paraphrases never appear inside quotation marks | Remembered-but-improved quotes |

### 6.5 Interviewer self-check, immediately after each session

Four questions, answered in writing before analysis begins:

1. What did I hear that **argues against** the wedge?
2. Which question did I ask that I would not have asked if I wanted the opposite answer?
3. Where did I complete the participant's sentence, or supply a word they had not used?
4. Which of my notes are their words, and which are mine?

Answers go into the participant summary under `interviewer_reflexivity`. A session where
question 1 has no answer is flagged — not because disconfirmation must exist, but because its
total absence is more often a listening failure than a finding.

---

## 7. Interview guide — semi-structured, 20–35 minutes

Arabic wording is **normative** for Arabic-speaking participants; the English is a working
equivalent for DH/NLP participants, not a translation to be read aloud in an Arabic session.
The interviewer adapts register to the participant's dialect — the wording below is written to
be *said*, not read from a page.

Every question is marked **[CORE]** or **[IF TIME]**. When the session runs short, drop
`[IF TIME]` questions in reverse order and record which were dropped as `NOT_ASKED` — never
compress Stages B–C, which are the evidence.

**Budget, indicative maxima:** A 2 · B 5 · C 8 · D 3 · E 5 · F 3 · G 3 · H 4 · I 3 minutes.
That is the ~36-minute upper bound with everything asked; dropping the `[IF TIME]` questions
brings a session to 20–25, which is what the recruitment message promises.

### Stage A — Role and context · ~2 min

**Purpose.** Place the participant against G1 §3, and let them start talking about themselves
rather than about a system. Nothing here is evidence for the wedge.

| | |
|---|---|
| **A1 [CORE]** | **AR:** ممكن تحكي لي عن شغلك الحالي؟ إيه الموضوع اللي شغال عليه دلوقتي؟<br>**EN:** Tell me about your current work — what are you working on at the moment? |
| **A2 [CORE]** | **AR:** والحديث بيدخل في شغلك إزاي بالظبط؟<br>**EN:** And how do hadith texts enter your work, specifically? |
| **A3 [IF TIME]** | **AR:** من إمتى وانت بتشتغل على النوع ده من المادة؟<br>**EN:** How long have you been working with this kind of material? |

**Acceptable probes.** "قصدك إيه بـ…؟" · "ده كان في إطار إيه؟" · "ممكن مثال؟"

**Avoid.** Any framing of the interviewer as an expert in their field. Any mention of software,
tools, AI, or the project's subject matter beyond what §20's consent script already said.

---

### Stage B — The recent, concrete task · ~5 min

**Purpose.** Obtain **one specific occasion**, not a category of work. This is the single most
important stage; everything downstream is a walk through what B establishes. Follows the
critical-incident form — *a particular time* — with the recency variant from §3.1.

| | |
|---|---|
| **B1 [CORE]** — the opening | **AR:** خدني لآخر مرة احتجت فيها تبص على أسانيد حديث أو أكثر عشان تخلّص حاجة معيّنة. إيه اللي حصل؟<br>**EN:** Take me to the last time you needed to look at the chains of one or more hadiths in order to get something specific done. What happened? |
| **B2 [CORE]** — trigger | **AR:** إيه اللي خلّاك تحتاج تعمل كده وقتها؟ إيه اللي بدأ الموضوع؟<br>**EN:** What made you need to do that at that point? What started it? |
| **B3 [CORE]** — goal | **AR:** كنت عايز توصل لإيه بالظبط؟<br>**EN:** What exactly were you trying to arrive at? |
| **B4 [CORE]** — inputs | **AR:** بدأت من إيه؟ حديث معيّن؟ اسم؟ موضوع؟ قائمة؟<br>**EN:** What did you start from — a particular hadith, a name, a topic, a list? |
| **B5 [CORE]** — timing | **AR:** ده كان إمتى تقريبًا؟ وأخد منك قد إيه؟<br>**EN:** Roughly when was that, and how long did it take you? |
| **B6 [IF TIME]** — recurrence | **AR:** الشغلانة دي بتتكرر معاك؟ كل قد إيه تقريبًا؟<br>**EN:** Does this kind of thing recur for you? Roughly how often? |

**Acceptable probes.** "وبعدين حصل إيه؟" · "فاكر اليوم ده؟" · "كان قدامك إيه وانت بتعمل كده؟"
· "ممكن نفتح الملف ده لو موجود؟" (see IR-05) · "قبل ما تبدأ، كنت عارف إن ده هياخد الوقت ده؟"

**Wording to avoid.**

- "بشكل عام، الباحثين بيعملوا إيه؟" — invites the generalisation §8 exists to reject.
- "لو كنت محتاج تقارن…" — hypothetical, and leading.
- "إيه أصعب حاجة في الأسانيد؟" — presupposes difficulty; that is Stage E's job to find or fail
  to find.
- Any suggestion of what the answer might be while the participant pauses (IR-04).

**If B1 returns a generalisation** — "عادةً بنعمل كذا" — apply the §8 recovery ladder before
going further. Do not proceed to Stage C on a generalisation.

---

### Stage C — Walk through the workflow · ~8 min

**Purpose.** Reconstruct the actual sequence of steps. This is the master–apprentice stage: the
interviewer is learning a craft, and the participant is correcting them. The interpretation
principle applies — reflect the sequence back and let them fix it.

| | |
|---|---|
| **C1 [CORE]** | **AR:** طيب خدني خطوة بخطوة. أول حاجة عملتها كانت إيه؟<br>**EN:** Walk me through it step by step. What was the first thing you did? |
| **C2 [CORE]** — the engine of the stage, repeated | **AR:** وبعد كده؟<br>**EN:** And then? |
| **C3 [CORE]** — decision points | **AR:** في اللحظة دي، إيه اللي خلّاك تروح للخطوة اللي بعدها بالذات؟<br>**EN:** At that point, what made you go to that next step in particular? |
| **C4 [CORE]** — intermediate artifacts | **AR:** كنت بتسجّل حاجة وانت ماشي؟ ورق، ملف، جدول، حاجة كده؟<br>**EN:** Were you writing anything down as you went — paper, a file, a table? |
| **C5 [CORE]** — reflect back | **AR:** خليني أتأكد إني فهمت: انت عملت كذا، وبعدين كذا، وبعدين كذا. صح كده ولا فاتني حاجة؟<br>**EN:** Let me make sure I have it: you did X, then Y, then Z. Is that right, or did I miss something? |
| **C6 [IF TIME]** — abandoned branches | **AR:** كان في حاجة بدأتها وسِبتها في النص؟<br>**EN:** Was there anything you started and then abandoned partway? |

**Acceptable probes.** "ودي أخدت منك قد إيه؟" · "وده كان على الشاشة ولا على ورق؟" · "لو حد
تاني عمل نفس الشغلانة، كان هيمشي بنفس الترتيب؟" · silence (IR-06).

**Wording to avoid.**

- Naming an operation the participant did not name — *بحث*, *مقارنة*, *تجميع* — until they use
  it. Use their verb.
- "يعني انت قارنت الأسانيد؟" — this supplies the conclusion the study exists to test. If the
  behaviour is comparison, they will describe it; the record then says so in their words.
- Skipping ahead when the sequence gets slow. C2 is the whole stage.

**Note for the record.** C3 and C6 are the raw material for the §11 agent test. Capture the
*reason* for each next step verbatim where possible — whether it was fixed in advance or
determined by what the previous step returned is precisely what H5 turns on, and it cannot be
reconstructed later from a summary.

---

### Stage D — Evidence used · ~3 min

**Purpose.** Establish the working material: chains, matn, rijal literature, datasets, printed
editions. This is the direct test of H2 and a partial test of H6.

| | |
|---|---|
| **D1 [CORE]** | **AR:** إيه المصادر اللي فتحتها فعلًا وانت بتعمل ده؟<br>**EN:** Which sources did you actually open while doing this? |
| **D2 [CORE]** | **AR:** وانت بتبص على السند نفسه، بتبص على إيه بالظبط جواه؟<br>**EN:** When you were looking at the isnad itself, what exactly were you looking at inside it? |
| **D3 [CORE]** — the join, asked neutrally | **AR:** والنص والسند كانوا جايين من نفس المكان ولا من مكانين؟<br>**EN:** Did the text and the chain come from the same place, or from two different places? |
| **D4 [IF TIME]** | **AR:** استخدمت أي بيانات جاهزة أو ملفات — إكسل، قاعدة بيانات، أي حاجة رقمية؟<br>**EN:** Did you use any prepared data or files — a spreadsheet, a database, anything digital? |
| **D5 [IF TIME]** — H6 | **AR:** الشغل ده كان جوّه كتاب واحد ولا كان لازم تعدّي لكتب تانية؟<br>**EN:** Was this work inside one collection, or did you have to cross into other collections? |

**Acceptable probes.** "طبعة معيّنة؟" · "موقع بعينه؟" · "وليه ده بالذات؟"

**Wording to avoid.** "هل كان صعب توصل النص بالسند؟" — presupposes the pain. D3 asks where
things came from; Stage E asks whether that cost anything.

---

### Stage E — Difficult, slow, or manual steps · ~5 min

**Purpose.** Locate real cost. Per §3.1, this stage asks about **tedium** as well as failure,
because Musnad's claim is about routine difficulty. **AB-2 is enforced here:** E4 exists to give
the participant a comfortable way to say nothing was hard.

| | |
|---|---|
| **E1 [CORE]** | **AR:** في الخطوات اللي حكيتها، إيه اللي أخد وقت أكتر من اللازم؟<br>**EN:** Of the steps you described, which took more time than it should have? |
| **E2 [CORE]** | **AR:** كان في حاجة اضطريت تعملها بإيدك وكنت بتتمنى ما تعملهاش؟<br>**EN:** Was there anything you had to do by hand that you would rather not have? |
| **E3 [CORE]** — repetition | **AR:** كان في حاجة كرّرتها أكتر من مرة على أكتر من حالة؟<br>**EN:** Was there anything you repeated across more than one case? |
| **E4 [CORE]** — **the disconfirming probe** | **AR:** وفي المقابل، إيه الحاجات اللي كانت سهلة وماخدتش مجهود يُذكر؟<br>**EN:** And on the other side — what parts were straightforward and took no real effort? |
| **E5 [CORE]** — workarounds | **AR:** عملت إيه عشان تتصرّف في الحتة الصعبة دي؟<br>**EN:** What did you do to work around the hard part? |
| **E6 [IF TIME]** — scale | **AR:** لو كان عدد الطرق أو الأحاديث أكبر بكتير، كان الموضوع هيفرق؟<br>**EN:** If the number of chains or hadiths had been much larger, would that have changed things? |

**Acceptable probes.** "قد إيه من وقتك تقريبًا؟" · "ودي مضايقة بجد ولا مجرد شغل عادي؟" (the
§9 severity distinction) · "وعملت إيه بعدها؟"

**Wording to avoid.**

- "أكيد ده كان متعب؟" — supplies the answer and is hard to contradict politely.
- "ما كانش أسهل لو في أداة بتعمل كده؟" — a pitch wearing a question mark. This is the
  Mom-Test violation most likely to occur in practice.
- Treating E4's "it was all fine" as a failed question. **That answer is a finding** (§16 NE-2)
  and must be recorded with the same weight as a complaint.

---

### Stage F — Failure and uncertainty · ~3 min

**Purpose.** Find where the participant did not know, could not tell, or got it wrong — and what
they did about it. Feeds H3 directly.

| | |
|---|---|
| **F1 [CORE]** | **AR:** كان في لحظة مكنتش متأكد فيها من حاجة؟<br>**EN:** Was there a point where you were not sure about something? |
| **F2 [CORE]** | **AR:** عملت إيه ساعتها؟<br>**EN:** What did you do at that point? |
| **F3 [CORE]** — absence | **AR:** كان في حاجة دوّرت عليها وما لقيتهاش؟ وإيه اللي حصل بعدها؟<br>**EN:** Was there something you looked for and did not find? What happened then? |
| **F4 [IF TIME]** | **AR:** عرفت منين إنها مش موجودة، ولا فضلت مش متأكد؟<br>**EN:** How did you know it was not there — or did you stay unsure? |

**Acceptable probes.** "وده وقّفك ولا كمّلت؟" · "قلت لحد؟" · "كتبتها في الشغل النهائي؟"

**Wording to avoid.** "كنت عايز النظام يقول لك إيه ناقص؟" — that is concept probe **CP3** and
belongs in Stage H. Asking it here contaminates F4, which is the closest thing this study has
to uncoached evidence for H3.

---

### Stage G — The output they actually needed · ~3 min

**Purpose.** Establish what the work had to produce and what decision it fed. A task whose
output changed nothing is weak evidence however painful it was. Feeds H4.

| | |
|---|---|
| **G1 [CORE]** | **AR:** في الآخر، الشغل ده طلع في شكل إيه؟<br>**EN:** In the end, what form did this work come out in? |
| **G2 [CORE]** | **AR:** ودي اتحطّت فين؟ استخدمتها في إيه؟<br>**EN:** Where did that go — what did you use it for? |
| **G3 [CORE]** — citation practice, feeds H4 | **AR:** لما بتكتب حاجة زي دي، بتوثّق منين بالظبط؟<br>**EN:** When you write something like this up, what exactly do you cite? |
| **G4 [IF TIME]** — reproducibility | **AR:** لو حد راجع شغلك وحب يتأكد بنفسه، هيعمل إيه؟<br>**EN:** If a reviewer wanted to check this themselves, what would they do? |

**Acceptable probes.** "ورقة؟ فصل؟ جدول؟ محاضرة؟" · "وحد تاني شافها؟"

**Wording to avoid.** "كنت محتاج تفاصيل السجلات والمصدر بالظبط؟" — leading, and it is CP4.

---

### Stage H — Concept probes · ~4 min · **only after A–G are recorded**

Read the fixed wording in §12. Everything from here is tagged `CONCEPT_REACTION`. Do not demo,
do not describe Musnad's architecture, and do not defend a probe that lands badly.

---

### Stage I — Terminology, dependence, and close · ~3 min

**Purpose.** Capture natural vocabulary (see §13), and close the session honestly.

| | |
|---|---|
| **I1 [CORE]** | **AR:** انت استخدمت كلمة «…» أكتر من مرة. ممكن تقول لي انت بتقصد بيها إيه بالظبط؟<br>**EN:** You used the word "…" more than once — what exactly do you mean by it? |
| **I2 [CORE]** | **AR:** لما بتتكلم مع زمايلك عن النوع ده من الشغل، بتسمّوه إيه؟<br>**EN:** When you talk to colleagues about this kind of work, what do you call it? |
| **I3 [IF TIME]** | **AR:** في حاجة مهمة في شغلك ما سألتش عنها وكان المفروض أسأل؟<br>**EN:** Is there anything important about your work I did not ask about and should have? |
| **I4 [CORE]** — snowball, per §4.5 | **AR:** تعرف حد تاني شغله قريب من كده ممكن يكون مستعد يتكلم معايا؟<br>**EN:** Do you know anyone else working on something similar who might be willing to talk to me? |
| **I5 [CORE]** — dependence, per §4.6 | **AR:** الشغلانة اللي حكيتها دي، اشتغلت فيها لوحدك ولا كانت جزء من مشروع أو فريق؟ وحد علّمك الطريقة دي ولا وصلت لها بنفسك؟<br>**EN:** The work you described — did you do it on your own, or was it part of a project or a team? And did someone teach you that method, or did you arrive at it yourself? |

I5 is what makes §4.6 answerable. Without it, dependence is guessed from institutional
affiliation, which is exactly the weak proxy the section exists to replace. Ask it neutrally —
it is a question about how the work was organised, not about whose idea it was.

**Closing disclosure (L4).** If — and only if — the participant asks what the interviewer is
building, answer plainly and within the G1 boundary: research software over the chains recorded
in one published dataset for Sahih Muslim, which **does not grade narrators, does not judge
authenticity, does not issue rulings, and does not work across collections.** Offer to share
results. Do not ask for feedback on the idea; anything said after this point is `L4` and is not
evidence.

### 7.10 Questions and behaviours prohibited at any point before Stage H

| Prohibited | Why |
|---|---|
| Any question in §6.3 | Self-confirming |
| Describing any Musnad capability, screen, output, or dataset | G1 §20 elicitation rule |
| Using *مقارنة الأسانيد*, *الرواة المشتركين*, *نقطة الافتراق*, *مدار*, *graph*, *AI*, *agent* before the participant does | Supplies vocabulary, then hears it back — and corrupts §13, whose entire value is that the terms were unprompted |
| Promising or implying grading, authenticity, identity, biography, takhrij, dating, or cross-book capability | G1 §9 U1–U8. Also recruits the wrong participants |
| Asking the participant to evaluate an idea | Mom Test; produces politeness, not evidence |
| Correcting the participant on hadith methodology | The interviewer is the apprentice, not the master |
| Asking "would you use…", "would you pay…", "would you like…" | Hypothetical future; G2A does not measure demand |

---

## 8. The recent-task requirement

**A task is admissible evidence only if it is specific.** The following are not tasks and must
not be recorded as such:

- "الباحثين عادةً بيقارنوا الطرق."
- "دايمًا محتاج أشوف الأسانيد."
- "لو كان في أداة كده كنت هستخدمها."

### 8.1 The specificity test — all five must hold

| # | Must be identifiable | Field |
|---|---|---|
| 1 | A **specific occasion** — a day, a week, a session | `task_recency` |
| 2 | A **specific purpose** it served | `task_goal` |
| 3 | **Specific inputs** it started from | `input_objects` |
| 4 | **Specific resources** consulted | `resources_used` |
| 5 | A **specific output** it produced | `output_required` |

A record failing any of the five is marked `TASK_SPECIFICITY = FAILED` and is **excluded from
the §14 wedge assessment**. It may still contribute terminology (§13). Excluded records are
reported by count in the synthesis — silently dropping them would make the evidence look
stronger than it is.

### 8.2 Recovery ladder when the answer is general

Apply in order; stop at the first rung that produces a specific occasion.

1. **Anchor to time.** "آخر مرة كانت إمتى؟"
2. **Anchor to an artifact.** "آخر ملف أو ورقة أو محاضرة اشتغلت فيها على ده — إيه كانت؟"
3. **Anchor to a document surface.** "لو فتحنا آخر حاجة كتبتها في الموضوع ده، هنلاقي إيه فيها؟"
4. **Anchor to another person.** "آخر مرة سألك فيها طالب أو زميل عن حاجة زي دي؟"
5. **Stop.** Record `TASK_SPECIFICITY = FAILED`, note which rungs were tried, and move to Stage
   I. Do not invent an occasion collaboratively with the participant — a task the interviewer
   helped construct is the interviewer's task.

### 8.3 What is captured per task

Trigger · goal · inputs · sequence of steps · resources consulted · decisions made ·
intermediate artifacts · output · time and effort · pain · uncertainty · workaround.

**This is the core evidence of G2A.** Everything in §14, §15 and §16 is computed from it.

---

## 9. Task-record schema

One record per **elicited task**, not per participant — a participant may yield more than one.
Filled after the session from notes, never during it (AB-5).

### 9.1 Missing-value discipline

**Never invent a value.** Four reserved values, and they are not interchangeable:

| Value | Means |
|---|---|
| `UNKNOWN` | Asked, and the participant did not know or could not recall |
| `NOT_ASKED` | Not covered in the session — dropped for time, or the stage was cut |
| `NOT_APPLICABLE` | The field has no meaning for this task |
| `UNCLEAR` | The participant said something, but it does not resolve the field either way |

`UNCLEAR` is a real finding and must never be silently rounded to `NO`. In the three structural
flags (§9.2) it is the honest default whenever the evidence is thin.

### 9.2 Fields

| Field | Type | Notes |
|---|---|---|
| `participant_id` | `P01`…`Pnn` | §18. No name, no institution |
| `participant_role` | enum | `PRIMARY_RESEARCHER` · `SECONDARY_STUDENT` · `SECONDARY_ENGINEER` · `SECONDARY_TEACHING` |
| `participant_field` | free text | Discipline only, at a granularity that cannot identify the person |
| `task_id` | `P01-T1` | |
| `task_description_verbatim` | verbatim | **Filled first.** Their words. Arabic kept in Arabic |
| `task_goal` | text | What they were trying to arrive at |
| `task_trigger` | text | What started it |
| `task_recency` | enum | `WITHIN_1_MONTH` · `WITHIN_6_MONTHS` · `WITHIN_12_MONTHS` · `OLDER_THAN_12_MONTHS` · `ONGOING`. **Data, not an eligibility rule** — §4.7 |
| `reconstruction_quality` | enum | `CONCRETE` · `PARTIAL` · `GENERIC` — §4.7. `GENERIC` fails §8.1 whatever the date |
| `task_specificity` | enum | `PASSED` · `FAILED` — §8.1. `FAILED` excludes the record from §14 |
| `evidence_class` | enum | `FIRST_HAND_TASK_EVIDENCE` — the participant personally performed or directly participated · `PROXY_CONTEXT_EVIDENCE` — an account of someone else's work (§3.2). Governs what the record may establish (§3.2.1) |
| `evidence_dependence` | enum | `NONE` · `POSSIBLE` · `KNOWN` — §4.6 |
| `dependence_with` | list | Participant ids this record may share an origin with |
| `dependence_basis` | text | Which §4.6 indicator applies |
| `input_objects` | list | What they started from — hadith, name, topic, list, file |
| `current_workflow_steps` | ordered list | One entry per step, each with the participant's stated reason for the next step where given (Stage C3) |
| `resources_used` | list | Books, sites, datasets, files, people |
| `evidence_inspected` | list | What they actually looked at *inside* the sources — matn, chain, narrator name, ṭabaqa, grading, biography |
| `manual_operations` | list | Done by hand |
| `comparison_operations` | list | Any operation setting two or more objects against each other. **Recorded only if the participant described it**, never inferred from "they must have compared" |
| `search_operations` | list | Finding or locating operations |
| `identity_operations` | list | Anything about who a narrator is, or whether two mentions are the same person. Flag against G1 §9 U2/U7 |
| `uncertainty_points` | list | Where they did not know |
| `failure_modes` | list | Where it went wrong or stalled |
| `workarounds` | list | What they did instead |
| `output_required` | text | The artifact produced |
| `decision_or_use_of_output` | text | What it fed. `UNKNOWN` if never established |
| `frequency_if_known` | text | `UNKNOWN` unless stated |
| `estimated_effort_if_known` | text | Participant's own estimate. Never the interviewer's |
| `natural_terminology` | list | §13. Verbatim terms, with the participant's own gloss where given |
| `pain_points` | list | Their words |
| `pain_severity` | enum | `HIGH` · `MEDIUM` · `LOW` · `NONE` · `UNCLEAR`. **Only assignable on participant evidence** — §9.3 |
| `structural_comparison_present` | `YES`/`NO`/`UNCLEAR` | Did the task involve setting chains or reports against each other |
| `cross_hadith_reasoning_present` | `YES`/`NO`/`UNCLEAR` | Did it span more than one hadith |
| `cross_isnad_reasoning_present` | `YES`/`NO`/`UNCLEAR` | Did it span more than one chain |
| `dynamic_investigation_present` | `YES`/`NO`/`UNCLEAR` | §11 test. Not a synonym for "complex" |
| `could_fixed_workflow_help` | `YES`/`NO`/`UNCLEAR` | Could a predefined sequence have done the heavy part |
| `potential_agent_need` | `YES`/`NO`/`UNCLEAR` | §11. `YES` requires **AG-1 = AG-2 = AG-3 = AG-4 = `YES` *and* AG-5 = `NO`** |
| `ag5_workflow_sketch` | text | §11.2 — the bounded workflow that would have covered the task, or why no enumerable branch tree does |
| `musnad_capability_mapping` | list | §10. `C01`–`C15` · `U1`–`U8` · `MISSING_CAPABILITY` · `NONE` |
| `mapping_rationale` | text | Why, in one sentence, tied to the recorded steps |
| `researcher_quote_or_paraphrase` | text + class | Every entry carries a §18.5 class: `VERBATIM_CONSENTED` · `PARAPHRASED` · `NOT_FOR_PUBLICATION`. A paraphrase never appears inside quotation marks, and `NOT_FOR_PUBLICATION` never enters a tracked artifact |
| `protocol_notes` | text | Breaches, dropped stages, interpreter present, recording conditions |

### 9.3 The `pain_severity` rule

Assignable **only** from participant evidence, and the evidence is named in the record.

| Level | Requires |
|---|---|
| `HIGH` | The participant abandoned, deferred, narrowed the work, or engaged someone else because of it |
| `MEDIUM` | They built a workaround, or repeated a manual operation across cases |
| `LOW` | They named it as slow or annoying but it changed nothing about what they did |
| `NONE` | They explicitly said it was not a problem, or E4 established the step was easy |
| `UNCLEAR` | Anything else |

Interviewer sympathy is not evidence. Neither is the length of a complaint.

---

## 10. Task → capability mapping

Performed after the session, from the record. **The task is never adjusted to fit a
capability.** Where a task half-fits, the mapping records the half and the remainder separately.

### 10.1 Permitted outcomes

| Outcome | Meaning | What it implies |
|---|---|---|
| Maps cleanly to one `Cxx` | The recorded operation is what the capability does | Supporting evidence for that capability |
| Maps to several `Cxx` | A composite task | Record all, in the order the steps occurred |
| Maps to `NONE` | Real task, no V1 capability serves it | **Valuable evidence.** Never discarded. If it recurs, §16 NE-8 |
| Exposes a `MISSING_CAPABILITY` | A V1-legal operation that G1 §8 does not contain | Recorded with a one-line description. Input to G2B and to any future G1 revision — **it does not expand V1 here** |
| Maps to `U1`–`U8` | The real need is a blocked capability | Recorded separately (§10.3). **Does not expand V1** |
| Contradicts the wedge | The task is real and its shape argues against H1–H6 | Goes to §16 with the hypothesis it bears on |

### 10.2 Reference — the frozen capability set

Reproduced from G1 §8 for mapping only. G1 is authoritative.

| ID | Capability | Class |
|---|---|---|
| C01 | Grounded matn answer | WORKFLOW |
| C02 | Known-item hadith lookup | WORKFLOW |
| C03 | Hadith record card | WORKFLOW |
| C04 | Recorded chains of a hadith | WORKFLOW |
| C05 | Narrator record card | WORKFLOW |
| C06 | Narrator name resolution | WORKFLOW |
| C07 | Narrator occurrences | WORKFLOW |
| C08 | Chain neighbours of a narrator | WORKFLOW |
| C09 | Isnad comparison within one hadith | WORKFLOW |
| C10 | Narrator pair relation | WORKFLOW |
| C11 | Narrator co-occurrence | WORKFLOW |
| C12 | Cross-hadith chain comparison | WORKFLOW |
| C13 | Topic + narrator constrained retrieval | WORKFLOW |
| C14 | Open structural investigation | **AGENT** |
| C15 | Evidence-gap diagnostic | WORKFLOW |

**Wedge-bearing capabilities.** C09, C10, C11, C12 and C13 are the structural-comparison
capabilities the wedge rests on; C15 carries H3; C03 and C04 carry H2. A study in which every
elicited task maps only to C01, C02 and C04 is evidence *against* the wedge, not for it — those
are the commoditised layers G1 §6 explicitly refuses to compete on.

### 10.3 U-mapping rule

A task mapping to `U1`–`U8` is recorded in a **separate table** in the synthesis, headed
*"real needs V1 cannot serve."* It never appears in the wedge count.

**It does not reopen V1.** G1 §9 blocks each entry on missing evidence, not on preference, and
elicitation does not supply the missing evidence. What repeated U-mappings *do* establish is the
size of the gap between what users want and what V1 offers — which is a positioning finding
(§16 NE-4, NE-5) and belongs in front of G1 §6 at the next revision, not in a V1 backlog.

---

## 11. Complexity is not agency — the per-task classification test

G1 §13 is binding and is restated here in the form the analysis uses: four aligned criteria
(§11.1), one mandatory workflow-representation check (§11.2), and the list of things that look
agentic and are not (§11.3).

### 11.1 The test — applied to every task with `dynamic_investigation_present ≠ NO`

Four criteria. **Every criterion is written so that `YES` is the agent-supporting answer** — the
directions are aligned deliberately, because a rubric with one inverted item silently converts
workflow evidence into agent evidence.

| # | Criterion | Question | Agent-supporting |
|---|---|---|---|
| **AG-1** | **Dynamic sequence necessity** | Was the complete useful operation sequence **impossible or unreasonable to determine before execution**, because later operations depended on intermediate observations? | `YES` |
| **AG-2** | **Discovery-dependent next action** | Did an **entity or fact discovered during execution** determine which evidence operation became useful next? | `YES` |
| **AG-3** | **Observation-dependent plan change** | Did an **empty, ambiguous, contradictory or otherwise informative intermediate result change the investigation plan**, rather than merely trigger a predetermined retry or fallback? | `YES` |
| **AG-4** | **Evidence-sufficiency termination** | Was stopping determined by **whether enough evidence had been gathered**, rather than by completing a predefined sequence, exhausting a list, or hitting a counter or deadline? | `YES` |

Each is recorded as `YES` / `NO` / `UNCLEAR`. `UNCLEAR` is not `YES`.

### 11.2 AG-5 — the mandatory workflow-representation check

**Four `YES` values do not by themselves make a task agentic.** A participant's account can
sound exploratory and still describe something a bounded workflow covers exactly; retrospective
narration tends to dramatise what was in fact routine. So one further check is required, and it
is the analyst's, not the participant's:

| # | Check | Consequence |
|---|---|---|
| **AG-5** | **Could the observed behaviour still be represented cleanly as a bounded, enumerable workflow with predetermined branches?** | **`YES` → classify as WORKFLOW evidence, not C14 evidence**, whatever AG-1–AG-4 returned. **`NO` → it may count as C14 user-task evidence** |

To answer AG-5 the analyst writes, in the record, **the workflow that would have covered the
task** — the operation sequence with its branches. If that sketch can be written, AG-5 is `YES`
and the task is workflow evidence. If writing it requires a branch tree that cannot be
enumerated or tested, AG-5 is `NO`.

`potential_agent_need = YES` requires **AG-1 = AG-2 = AG-3 = AG-4 = YES and AG-5 = NO.** Any
other combination is workflow evidence.

### 11.3 What does not survive this test — G1 §13, in force

None of the following is agent evidence, at any count, in any combination:

| Not agency | Because |
|---|---|
| **Many steps** | A long fixed ladder is deterministic at every rung |
| **Unknown fan-out** | Iterating an unknown-length list is a loop; size is not complexity |
| **Many chains** | A comparison spanning 24 chains is still set arithmetic |
| **Multiple tools** | G1's C12 calls five kinds of operation and remains a workflow |
| **A conditional branch** | Fixed branching written into the code path |
| **A predetermined fallback or retry** | G1 records a measured negative result for exactly this pattern — CRAG self-grading with one rewrite, built here, no gain |
| **Multiple documents, or text combined with structure** | That is an evidence pipeline (`CROSS_LAYER`), not an orchestration class |

### 11.4 The decisive contrast, in participant material

A researcher who knew from the outset that they would "open each chain and note the repeated
names" scores **AG-1 = NO** however many chains there were: the sequence was determinable in
advance, so this is workflow evidence.

A researcher who says "I found that name, and *because it was that name* I then went and looked
at…" has produced **AG-2 = YES** material — but it only reaches C14 if the detour genuinely
could not have been anticipated (**AG-1 = YES**) and if no enumerable branch tree covers it
(**AG-5 = NO**). "I checked X, and if X was empty I always check Y" is a predetermined fallback:
AG-3 = NO, and AG-5 = YES.

### 11.5 Per-task outcome

The five answers are recorded on the task record, with the AG-5 workflow sketch, as
`potential_agent_need`. The **study-level** flag is set once, across all tasks, by §15.

---

## 12. Concept probes — Stage H, after A–G only

**Purpose.** Test reaction to *possible assistance* described without naming a feature, an
architecture, or Musnad. Everything here is tagged `CONCEPT_REACTION` (§3.2) and is recorded in
the **participant summary**, never in the task record.

**Rules.** Read the wording as written. Do not demo. Do not show a screen. Do not defend a probe
the participant dismisses — a dismissal is the most valuable answer this stage can produce. Ask
each probe **against the workflow the participant just described**, so the answer is anchored to
their work rather than to an idea.

| ID | Probes | Wording |
|---|---|---|
| **CP1** | H1 — **the decisive question**, per G1 §20 | **AR:** لو نظام قدر يعرض عدة طرق مسجّلة جنب بعض ويأشّر آليًا على الأسماء المتكرّرة وعلى الروايات المتكرّرة بينها — فين، لو في مكان أصلًا، كان ممكن ده يدخل في الشغل اللي حكيته لي؟<br>**EN:** If a system could show several recorded chains side by side and mechanically highlight repeated identifiers and repeated adjacent transmissions — where, if anywhere, would that fit into the workflow you just described? |
| **CP2** | H2 / H3 — coverage disclosure | **AR:** لو بعض السجلات ما اتوصلتش بالبيانات البنيوية، هل يهمّك تشوف السجلات المستبعَدة والسبب؟<br>**EN:** If some records could not be joined to the structural dataset, would seeing the excluded records and the reason matter to your work? |
| **CP3** | H3 — named absence | **AR:** لما نظام ما يقدرش يثبت علاقة من بياناته، هل جملة «غير ثابت في هذه البيانات» تفيدك في حاجة؟<br>**EN:** When a system cannot establish a relation from its data, is "not established in this dataset" useful information to you? |
| **CP4** | H4 — provenance granularity | **AR:** كنت هتحتاج إحداثيات السجلات ومصدرها بالضبط، ولا الملخّص النثري بيكفي؟<br>**EN:** Would you need the underlying record coordinates and provenance, or would a prose summary be enough? |
| **CP5** | **AB-2 — the disconfirming probe** | **AR:** وفي الحالات اللي بتشتغل عليها فعلًا، هل قراءة الطرق بعينك بتكفي وخلاص؟<br>**EN:** And in the cases you actually work on — is reading the chains yourself simply enough? |

**CP5 exists to be answered "yes, it's enough."** If it is never asked, or if its answer is not
recorded with the same prominence as CP1's, the study has failed its own anti-bias design.

**Recording.** For each probe: the answer verbatim or closely paraphrased and marked as such ·
whether the participant located a place in *their own* workflow for it (`FIT_LOCATED` /
`NO_FIT_LOCATED` / `UNCLEAR`) · whether they qualified or resisted it · anything they proposed
instead. A probe answered with polite approval and **no location in their workflow** is recorded
as `NO_FIT_LOCATED`, and G1 §20 governs the reading: this is *their judgement*, and enthusiasm
without a location is not a judgement in favour.

**Not permitted at Stage H.** Describing the graph, the linkage, the statuses, the agent, MIS
identifiers, hashes, or the abstention taxonomy. Asking "would you use it". Asking about price,
adoption, or willingness to try. Naming the project.

---

## 13. Terminology capture

**Purpose.** Record the participant's own Arabic and scholarly vocabulary, to inform G2B
question wording, later interface language, and tool descriptions. **Not** to establish scholarly
equivalence, and **not** to infer that two participants using one word mean the same thing.

### 13.1 Method

1. During Stages B–G, write terms **verbatim** as they occur, with the sentence around them.
2. Do not introduce a term the participant has not used (§7.10).
3. At Stage I, ask for a gloss of the two or three most load-bearing terms — I1.
4. Record which term the participant used for the same concept **at different moments**;
   inconsistency within one participant is itself data.

### 13.2 Concepts to watch for — a listening aid, never a checklist to read aloud

طريق · سند · إسناد · رواية · راوٍ مشترك · اختلاف الطرق · مدار · متابعة · شاهد · طبقة ·
تخريج · سياق الرواية — together with how they refer to sources, editions, numbering, and
"the dataset" if one was used.

**These words are for the interviewer's ear only.** Reading this list to a participant would
manufacture exactly the vocabulary the study is trying to observe.

### 13.3 Prohibited impositions

Do not offer, and do not record as the participant's, any of: *node*, *edge*, *graph*,
*traversal*, *evidence board*, *trajectory*, *agent*, *pipeline*, *entity resolution*. If a
participant uses one unprompted — plausible for a B2 engineer — record it verbatim and note that
it was unprompted.

### 13.4 What the output is, and is not

The terminology output is a **vocabulary record**, not a glossary of scholarly definitions. Two
participants using مدار differently is recorded as two usages, not reconciled into one. No
G2A output may assert what a term means in the discipline; it may only assert what a named
participant said it meant to them.

---

## 14. `PRODUCT_WEDGE_EVIDENCE` rubric

The approved vocabulary is exactly three values, carried from G1 §20. **`VALIDATED`,
`MARKET_VALIDATED` and `PRODUCT-MARKET-FIT` are prohibited.**

### 14.1 The three values

| Value | Set when | Consequence — from G1 §20 |
|---|---|---|
| **`SUPPORTED`** | **All four conditions hold.** (i) The evidence is `FIRST_HAND_TASK_EVIDENCE` (§3.2) — tasks the participants personally performed. (ii) It comes from **at least two participants independent of each other** under §4.6, i.e. `EVIDENCE_DEPENDENCE = NONE` between them. (iii) The tasks pass §8.1 (`TASK_SPECIFICITY = PASSED`) and their recorded operations align with the structural-comparison / evidence-provenance / investigation wedge. (iv) The alignment is visible in **Stages B–G, before any concept probe** — uncoached | C09–C13 proceed as specified. **Still evidence, not proof** |
| **`LIMITED`** | Evidence exists but rests on too few participants, mixed signals, or a narrow sample | **Engineering proceeds — it is not blocked.** The product hypothesis stays provisional and is re-checked at G5. G1 records this as the *expected* outcome |
| **`NOT_SUPPORTED`** | Elicited real tasks do not support the proposed wedge strongly enough, or materially contradict it | **Reopen G1 §6 positioning before G3 tools are built around the assumption.** The structural capabilities may still be built; what is wrong is the positioning in G1 §2 |

### 14.2 Qualifiers recorded alongside the value

The flag alone hides too much. Three mandatory companions:

| Field | Values |
|---|---|
| `WEDGE_EVIDENCE_BASIS` | `ELICITED_TASKS` — the flag rests on real recorded tasks · `NO_ELICITATION_ASSUMPTIONS_CARRIED` — no admissible task was elicited and G1's assumptions are carried forward as assumptions, per G1 §20 |
| `PARTICIPANTS_N` / `PRIMARY_N` | Total, and how many were profile A |
| `ADMISSIBLE_TASKS_N` | Tasks with `TASK_SPECIFICITY = PASSED` |

A `LIMITED` with `NO_ELICITATION_ASSUMPTIONS_CARRIED` and a `LIMITED` resting on two real
participants are different states, and G2B must be able to tell them apart. G1 §20 permits the
first — *G2A does not block G2B indefinitely* — but requires it be recorded as assumptions, not
findings.

### 14.3 Per-hypothesis reading — filled before the overall flag is set

The overall value is not assigned by impression. Each hypothesis gets its own verdict from the
task records first, and the overall flag is then justified in one paragraph against this table.

| Hypothesis | Verdict | Evidence — task ids | Counter-evidence — task ids |
|---|---|---|---|
| H1 chains as comparable objects | `SUPPORTED` / `LIMITED` / `NOT_SUPPORTED` / `NOT_ASSESSED` | | |
| H2 matn ↔ structure join is a real cost | | | |
| H3 named absence is useful | | | |
| H4 record-level provenance needed | | | |
| H5 non-enumerable operation sequence | | | |
| H6 one collection still useful | | | |

### 14.4 Rules that bind the assignment

1. **First-hand task evidence outranks everything else.** A `SUPPORTED` verdict may not rest on
   Stage H answers, and **a positive concept reaction can never upgrade the flag by itself**.
   "Yes, comparison sounds useful" is a `CONCEPT_REACTION` about an idea the interviewer
   supplied; what a participant *did* outweighs how they reacted to a proposal. Enthusiasm at
   CP1 with `NO_FIT_LOCATED` is not support — it is closer to NE-8.
2. **Proxy evidence cannot carry the flag.** `PROXY_CONTEXT_EVIDENCE` counts toward none of the
   four §14.1 conditions (§3.2.1). A study whose only wedge-aligned material is what a lecturer
   says students do is `LIMITED` at best, whatever its headcount.
3. **Independence is required for "multiple", in the §4.6 sense.** Two participants on the same
   project, in the same team, in a supervisory relationship, taught the same method, or
   recounting one shared incident are **one** source of variation. `POSSIBLE` dependence is
   reported as `POSSIBLE` and the flag is stated under both readings.
4. **`UNCLEAR` never rounds toward the wedge.** A structural flag left `UNCLEAR` is counted with
   the counter-evidence when deciding between `SUPPORTED` and `LIMITED`.
5. **The rubric is not adjusted after seeing results.** The thresholds above are fixed by this
   document, dated before any interview, in the same spirit as the pre-registration discipline
   G1 §20 and ADR-008 impose on the benchmark.
6. **`NOT_SUPPORTED` is a legitimate result of this project**, not a failure of it — G1 §6
   names it in advance as redundancy condition 4.

---

## 15. `C14_USER_TASK_EVIDENCE` rubric

G2A is **not** supposed to prove C14. Its only job is to record whether real tasks exhibit the
structural property that could later justify it.

| Value | Set when |
|---|---|
| **`OBSERVED`** | At least one admissible **first-hand** task (§3.2) satisfies **AG-1 = AG-2 = AG-3 = AG-4 = `YES` and AG-5 = `NO`** (§11.1–§11.2). The synthesis names **exactly which task**, quotes the step showing AG-2 or AG-3, and reproduces the AG-5 reasoning for why no bounded workflow covers it |
| **`INCONCLUSIVE`** | A task shows AG-2 or AG-3 but AG-1 or AG-5 cannot be settled from the record; or the only candidate failed the §8.1 specificity test; or the only candidate is `PROXY_CONTEXT_EVIDENCE` |
| **`NOT_OBSERVED`** | No elicited task exhibits the property — including the case where every candidate was reclassified as workflow evidence by AG-5 |
| **`NOT_YET_ASSESSED`** | Before elicitation. **Current value** |

**Proxy evidence can never set `OBSERVED`.** A lecturer's account of what students do may raise
the hypothesis; it cannot establish that the property occurred, because the reason each next
operation was chosen is exactly what a second-hand account loses (§3.2, §4.2).

**`NOT_OBSERVED` neither deletes C14 nor is fatal to it.** G1 §27 places the agent's fate at G4,
on a measured benchmark against a workflow baseline that must exist first. What `NOT_OBSERVED`
does establish is that C14's *user-task* premise is unevidenced, which G2B must record when it
writes the S6–S10 strata and which G4 weighs alongside the measured delta.

> **Do not manufacture an agent use case.** An agent use case invented at G2A would make the G4
> falsification test unfalsifiable — precisely the failure G1 §1.2 condition 4 exists to
> prevent, and precisely the temptation a project that wants to be agentic will feel here.

---

## 16. Negative-evidence protocol

**Pre-registered.** The nine findings below are written down before the first interview so they
cannot be quietly not-looked-for. **Every one is explicitly marked in the synthesis**, whether or
not it was found. "Not observed" is a valid mark; silence is not.

| ID | Negative finding to look for | Bears on | Where it would surface |
|---|---|---|---|
| **NE-1** | Users rarely hold more than one chain in view; chains are read one at a time | H1 | Stage B/C, screener S4 |
| **NE-2** | Reading and comparing chains manually is already easy enough at this scale | H1 | Stage E4, CP5 |
| **NE-3** | The real pain is **retrieval** — finding the relevant hadith at all — not comparison | H1, and G1 §6's "commoditised layer" | Stage E1, mapping to C01/C02 only |
| **NE-4** | The real pain is **grading or narrator reliability** — G1 §9 U1/U7 | Wedge scope | Screener exclusion log, U-mapping |
| **NE-5** | The real pain is **takhrij across collections** — U5 — making a one-book instrument insufficient | H6 | Stage D5, U-mapping |
| **NE-6** | Provenance at record granularity is unnecessary; participants cite printed editions and would accept a prose summary | H4 | Stage G3, CP4 |
| **NE-7** | Participants cannot interpret dataset-internal narrator identities meaningfully, or would not trust them | H2, and G1 §4 constraint 2 | CP1 reaction, Stage D |
| **NE-8** | Structural outputs would not change a research decision — interesting but inert | Whole wedge | Stage G2, CP1 `NO_FIT_LOCATED` |
| **NE-9** | Open, evidence-directed investigation does not occur naturally; work is planned in advance | H5, C14 | §11 — `AG-1 = NO`, or `AG-5 = YES`, on every task |

### 16.1 Handling rules

- Negative findings get their **own section** in the synthesis (T3 §4), not a footnote inside a
  positive one, and not a "risks" appendix.
- A negative finding from **one** participant is reported as one participant's evidence — it is
  neither generalised nor dismissed for being singular.
- Where a negative finding and a positive finding coexist, **both are reported with their task
  ids**. The synthesis does not resolve the tension by choosing; it names it as an open
  uncertainty (T3 §6).
- If NE-1, NE-2 and NE-8 are all marked *found* and no admissible task maps to C09–C13, the
  correct overall value is `NOT_SUPPORTED`. That inference is fixed here, in advance, so it
  cannot be argued around later.

---

## 17. Synthesis procedure

Lightweight enough for one engineer, strict enough that the conclusion is traceable to a record.
No enterprise research tooling: plain text or Markdown files plus the three templates in §23 are
sufficient and are what this section assumes.

**A · Normalise without changing meaning.**
Transcribe each task into a T1 record. Keep Arabic in Arabic. `task_description_verbatim` is
filled before any interpretive field. Normalisation means consistent field use and nothing else
— no smoothing, no tidying of a contradictory account, no translation of a term into its
"proper" scholarly equivalent.

**B · Cluster by job and operation, not by person.**
Group tasks by *what was being done* — locating, reading, cross-referencing, tabulating,
comparing, checking a name, chasing a gap — using the participants' verbs. Do not cluster by
discipline, seniority, institution, or country; those are not the unit of analysis and grouping
by them invites demographic storytelling the sample cannot support.

**C · Count carefully, and state the denominator and the dependence structure.**
Write *"3 of 4 participants in this elicitation"*. **Never** a percentage, never "researchers
generally", never a projection to a population. This mirrors the denominator discipline already
enforced elsewhere in this repository — every rate carries the base it was computed on. Counts
are of **participants** and of **admissible tasks**, reported separately, because one participant
can contribute several tasks and inflate a task count on their own.

Three further rules, from §4.6 and §3.2.1:

- **Multiple retellings of one shared task count once.** Write "one task, described by two
  participants", never "two participants reported this".
- **Every count carries its dependence structure** — *"3 participants, 2 independent sources"*.
- **First-hand and proxy counts are never summed.** A claim supported by two first-hand tasks
  and one lecturer's account of students is *"2 first-hand tasks, plus proxy context"*.

**D · Preserve unique high-value tasks.**
A task occurring once is not noise. A single well-evidenced first-hand task that passes the
full §11 test — AG-1–AG-4 `YES` with AG-5 `NO` — or that maps to a `MISSING_CAPABILITY`, is
recorded in full and carried into G2B. Clustering must not average it away.

**E · Keep the four evidence classes separate** (§3.2) — `FIRST_HAND_TASK_EVIDENCE`,
`PROXY_CONTEXT_EVIDENCE`, `CONCEPT_REACTION`, `RESEARCHER_INFERENCE`, plus the
`PARTICIPANT_OPINION` annotation. Each appears under its own heading in T3, and first-hand and
proxy counts are never added together. A sentence that mixes two classes is rewritten.

**F · Map.** Produce four tables:
1. tasks → G1 capabilities C01–C15;
2. tasks → U1–U8 — *real needs V1 cannot serve* (§10.3);
3. tasks → `MISSING_CAPABILITY` — V1-legal operations G1 §8 lacks;
4. tasks → `NONE` — no Musnad relevance.

Tables 2–4 are reported with the same prominence as table 1. A synthesis showing only table 1
has hidden its most useful findings.

**G · Derive, in this order.**
1. Strongest wedge evidence, with task ids.
2. Strongest negative evidence, with task ids (§16).
3. Open uncertainties — including every contradiction left unresolved at step F.
4. The §14.3 per-hypothesis table.
5. `PRODUCT_WEDGE_EVIDENCE` with its §14.2 qualifiers.
6. `C14_USER_TASK_EVIDENCE` per §15.
7. What G2B should carry forward: candidate question wordings traceable to a task id,
   terminology, and the strata those tasks touch.

### 17.1 Prohibited in synthesis

- Percentages, projections, or any claim about researchers beyond those interviewed.
- Merging profile A and profile B counts without the split being visible.
- **Adding `PROXY_CONTEXT_EVIDENCE` to first-hand counts**, or letting proxy material carry a
  task, a pain point, `SUPPORTED`, or `C14_USER_TASK_EVIDENCE` (§3.2.1).
- Promoting a `CONCEPT_REACTION` into evidence of a task, or letting a positive concept reaction
  upgrade the wedge flag (§14.4 rule 1).
- **Counting dependent retellings as independent confirmations** (§4.6), or rounding
  `EVIDENCE_DEPENDENCE = POSSIBLE` to `NONE` to reach a threshold.
- **Describing the §4.6 dependence flags as statistical independence**, or attaching any
  significance claim, confidence interval, or inferential statistic to a qualitative count.
- Treating `UNCLEAR` as `YES` in any structural or AG flag.
- **Declaring a task agentic on AG-1–AG-4 alone**, without the AG-5 workflow-representation
  check and its written sketch (§11.2).
- Writing an unbuilt capability in the past tense, or describing G2A findings as validation.
- Rewriting a task so that it maps to a capability (§10).
- Dropping `TASK_SPECIFICITY = FAILED` records without reporting their count (§8.1).
- Using recency as a silent eligibility filter instead of recording it as data (§4.7).

---

## 18. Research ethics and data minimisation

This is lightweight professional-practice research, not a clinical or regulated study. The
obligations below are proportionate to that, and they are strict about one thing: **participant
records stay minimal and de-identified.**

### 18.1 What is collected

| Collect | Do not collect |
|---|---|
| A participant identifier `P01`, `P02`, … | Full legal name |
| Role and level — "graduate researcher", "lecturer" | Employer, department, or institution in the stored record |
| Discipline at a coarse grain — "hadith studies", "Arabic DH" | Address, phone, national identifiers |
| The task content itself | Religious affiliation, madhhab, political views |
| Working language, and whether Arabic is the working language | Age, gender, nationality, ethnicity |
| Whether the participant was referred by another participant | Anything not needed to interpret the task |

Role and context are recorded **only to the level needed for research interpretation** — enough
to know which G1 §3 user the task came from, and no more.

### 18.2 Participant identifiers

Participants are `P01`, `P02`, … Tasks are `P01-T1`, `P01-T2`, … The identifier is the **only**
handle used in any tracked artifact, in any note that could be committed, and in any output.

**The `P01 → real person` mapping is not a project artifact.** It is not committed, not
referenced by path in any tracked file, and not reconstructable from what is committed.

### 18.3 What may be tracked in git, and what may never be

**Permitted — and only these, and only at G2A close:**

| Tracked artifact | Condition |
|---|---|
| De-identified task records (T1) | No name, employer, or identifying specialism |
| De-identified participant summaries (T2) | Role and coarse discipline only |
| De-identified cross-participant synthesis (T3) | Counts and dependence structure, no identities |
| Paraphrases | Marked `PARAPHRASED` |
| Anonymous verbatim quotations | Only where marked `VERBATIM_CONSENTED` (§18.5) |

**Must never enter git, in any branch, at any time:**

- Participant names, or any name at all
- Email addresses, phone numbers, handles, or any contact detail
- Raw contact or recruitment lists
- Raw audio or video recordings, and raw transcripts
- Screenshots, photographs, or scans that identify a person or an institution
- Private research documents, drafts, datasets or files a participant shared
- **Any participant-id → real-person mapping**, in any form, including a partial one
- Institution, department, project, grant or publication names attached to a participant
- Any detail that would single someone out in a small field — an unusual specialism, a
  distinctive dataset, a named collaboration. Where such a detail is load-bearing, it is
  generalised and the generalisation is marked as such

**Before any G2A artifact is committed**, it is read once against this list. A commit is the
point of no return in a public repository: a later deletion does not remove history.

### 18.4 Raw notes and recordings

- **Private storage only** — outside this repository, not in a synced project folder that is
  itself tracked, and not in the scratchpad of any tooling that persists to a shared location.
- **Audio or video recording only after explicit permission**, asked for at L1 (§20) and
  recorded as given or refused. If refused, take written notes. Never record covertly under any
  framing, including "just for my own accuracy".
- **Minimum necessary retention.** Raw material is kept only as long as it is needed to produce
  the de-identified records, then deleted. Retention is not extended because the material might
  be useful later.
- A participant may **withdraw** at any point, including after the session. On withdrawal the
  raw material is deleted, the record is removed, and every count that used it is restated —
  not quietly retained because the analysis is already written.

### 18.5 Quotation classes

Every quotation carries exactly one class. **Participation in an interview does not by itself
permit public quotation**, and no output may treat it as if it did.

| Class | Means | May appear in |
|---|---|---|
| `VERBATIM_CONSENTED` | Word-for-word, and the participant has agreed to this specific use | Tracked artifacts and any published output |
| `PARAPHRASED` | Reworded by the analyst, meaning preserved, never inside quotation marks | Tracked artifacts and published output |
| `NOT_FOR_PUBLICATION` | Said in confidence, or consent was not obtained or was withdrawn | Private notes only. **Never committed, never published**, and never used as a quotable basis for a claim |

Consent for a verbatim quote is specific and is asked for after the session with the quote in
front of the participant, not inferred from the consent script. **When in doubt, paraphrase** —
the analytical value of a quote is almost never worth the exposure of getting this wrong.

### 18.6 Institutional research-ethics requirements

This protocol is written for lightweight practitioner research conducted to inform an
engineering decision. **If G2A results are to be used in a thesis, a publication, or any formal
academic study, the relevant institution's research-ethics and participant-consent requirements
must be checked before the interviews are relied upon as publishable human-subject evidence.**

That check is a required step, not a formality, and it happens **before** recruitment where the
academic use is already intended — approval is not usually grantable retrospectively, and
interviews collected without it may be unusable however good they are.

This document does **not** determine whether formal review is required. That depends on the
institution, the jurisdiction, and the intended use, and none of those can be settled here.
Record the outcome of the check — required and obtained, required and pending, or assessed as
not required, with who assessed it and when — in the exit record (§22.1).

### 18.7 On honesty toward participants

Participants are told the interviewer builds research software in this area (L1) and are not
told the specific capabilities before Stage H (L3). This is **withholding, not deception**: the
purpose is stated truthfully, nothing false is asserted, and the full picture is offered at L4
to anyone who asks. If a participant asks at the outset what the system does, answer plainly
and record `PROTOCOL_BREACH = EARLY_DISCLOSURE` — an honest answer to a direct question outranks
the study design.

---

## 19. Recruitment message

**Describes the study, never the product.** No mention of AI, GraphRAG, chain comparison,
automatic investigation, graphs, agents, or any capability. No promise of grading, authenticity,
identity, or cross-book work.

### 19.1 Arabic

> **موضوع:** مشاركة في دراسة قصيرة عن طرق البحث في نصوص الحديث والأسانيد
>
> السلام عليكم ورحمة الله وبركاته،
>
> أنا [الاسم]، وبشتغل على دراسة صغيرة الهدف منها إني أفهم **إزاي الباحثون بيشتغلون فعليًا**
> دلوقتي لما يكون شغلهم متعلّق بنصوص الحديث وبالأسانيد: إيه المصادر اللي بيفتحوها، وإيه
> الخطوات اللي بيمشوا فيها، وإيه الحاجات اللي بتاخد وقت.
>
> لو حضرتك اشتغلت على حاجة من النوع ده — بحث، أو فصل من رسالة، أو تدريس، أو مشروع — يهمّني
> جدًا أسمع منك.
>
> الكلام هيكون عن **شغلك الحالي وطريقتك في العمل**، مش عن أي برنامج أو أداة، ومش محتاج أي
> معرفة تقنية أو خبرة بالذكاء الاصطناعي.
>
> المدة تقريبًا **٢٠ إلى ٣٠ دقيقة**، ويكون في الوقت اللي يناسبك، أونلاين أو تليفون.
>
> مش هيتنشر اسمك ولا جهة عملك، والمشاركة اختيارية بالكامل وممكن تتوقّف في أي وقت.
>
> لو الموضوع يناسبك، ياريت ترد على الرسالة دي وأنا أرتّب حسب وقتك. وشكرًا لوقتك على كل حال.
>
> [الاسم] — [وسيلة تواصل]

### 19.2 English — for DH / NLP researchers

> **Subject:** Short study on how researchers currently work with hadith texts and isnads
>
> Hello,
>
> I am [name], and I am running a small study to understand **how researchers actually work
> today** when their task involves hadith texts and isnads — which sources they open, what steps
> they go through, and which parts take the most time.
>
> If you have worked on something like this — a paper, a thesis chapter, teaching material, or
> a data project — I would value hearing about it.
>
> The conversation is about **your existing workflow**, not about any software or tool, and no
> technical or AI background is needed.
>
> It takes roughly **20–30 minutes**, at a time that suits you, online or by phone.
>
> Your name and institution will not be published, participation is entirely voluntary, and you
> can stop at any point.
>
> If you are willing, just reply to this message and I will work around your schedule. Thank you
> either way.
>
> [name] — [contact]

### 19.3 What must never appear in a recruitment message

AI · agent · GraphRAG · knowledge graph · chain comparison · shared narrators · automatic
analysis · narrator grading · authenticity · takhrij · "our system" · "our product" · any
screenshot · any capability name · any claim that the study will improve their research.

---

## 20. Participant introduction and consent script

Read at the start, in the participant's language, in under a minute. Plain, not legalistic.

### 20.1 Arabic

> شكرًا لوقتك. قبل ما نبدأ، أوضّح باختصار:
>
> أنا بشتغل على برمجيات بحثية في المجال ده، بس **مش هعرض عليك أي حاجة النهاردة**، والمقابلة
> دي **مش عرض لمنتج**. اللي يهمّني هو **طريقتك انت في الشغل** وإيه اللي بتعمله فعلًا.
>
> مفيش إجابة صح وإجابة غلط، ولو حاجة في شغلك كانت سهلة أو مش محتاجة مجهود، ده معلومة مفيدة
> ليّ زي أي حاجة تانية — بالعكس، ده من أهم اللي محتاج أعرفه.
>
> الكلام هياخد حوالي **٢٥ دقيقة**. ممكن تتوقّف في أي وقت، أو تعدّي أي سؤال، أو تطلب إننا
> نلغي المقابلة بعد ما تخلص ومش هستخدم أي حاجة منها.
>
> مش هسجّل اسمك ولا جهة عملك. هستخدم رمز زي «مشارك ١» بس. **ممكن أسجّل صوت المقابلة عشان
> أرجع للتفاصيل؟** ولو مش مريح، هكتب ملاحظات بإيدي وخلاص.
>
> ولو حبّيت أقتبس جملة بالنص، هرجعلك أستأذن الأول.
>
> عندك أي سؤال قبل ما نبدأ؟

### 20.2 English

> Thank you for your time. Before we start, briefly:
>
> I build research software in this area, but **I am not going to show you anything today** —
> this is not a product demo. What I am interested in is **how you work** and what you actually
> do.
>
> There are no right or wrong answers. If part of your work turns out to be easy or to need no
> effort, that is just as useful to me as a difficulty — in fact it is one of the more important
> things for me to learn.
>
> This will take about **25 minutes**. You can stop at any point, skip any question, or ask me
> afterwards to discard the whole conversation, in which case I will not use any of it.
>
> I will not record your name or institution — only a label like "Participant 1". **May I record
> the audio so I can go back to the details?** If you would rather I did not, I will take notes
> instead.
>
> If I want to quote you word for word anywhere, I will come back and ask you first.
>
> Any questions before we begin?

### 20.3 What the script must not say

That the system compares chains, finds shared narrators, uses a graph, uses AI, or investigates
anything · that participation will help build a tool they will get to use · anything implying
grading, authenticity, identity, or cross-book capability · any request for personal data beyond
role.

---

## 21. Interviewer checklist

One page. Read before each session; check afterwards.

| # | Rule |
|---|---|
| **IR-01** | **Ask about the past, not the hypothetical future.** "Tell me about the last time…", never "would you…" |
| **IR-02** | **Ask "and then what happened?"** It is the highest-yield sentence in the interview. Use it more than feels natural |
| **IR-03** | **You are the apprentice; they are the master.** You are learning their craft, not evaluating it |
| **IR-04** | **Do not complete their sentence and do not supply a word they have not used.** If they pause on a term, wait |
| **IR-05** | **Ask to see the artifact** where it exists and they are willing — the file, the table, the notes, the page. Watching beats recall |
| **IR-06** | **Tolerate silence.** Count to five before filling it |
| **IR-07** | **Do not teach capabilities and do not correct their methodology.** Not on hadith science, not on their tools |
| **IR-08** | **Do not defend Musnad.** If a concept probe is dismissed, record the dismissal and move on. It is the most valuable answer available |
| **IR-09** | **Distinguish behaviour from opinion.** "I opened three chains" is behaviour; "chains matter a lot" is opinion. Tag them differently (§3.2) |
| **IR-10** | **Distinguish observed pain from stated preference.** A workaround they actually built outranks a difficulty they describe |
| **IR-11** | **Never label anything during the session** — not "agentic", not "comparison", not a capability name. Classification happens afterwards, from the record |
| **IR-12** | **Capture exact terminology**, with the sentence around it. Do not translate or normalise in your notes |
| **IR-13** | **Pursue contradictions neutrally.** "Earlier you mentioned X, and just now Y — help me understand how those fit." Never "but you said…" |
| **IR-14** | **Do not enter Stage H until A–G are recorded** (§6.1). If you slip, mark `PROTOCOL_BREACH = CONCEPT_LEAK` honestly |
| **IR-15** | **Answer the §6.5 self-check in writing** before analysing the session |

---

## 22. Exit criteria

G2A exits in exactly one of three states. **No arbitrary participant count is required** — the
quality and relevance of the evidence decide — but **participant scarcity must be disclosed** in
the exit record.

| Exit state | Conditions | What follows |
|---|---|---|
| **`G2A_PASS_SUPPORTED`** | Enough real, admissible task evidence to proceed, and `PRODUCT_WEDGE_EVIDENCE = SUPPORTED` per §14.1 | Proceed to G2B. C09–C13 proceed as specified in G1 §8. The wedge remains evidence, not proof |
| **`G2A_PASS_LIMITED`** | `PRODUCT_WEDGE_EVIDENCE = LIMITED`. Includes the case where elicitation could not be completed, with `WEDGE_EVIDENCE_BASIS = NO_ELICITATION_ASSUMPTIONS_CARRIED` | **Engineering proceeds; it is not blocked.** G2B is written on assumptions **recorded as assumptions, not as findings** (G1 §20). The hypothesis is re-checked at G5 |
| **`G2A_REOPEN_G1`** | `PRODUCT_WEDGE_EVIDENCE = NOT_SUPPORTED`, or elicited real tasks materially contradict the frozen wedge | **Do not proceed to G3 tool design on the current positioning.** Reopen G1 §2 and §6 first. The structural capabilities may survive; the positioning is what is under revision |

### 22.1 The exit record — required contents

1. Exit state, dated.
2. `PRODUCT_WEDGE_EVIDENCE` with all §14.2 qualifiers.
3. `C14_USER_TASK_EVIDENCE` per §15.
4. Participant count, split A / B, and how many were reached through referral.
5. Admissible tasks, and the count of `TASK_SPECIFICITY = FAILED` records excluded.
6. The §14.3 per-hypothesis table.
7. The §16 negative-findings table, every row marked.
8. Recruitment effort actually expended — channels tried, approaches sent, replies received —
   so that "we could not reach participants" is a measured statement rather than an impression.
9. **Dependence structure** — which participants were `NONE` / `POSSIBLE` / `KNOWN` relative to
   each other, and how many independent sources that leaves (§4.6).
10. **Evidence-class split** — how many admissible tasks were `FIRST_HAND_TASK_EVIDENCE` and how
    many sources were `PROXY_CONTEXT_EVIDENCE` only (§3.2).
11. **Recency distribution** of admissible tasks, with `reconstruction_quality` (§4.7).
12. **Institutional research-ethics check** (§18.6) — required and obtained, required and
    pending, or assessed as not required; by whom, and on what date.
13. Open uncertainties carried into G2B.

### 22.2 What does not count as an exit

- The existence of this protocol. **Protocol-ready is not elicitation-complete.**
- Simulated, imagined, or model-generated participants, of any kind, for any reason.
- Web articles, papers, forum posts or dataset documentation treated as participant evidence.
  These may inform G2B's wording; they are **not** elicitation and may not set the wedge flag.
- A single interview with a non-qualifying participant.

---

## 23. Blank templates

All three are empty. **No template below may be filled with an imagined participant** (§24).
Copy them out of this document; do not fill them in place.

### 23.1 T1 — task record

One per elicited task. Reserved values: `UNKNOWN` · `NOT_ASKED` · `NOT_APPLICABLE` · `UNCLEAR`.

```yaml
# --- T1 TASK RECORD ---------------------------------------------------
participant_id:                 # P__
participant_role:               # PRIMARY_RESEARCHER | SECONDARY_STUDENT
                                # | SECONDARY_ENGINEER | SECONDARY_TEACHING
participant_field:              # coarse discipline only
task_id:                        # P__-T_
interview_date:
interview_language:

task_description_verbatim: |    # FILL THIS FIRST — their words, their language

task_goal:
task_trigger:
task_recency:                   # WITHIN_1_MONTH | WITHIN_6_MONTHS | WITHIN_12_MONTHS
                                # | OLDER_THAN_12_MONTHS | ONGOING   -- data, not a cutoff (§4.7)
reconstruction_quality:         # CONCRETE | PARTIAL | GENERIC       (§4.7)
task_specificity:               # PASSED | FAILED   (§8.1 — five criteria)

evidence_class:                 # FIRST_HAND_TASK_EVIDENCE | PROXY_CONTEXT_EVIDENCE   (§3.2)
                                # PROXY cannot establish a task, a pain point, SUPPORTED,
                                # or C14_USER_TASK_EVIDENCE                          (§3.2.1)
evidence_dependence:            # NONE | POSSIBLE | KNOWN            (§4.6)
dependence_with:                # [participant ids]
dependence_basis:               # which §4.6 indicator applies

input_objects:                  # []
current_workflow_steps:         # ordered; each: step, reason_for_next_step (verbatim if given)
  # - step:
  #   reason_for_next_step:
resources_used:                 # []
evidence_inspected:             # []

manual_operations:              # []
comparison_operations:          # [] — only if the participant described it
search_operations:              # []
identity_operations:            # [] — flag any U2/U7 contact

uncertainty_points:             # []
failure_modes:                  # []
workarounds:                    # []

output_required:
decision_or_use_of_output:
frequency_if_known:
estimated_effort_if_known:      # participant's own estimate only

natural_terminology:            # [{term:, gloss_if_given:, unprompted: true/false}]
pain_points:                    # []
pain_severity:                  # HIGH | MEDIUM | LOW | NONE | UNCLEAR
pain_severity_evidence:         # the §9.3 condition that justifies the level

structural_comparison_present:  # YES | NO | UNCLEAR
cross_hadith_reasoning_present: # YES | NO | UNCLEAR
cross_isnad_reasoning_present:  # YES | NO | UNCLEAR
dynamic_investigation_present:  # YES | NO | UNCLEAR
could_fixed_workflow_help:      # YES | NO | UNCLEAR
potential_agent_need:           # YES only if AG1..AG4 = YES *and* AG5 = NO
agent_test:                     # §11.1 — every criterion: YES is the agent-supporting answer
  AG1_dynamic_sequence_necessity:     # YES | NO | UNCLEAR
  AG2_discovery_dependent_next:       # YES | NO | UNCLEAR
  AG3_observation_dependent_change:   # YES | NO | UNCLEAR
  AG4_sufficiency_termination:        # YES | NO | UNCLEAR
  AG5_bounded_workflow_representable: # YES | NO | UNCLEAR   (§11.2)
                                      # YES => WORKFLOW evidence, not C14
  ag5_workflow_sketch:                # the workflow that would have covered it, or
                                      # why no enumerable branch tree does

musnad_capability_mapping:      # [C01..C15 | U1..U8 | MISSING_CAPABILITY | NONE]
mapping_rationale:
missing_capability_description: # only if MISSING_CAPABILITY

researcher_quote_or_paraphrase: # each classed VERBATIM_CONSENTED | PARAPHRASED
                                # | NOT_FOR_PUBLICATION   (§18.5)
                                # NOT_FOR_PUBLICATION never enters a tracked artifact
protocol_notes:                 # breaches, dropped stages, recording conditions
```

### 23.2 T2 — participant summary

One per participant. Concept-probe material lives **here**, never in T1.

```markdown
# --- T2 PARTICIPANT SUMMARY -------------------------------------------
participant_id:
role / profile:            # A | B1 | B2 | B3
field (coarse):
screener outcome:          # QUALIFIES-A | QUALIFIES-B | BORDERLINE-ADMITTED
borderline rule applied:   # §5.3, or NOT_APPLICABLE
referred_by:               # participant id, or NONE
evidence_dependence:       # NONE | POSSIBLE | KNOWN   (§4.6)
dependence_with / basis:   # participant ids + which indicator
session date / duration / language:
recording:                 # AUDIO_CONSENTED | NOTES_ONLY   (§18.4)
quotation consent:         # obtained for which quotes, or NONE   (§18.5)
stages completed:          # A B C D E F G H I — mark any dropped
tasks elicited:            # task ids, each with its evidence_class

## 1. First-hand tasks          [FIRST_HAND_TASK_EVIDENCE]
   (one line per task id, pointing to its T1 record)

## 1b. Proxy accounts           [PROXY_CONTEXT_EVIDENCE]
   (someone else's work. Per §3.2.1 these establish no task, no pain point,
    and cannot contribute to SUPPORTED or to C14_USER_TASK_EVIDENCE.)

## 2. Participant opinions      [PARTICIPANT_OPINION]

## 3. Concept reactions         [CONCEPT_REACTION]
| Probe | Response (verbatim / paraphrase) | Fit located? | Qualified or resisted? |
|---|---|---|---|
| CP1 |  | FIT_LOCATED / NO_FIT_LOCATED / UNCLEAR |  |
| CP2 |  |  |  |
| CP3 |  |  |  |
| CP4 |  |  |  |
| CP5 |  |  |  |

## 4. Terminology               (§13 — verbatim, with unprompted flag)

## 5. Negative signals from this participant   (§16 — NE ids)

## 6. Researcher inference      [RESEARCHER_INFERENCE]
   (kept strictly separate; never cited as evidence)

## 7. interviewer_reflexivity   (§6.5 — the four questions, answered)
   1. What did I hear that argues against the wedge?
   2. Which question would I not have asked if I wanted the opposite answer?
   3. Where did I complete a sentence or supply a word?
   4. Which notes are their words, and which are mine?

## 8. Protocol breaches         (§6.1 / §18.4)
```

### 23.3 T3 — cross-participant synthesis

One per study. Produced by §17.

```markdown
# --- T3 G2A SYNTHESIS -------------------------------------------------
date:
PARTICIPANTS_N:        (profile A: __ · profile B: __)
INDEPENDENT_SOURCES_N: (§4.6 — dependence clusters counted once; POSSIBLE listed separately)
ADMISSIBLE_TASKS_N:    (first-hand: __ · excluded for TASK_SPECIFICITY = FAILED: __)
PROXY_ONLY_SOURCES_N:  (§3.2.1 — contribute no task, pain point, or SUPPORTED)
RECENCY_DISTRIBUTION:  (§4.7 — with reconstruction_quality)
G1 baseline: musnad-g1-v1.1

## 0. Dependence structure              (§4.6)
| Participant | EVIDENCE_DEPENDENCE | With | Basis |
|---|---|---|---|
   Shared-incident retellings are named here and counted once in every table below.

## 1. What was elicited
   Clusters by job and operation (§17.B), each with its task ids.
   Counts written as "N of M participants in this elicitation" (§17.C),
   each carrying its dependence structure — "3 participants, 2 independent sources".

## 2. First-hand task evidence          [FIRST_HAND_TASK_EVIDENCE]

## 2b. Proxy context                    [PROXY_CONTEXT_EVIDENCE]
   Reported separately and never added to the counts in §2.

## 3. Strongest wedge evidence
   Task ids, and the hypothesis each bears on.

## 4. NEGATIVE EVIDENCE                 (§16 — every row marked)
| ID | Finding | Found? | Evidence — task ids | Notes |
|---|---|---|---|---|
| NE-1 | Chains read one at a time, rarely held together | FOUND / NOT_OBSERVED / UNCLEAR |  |  |
| NE-2 | Manual comparison already easy enough |  |  |  |
| NE-3 | Real pain is retrieval, not comparison |  |  |  |
| NE-4 | Real pain is grading / reliability (U1, U7) |  |  |  |
| NE-5 | Real pain is cross-book takhrij (U5) |  |  |  |
| NE-6 | Record-level provenance unnecessary |  |  |  |
| NE-7 | Dataset-internal narrator identity not interpretable |  |  |  |
| NE-8 | Structural output would not change a decision |  |  |  |
| NE-9 | Open evidence-directed investigation does not occur |  |  |  |

## 5. Capability mapping
### 5.1 Tasks → C01–C15
### 5.2 Tasks → U1–U8   — real needs V1 cannot serve (§10.3; does not expand V1)
### 5.3 Tasks → MISSING_CAPABILITY   (V1-legal operations G1 §8 lacks)
### 5.4 Tasks → NONE

## 6. Open uncertainties and unresolved contradictions

## 7. Per-hypothesis verdicts            (§14.3 table)

## 8. Flags
PRODUCT_WEDGE_EVIDENCE:   SUPPORTED | LIMITED | NOT_SUPPORTED
WEDGE_EVIDENCE_BASIS:     ELICITED_TASKS | NO_ELICITATION_ASSUMPTIONS_CARRIED
   SUPPORTED requires all four §14.1 conditions: first-hand · >=2 mutually
   independent participants (§4.6) · specificity passed and wedge-aligned ·
   uncoached, visible in Stages B-G. State the flag under both readings if any
   dependence is POSSIBLE.
C14_USER_TASK_EVIDENCE:   OBSERVED | INCONCLUSIVE | NOT_OBSERVED
   (if OBSERVED: the exact first-hand task id, the step evidencing AG-2 or AG-3,
    and the AG-5 reasoning for why no bounded workflow covers it)
justification: one paragraph against §14.3, not an impression

## 9. Terminology record                 (§13.4 — usages, not definitions)

## 10. Carried into G2B
   Candidate question wordings, each traceable to a task id · terminology ·
   strata touched · what remains assumption rather than finding.

## 11. Recruitment effort                (§22.1 item 8)
   Channels tried · approaches sent · replies · screened · excluded, with reasons.

## 12. EXIT STATE
   G2A_PASS_SUPPORTED | G2A_PASS_LIMITED | G2A_REOPEN_G1
```

---

## 24. What this phase must not do

| Prohibited | Why |
|---|---|
| **Simulate participants** — invent interviews, fabricate quotes, imagine responses, fill any template with a hypothetical user | It would make the wedge flag meaningless and every downstream decision unfalsifiable. This is the single most important prohibition in this document |
| Treat web articles, papers, forum posts or dataset documentation as participant evidence | They are literature, not elicitation (§22.2) |
| Declare the wedge `SUPPORTED` without real elicitation | §14.1 |
| Generate benchmark questions, strata, or gold labels | That is G2B |
| Design tools, APIs, schemas or state machines; write agent or LangGraph code | G1 §29, *what G2 must not do* |
| Touch retrieval, graph data, the linkage artifact, or attach Itqan | G1 §29 |
| Edit the frozen G1 contract | G1 is frozen at `musnad-g1-v1.1` |
| Coach participants toward Musnad's capabilities before their own tasks are recorded | G1 §20 elicitation rule; §6 here |
| Expand V1 because a participant asked for a U1–U8 capability | §10.3. The blocks are evidential, and elicitation supplies no identity evidence |
| Describe G2A output as validation, market validation, or product–market fit | §0, G1 §20 |
| Write an unbuilt capability in the past tense anywhere in this repository | Standing documentation rule; §17.1 |

---

## 25. Status

| | |
|---|---|
| **Phase** | G2A — Research Task Elicitation |
| **Type** | Research protocol |
| **Status** | **READY_FOR_ELICITATION** |
| **G1 baseline** | `musnad-g1-v1.1` — commit `a2da81ad0f4c327ca71d3d5a4ef4d19233ea0ee6` |
| **Product evidence** | `PRODUCT_WEDGE_EVIDENCE = NOT_YET_ASSESSED` |
| **C14 evidence** | `C14_USER_TASK_EVIDENCE = NOT_YET_ASSESSED` |
| **Participants screened** | 0 |
| **Participants interviewed** | 0 |
| **Task records** | 0 |
| **Exit state** | Not reached |

**Next action — human, not automated:** recruit and interview real target users under §19, §5
and §7, then produce T1, T2 and T3 and set the flags per §14, §15 and §22.

*This protocol is an instrument. It contains no findings, and G2A is not complete.*
