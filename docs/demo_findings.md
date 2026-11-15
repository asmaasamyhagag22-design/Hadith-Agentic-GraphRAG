# Demo Self-Test Findings (`docs/demo_findings.md`)

Playwright live end-to-end test against the Streamlit app (`http://127.0.0.1:8502`, `MUSNAD_DEMO_REPLAY=0`, Vertex AI `gemini-4-argon` + `gemini-3.8-flash` + `gemini-embedding-001`) across **20 brand-new natural Arabic questions** (verified zero normalized overlap against all 753 strings across `data/raw/*.jsonl` and all 10 recorded runs in `data/demo/recorded_runs.json`).

- **Live API calls spent in Step 5**: `23 Pro`, `16 Flash`, `33 Embed` (plus `0 Pro`, `0 Flash`, `24 Embed` in pre-flight router verification).
- **Overall Step 5 outcome**: **20 / 20** routed properly, **20 / 20** verified factually correct against `muslim_chunks.json` / `sanad_graph.sqlite` (or cleanly refused with `المصادر المتاحة لا تجيب عن هذا السؤال` on all 3 out-of-scope questions), `0` Python/browser crashes, `0` console/page errors, `0 px` horizontal overflow at desktop (`1400×960`) and mobile (`390×844`).
- **UI bugs caught during visual screenshot review & fixed directly**: 4 visual/UX bugs fixed in `app/components.py` and re-verified on replay screenshots before commit.
- **Open quality / validator / latency findings**: 6 items documented below with exact evidence and proposed fixes (pipeline retrieval, routing, prompts, and validators left untouched per rules).

---

## 1. Live Playwright Results (20 New Natural Questions)

Note on timing columns: **Pipeline Total** is the backend `TraceCollector` duration displayed in the UI summary card (`الزمن الكلي`); **UI E2E** measures click-to-render in Chromium including Streamlit WebSocket round-trip and rerun overhead.

| # | Category | Question | Route (Source, $p$) | Calls (P/F/E) | Correct? (Verified vs Matn / SQLite) | Pipeline Total / UI E2E | UI / Quality Issue? |
|---|---|---|---|---|---|---|---|
| Q01 | `text` | ما تعريف الغيبة في صحيح مسلم كما بيّنه النبي صلى الله عليه وسلم؟ | `text` (`classifier`, `0.167`) | 1 / 1 / 2 | **Yes** — cited `13708` (`ذكرك أخاك بما يكره... فإن لم يكن فيه فقد بهته`), sanad attached (`3` chains, أبو هريرة) | `14.06 s` / `16.39 s` | Extra blank lines before citation; LTR/RTL collapsed sidebar bug; reversed ID brackets `[10616, ...]` |
| Q02 | `text` | كيف يُطهَّر الإناء إذا شرب منه الكلب وفقًا لما ورد في صحيح مسلم؟ | `text` (`classifier`, `0.206`) | 1 / 0 / 1 | **Yes** — cited `7830, 7832, 7834, 7833, 7835` (سبع مرات أولاهن بالتراب / وعفروه الثامنة) | `48.82 s` / `50.90 s` | Hit API timeout -> `legacy_fallback` (`36.18 s`); numbered list `1.` clipped right border + 6-line gap |
| Q03 | `text` | ما فضل صلاة الجماعة في المسجد على صلاة الرجل وحده؟ | `text` (`classifier`, `0.027`) | 1 / 1 / 2 | **Yes** — cited `8678, 8644, 8649, 8650, 8647` (25/27 درجة + خطوات + دعاء الملائكة) | `18.97 s` / `19.74 s` | Numbered/bulleted list whitespace chasm + inline `(حديث رقم 8678)` phrasing alongside bottom citations |
| Q04 | `text` | ماذا يفعل المسلم إذا حلف على يمين ثم رأى غيرها خيرًا منها؟ | `text` (`classifier`, `0.025`) | 1 / 1 / 2 | **Yes** — cited `11420, 11423, 11424, 11419, 11426` (يترك يمينه ويأتي الذي هو خير ويكفر) | `14.29 s` / `15.25 s` | Collapsed sidebar overlay (UI bug #1) |
| Q05 | `chain` | ما سلسلة الإسناد الكاملة لحديث رقم 7285 من شيخ الإمام مسلم إلى الصحابي؟ | `chain` (`regex`, `1.000`) | 2 / 0 / 0 | **Yes** — exact 1-isnad chain (`قتيبة بن سعيد ← مالك بن أنس ← نافع بن مالك ← مالك بن أبي عامر ← طلحة بن عبيد الله`), cited `7285` | `11.74 s` / `13.62 s` | `.1/.2/.3` clipped right border + multi-line gaps in `<div class="musnad-answer-body">` |
| Q06 | `chain` | هل روى أبو هريرة حديث رقم 9025 أم رواه صحابي آخر وما إسناده؟ | `chain` (`regex`, `1.000`) | 2 / 0 / 0 | **Yes** — correctly denied أبو هريرة & named **البراء بن عازب بن الحارث** (`9025`, 1 chain) | `7.62 s` / `8.58 s` | Literal `**البراء بن عازب بن الحارث**` markdown asterisks visible + Companion-first order opposite chip strip |
| Q07 | `chain` | من هم رواة حديث رقم 9008 وكم عدد أسانيده المسجلة؟ | `chain` (`regex`, `1.000`) | 2 / 0 / 0 | **Yes** — `1` isnad, exact Golden Chain (`ابن عمر ← نافع ← مالك ← يحيى بن يحيى`, `9008`) | `80.43 s` / `81.27 s` | Severe Vertex `gemini-4-argon` tail latency (`80.41 s`); Companion-first list vs teacher-first chip strip |
| Q08 | `refusal` | ما هو النظام الغذائي المعتمد طبيًا لمرضى السكري من النوع الثاني؟ | `text` (`classifier`, `0.037`) | 1 / 1 / 2 | **Yes (Refusal)** — exact `REFUSAL`, orange refusal badge/card, `0` SQLite sanads | `13.11 s` / `14.20 s` | Collapsed sidebar overlay |
| Q09 | `refusal` | ما عقوبة انتهاك حقوق الملكية الفكرية وبراءات الاختراع في القانون التجاري المعاصر؟ | `text` (`classifier`, `0.027`) | 1 / 1 / 2 | **Yes (Refusal)** — exact `REFUSAL` | `12.58 s` / `13.63 s` | Collapsed sidebar overlay |
| Q10 | `refusal` | ما هي شروط الترشح لجائزة نوبل في الفيزياء ومعايير التحكيم العلمية فيها؟ | `text` (`classifier`, `0.025`) | 1 / 1 / 2 | **Yes (Refusal)** — exact `REFUSAL` | `95.28 s` / `96.28 s` | Severe Vertex `gemini-4-argon` generation latency spike (`85.37 s`) |
| Q11 | `mixed` | ما قصة الثلاثة الذين انطبقت عليهم الصخرة في الغار وما الأعمال الصالحة التي توسلوا بها في صحيح مسلم؟ | `text` (`classifier`, `0.229`) | 1 / 1 / 2 | **Yes** — full 3 deeds (بر الوالدين، العفة، أمانة الأجير) grounded on `14056` + `14058` | `42.56 s` / `43.44 s` | Slow generation (`33.30 s`) + `1.` list border clipping + multi-line gaps |
| Q12 | `mixed` | ما حكم سباب المسلم وقتاله وهل هما في منزلة واحدة من الإثم أم أحدهما أعظم كما ورد في صحيح مسلم؟ | `text` (`classifier`, `0.180`) | 1 / 1 / 2 | **Yes** — distinguished فسوق (سباب) vs كفر (قتال) from `7404` (+ 4 SQLite chains) | `17.45 s` / `18.69 s` | Collapsed sidebar overlay |
| Q13 | `typos` | هل تقبل صلاه بغير طهور او صدقه من قلول؟ | `text` (`classifier`, `0.023`) | 1 / 1 / 2 | **Yes** — recovered `غلول` from `قلول`, cited `7718` (`3` chains) | `13.20 s` / `14.17 s` | Collapsed sidebar overlay |
| Q14 | `typos` | مافضصل ركعتي الضحي علي كل سلامي من الناس؟ | `text` (`classifier`, `0.051`) | 1 / 1 / 2 | **Yes** — recovered `فضل الضحى على كل سلامى`, cited `8842` (`1` chain via أبو ذر) | `48.62 s` / `49.40 s` | Slow generation (`39.96 s`) + `1 أسانيد` plural grammar in trace |
| Q15 | `typos` | ماهو اجر من صام ستا من شوال بعد رمضن في صحييح مسلم؟ | `text` (`classifier`, `0.204`) | 1 / 1 / 2 | **Yes** — cited `9919` (`كصيام الدهر`, `3` chains via أبو أيوب الأنصاري) | `13.02 s` / `14.12 s` | Collapsed sidebar overlay |
| Q16 | `colloquial` | لو الواحد وهو صايم حد جه شتمه أو اتخانق معاه في الشارع يتصرف إزاي حسب السنة؟ | `text` (`classifier`, `0.038`) | 1 / 1 / 2 | **Yes** — cited `9864` & `9867` (`إني صائم / إني امرؤ صائم`, لا يرفث ولا يسخب) | `16.83 s` / `17.77 s` | Collapsed sidebar overlay |
| Q17 | `colloquial` | هو الحلفان الكتير في البيع بيزوّد البركة ولا بيمحقها في الكلام النبوي؟ | `text` (`classifier`, `0.050`) | 1 / 1 / 2 | **Yes** — cited `11274` & `11273` (`الحلف منفقة للسلعة ممحقة للربح`) | `16.19 s` / `17.19 s` | Collapsed sidebar overlay |
| Q18 | `very_short` | ساعة يوم الجمعة | `text` (`classifier`, `0.130`) | 1 / 1 / 2 | **Yes** — cited `9142, 9138, 9139, 9143, 9144` (فضلها وخفتها وما بين جلوس الإمام) | `15.97 s` / `17.21 s` | Unlinked `9139` & `9144` rendered raw enum `VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK`; list clipping |
| Q19 | `very_short` | شفاعة القرآن لأصحابه | `text` (`classifier`, `0.070`) | 1 / 1 / 2 | **Yes** — cited `9043` & `9045` (يأتي شفيعًا لأصحابه والزهراوين غمامتان) | `15.97 s` / `17.21 s` | Collapsed sidebar overlay |
| Q20 | `very_long` | بينما كنت أصلي صلاة رباعية الظهر في المنزل أصابني شك قوي... | `text` (`classifier`, `0.124`) | 1 / 1 / 2 | **Yes** — cited `8449` (يطرح الشك ويبني على ما استيقن ويسجد سجدتين قبل السلام) | `14.65 s` / `15.71 s` | Minor HyDE stray English token (`أthreads ثَلَاثًا` in trace snippet; retrieval unaffected, `8449` rank #1) |

---

## 2. UI Bugs Fixed Directly in Step 5

All visual issues observed in Playwright screenshots were fixed cleanly in `app/components.py` and covered by unit tests in `tests/test_app_ui.py`:

1. **Collapsed Sidebar RTL Overlap Bug (`[data-testid="stSidebar"]`)**:
   - **Symptom**: Setting `direction: rtl` globally on `html, body, .stApp` reversed `[data-testid="stAppViewContainer"]` so Streamlit placed the sidebar on the right (`x=1100`) while still applying its LTR collapse transform (`translateX(-300px)`), sliding the collapsed sidebar strip vertically over the main page text (`Q01`, `Q02`, `Q05`, `Q08`, `Q11`, `Q18`).
   - **Fix**: Scoped `[data-testid="stAppViewContainer"] { direction: ltr; }` so native sidebar slide/collapse works offscreen left, kept `[data-testid="stMain"], .stMainBlockContainer { direction: rtl; text-align: right; }` and `[data-testid="stSidebar"] { direction: rtl; text-align: right; }`, plus `[data-testid="stSidebar"][data-collapsed="true"] { visibility: hidden !important; pointer-events: none !important; overflow: hidden !important; }`. Re-verified via Playwright (`rect.x=-300, width=0, visibility='hidden'` when collapsed; clean slide-in when expanded).
2. **Markdown-in-HTML List Clipping, Giant Vertical Gaps & Raw `**bold**` / Backtick Leaks**:
   - **Symptom**: Putting raw `html.escape(answer)` inside `<div class="musnad-answer-body">` with `white-space: pre-wrap` caused Streamlit's CommonMark parser to split blank-line lists into `<ol><li>` whose ordinal numbers (`1.`, `2.`) clipped the right card border while `pre-wrap` expanded newlines into ~6-line gaps; inline `**...**` and `` `...` `` also rendered literally (`Q06`, replay banner).
   - **Fix**: Added `format_answer_body_html` and `_format_inline_markdown_html` in `app/components.py` to safely convert escaped text into semantic `<p>`, `<ol class="musnad-answer-list">`, `<ul class="musnad-answer-list">`, `<strong>`, and `<code dir="ltr">` with `white-space: normal` and `padding-inline-start: 2.1rem`.
3. **Raw English SQLite Linkage Status in Arabic Sanad Cards**:
   - **Symptom**: In `Q18`, hadiths `9139` and `9144` had zero recorded MIS links and displayed raw internal code `VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK` directly in the Arabic UI card and trace panel.
   - **Fix**: Added `SANAD_STATUS_ARABIC_UI` localization in `app/components.py` (mapping missing/ambiguous/error statuses to clear Arabic explanations).
4. **Trace Bidi Bracket Reversal & Singular Chain Grammar**:
   - **Symptom**: In `Q01`–`Q20`, `أعلى 5 أحاديث: [13708, 14302, ...]` visually reordered IDs in RTL bidi, and 1-chain hadiths displayed `"1 أسانيد"`.
   - **Fix**: Wrapped trace ID arrays and tool arguments in `<code dir="ltr">...</code>` and added `_format_isnad_count_ar` (`إسناد واحد`, `إسنادان`, `N أسانيد`), keeping the prompt-specified card badge `"+N طرق أخرى"` intact.

---

## 3. Open Quality, Validator, Routing & Latency Findings (Not Modified Tonight)

Per task rules, **no changes** were made to retrieval, routing, prompts, or validators. The following verified issues remain open for decision:

1. **Validator False Positive on Multi-Chain Numbered Answers (`run_03_chain_id_7306` from Step 3)**:
   - **Evidence**: When asking `"ما أسانيد حديث رقم 7306 ومن الصحابي الذي رواه؟"` (which has `isnad_count = 4`), `gemini-4-argon` produced accurate chains formatted as `1. **الإسناد الأول:** ...` ending with `(المصدر: صحيح مسلم، حديث رقم 7306)`. `validate_answer` ran `loose_cited_ids(raw)` and extracted `{1, 7306}` from the bare ordinal `"1."`, raising `OUT_OF_CONTEXT_CITATION` -> retry -> false refusal (`data/demo/recorded_runs.json` trace for `run_03` vs accurate `run_07_narrator_7294`).
   - **Proposed Fix**: Tighten `LOOSE_CITATION` in `src/answer.py` to require hadith-reference context (`حديث`, `رقم`, `مسلم`, `المصدر`) rather than matching standalone ordinals at the start of list items.
2. **Vertex Generation Tail Latency Spikes & Uncaught Timeout -> 36s Local Legacy Fallback (`Q02`, `Q07`, `Q10`, `Q11`, `Q14`)**:
   - **Evidence**: While `15/20` live questions finished end-to-end in `7.62–18.97 s`, `Q02` hit an upstream retrieval timeout (`Flash: 0`) and triggered `legacy_fallback` (`36.18 s` loading/running local E5 + CrossEncoder; total `48.82 s`), and `gemini-4-argon` stalled on generation in `Q07` (`80.41 s`), `Q10` (`85.37 s`), `Q11` (`33.30 s`), and `Q14` (`39.96 s`). `Q20` also exhibited a minor multilingual Flash HyDE token artifact (`أthreads ثَلَاثًا`), though retrieval still placed ground-truth `8449` at rank #1.
   - **Proposed Fix**: Add one bounded short-timeout retry with exponential backoff on Vertex API calls before falling back to `legacy` (local) / `replay` (`MUSNAD_CLOUD=1`), and strip stray non-Arabic characters in `generate_hyde` output.
3. **Unlinked Duplicate-Matn Hadiths in Graph Coverage (`Q18`: `9139`, `9144`)**:
   - **Evidence**: Querying `"ساعة يوم الجمعة"` returned `9142, 9138, 9139, 9143, 9144` from book 10 (الجمعة), of which `9139` and `9144` have `VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK` (`0` chains) in `sanad_graph.sqlite` even though sibling variants `9142`/`9138`/`9143` are linked.
   - **Proposed Fix**: Audit unlinked contiguous Friday-hour variant IDs (`9139`, `9144`) in `sanad_graph` linkage calibration.
4. **Narrator-Direction Mismatch Between Agent Prose and Sanad Strip (`Q06`, `Q07`)**:
   - **Evidence**: When the user did not specify ordering (`Q06`, `Q07`), the LLM listed narrators Companion-first (`أبو إسحاق ... ← البراء بن عازب` reversed vs `شيخ مسلم ← الصحابي`), whereas `render_sanad_chain_html` always displays horizontal chips from **Muslim's teacher to the Companion**.
   - **Proposed Fix**: Align `AGENT_SYSTEM_PROMPT` output ordering guidance to list chains from Muslim's teacher down to the Companion (`←`), matching both `format_sanad_chain` and the UI chips.
5. **Startup Performance When `sentence_transformers` / `transformers` Are Top-Level Imported**:
   - **Evidence**: Streamlit's `local_sources_watcher` scans `transformers` submodules (`2000+` `ModuleNotFoundError: No module named 'torchvision'` logs, adding ~18 s on cold `streamlit run` startup) when `src/utils.py` and `src/rerank.py` import `sentence_transformers` at module import time.
   - **Proposed Fix**: Addressed cleanly for runtime in Step 6a via lazy imports inside `get_model()` / `get_reranker()` and `--server.fileWatcherType=none` in production.
6. **Mixed Text + Companion Attribution Topic Queries Route to `chain` (Higher Pro Cost) When Phrased Explicitly**:
   - **Evidence**: During pre-flight router verification, two-part questions mentioning companion attribution alongside matn story (`"مع ذكر من رواها"`, `"ومن الصحابي الذي حدّث به"`) scored `p=0.647` and `p=0.767` in `Router v3` (`chain` -> full `run_agent` multi-step loop), whereas matn-and-ruling mixed questions (`Q11`, `Q12`) scored `p=0.229` and `p=0.180` (`text`).
   - **Proposed Fix**: Expected behavior given `v3` intent design (`attach_sanad` already enriches all cited text answers with SQLite sanads); document for users that asking explicit Companion/narrator names triggers tool-agent lookup.
