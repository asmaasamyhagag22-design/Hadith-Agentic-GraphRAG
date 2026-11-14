# EXPERIMENTS

**هذا الملف هو المصدر الوحيد للأرقام في المشروع.** أي رقم في
`README.md` منقول من هنا؛ لو اختلفا فالصحيح ما هنا.

كل رقم مقيس، ومعاه حجم العينة والإعداد اللي طلّعه. النتايج
السلبية مكتوبة زي الإيجابية — التجربة اللي ما نفعتش معلومة
برضه.

**النطاق.** الملف بيغطي مرحلتين مقيستين، وكل واحدة ليها
لقطتها:

* **الأقسام 1–9** — مسار الاسترجاع والإجابة النصية. أرقامها
  كلها بتخص لقطة القياس المذكورة تحت، والتاريخ اللي فيها
  يخص اللقطة دي وحدها مش المستند كله.
* **الأقسام 10–19** — الربط وتحليل الهوية والجراف
  الاستنتاجي. كل قسم فيها بيسجّل قياسه ولقطته بنفسه.

**اللي مبني فعلًا:** مسار RAG الاسترجاعي · جراف السند
الاستنتاجي على هويات MIS · جسر الحديث المحلي ↔ MIS · سطح
سياق السند القرائي.

**اللي لسه مش مبني:** هوية الراوي التاريخية (بوابة فرز
الكيانات مقفولة) · ربط تقييمات الجرح والتعديل من Itqan ·
أي راوتر أو LangGraph أو وكيل. مفيش أرقام هنا لأي حاجة
من دول.

---

## نسخة القياس — كل رقم في هذا الملف يخص هذه النسخة بالضبط

**تاريخ القياس:** 2026-08-09

**مجموعات التقييم (مجمَّدة بالبصمة):**

| الملف | عدد المدخلات | المقيسة | sha256 (أول 16) |
|---|---|---|---|
| `data/raw/golden.jsonl` | 33 — 27 matn · 3 refusal · 3 narrator | **27** | `a7ec05f48ec0491a` |
| `data/raw/synthetic_eval.jsonl` | 224 | 224 | `4bec52d5a56a8fc8` |
| `data/raw/muslim.json` | 7,459 حديث | — | `63a99e46155dc6e9` |

**إعداد النظام:**

| | |
|---|---|
| الفهرس | 7,110 وثيقة من 7,459 حديث (7,570 chunk ناقص 460 إحالة) |
| المتجهات | `intfloat/multilingual-e5-base`، FAISS `IndexFlatIP` |
| اللفظي | BM25 بتطبيع عربي |
| الدمج | RRF على المراتب، `k=60`، مرشحون = 50، أوزان متساوية |
| إعادة الترتيب | `mmarco-mMiniLMv2-L12` على أول 10 |
| التوليد | `gemini-2.5-pro` عبر Vertex، `temperature=0` |

`src/check_docs.py` بيتحقق إن البصمات دي لسه مطابقة للملفات، وبيفشل لو اتغيرت من غير ما الأرقام تتحدّث.

**السجل القانوني للنتايج.** الكتلة دي هي اللي جداول README
بتتقارن بيها خانة بخانة. المقارنة على (جدول، صف، مقياس) مش
على الرقم لوحده، وكل نسبة معاها المقام اللي اتحسبت عليه —
عشان رقم صحيح منسوب لمقياس غلط ما يعدّيش. `section=` بيربط
كل صف بقسمه هنا، و`check_docs` بيتأكد إن القيمة موجودة في
القسم ده بالذات.

المقامات مش واحدة عبر الجدول، وده مقصود ومقروء من
`answer_eval.report()`: الاستشهاد الصحيح بيتحسب على الأسئلة
القابلة للإجابة (27)، والاستشهاد الباطل والخاطئ على كل
الأسئلة (30)، والرفض الكاذب على الأسئلة اللي وصل فيها
الحديث الصح للسياق (27 للمسار المرقّى، 22 مع إعادة الترتيب، 20 للهجين).

```canonical-results
# table | row_id | README row label | meta | metric=value[@denominator]
retrieval_golden | upgraded | Upgraded (HyDE + Gemini-001) | dataset=golden.jsonl n=27 section=29 | hit@1=85%@27 hit@3=100%@27 hit@5=100%@27 hit@10=100%@27 MRR=0.926
retrieval_golden | hybrid_rerank | Hybrid + rerank (baseline) | dataset=golden.jsonl n=27 section=6 | hit@1=56%@27 hit@3=74%@27 hit@5=81%@27 hit@10=85%@27 MRR=0.665
retrieval_golden | hybrid_rrf | Hybrid (RRF) | dataset=golden.jsonl n=27 section=5 | hit@1=44%@27 hit@3=67%@27 hit@5=74%@27 hit@10=85%@27 MRR=0.565
retrieval_golden | dense_matn | Dense only | dataset=golden.jsonl n=27 section=5 | hit@1=41%@27 hit@3=56%@27 hit@5=59%@27 hit@10=63%@27 MRR=0.493
retrieval_golden | bm25_matn | BM25 only | dataset=golden.jsonl n=27 section=5 | hit@1=33%@27 hit@3=59%@27 hit@5=63%@27 hit@10=67%@27 MRR=0.464
retrieval_synthetic | upgraded | Upgraded (HyDE + Gemini-001) | dataset=synthetic_eval.jsonl n=224 section=29 | hit@1=41%@224 hit@3=64%@224 hit@5=73%@224 hit@10=84%@224 MRR=0.545
retrieval_synthetic | hybrid_rerank | Hybrid + rerank (baseline) | dataset=synthetic_eval.jsonl n=224 section=6 | hit@1=27%@224 hit@3=37%@224 hit@5=41%@224 hit@10=44%@224 MRR=0.330
retrieval_synthetic | hybrid_rrf | Hybrid (RRF) | dataset=synthetic_eval.jsonl n=224 section=5 | hit@1=18%@224 hit@3=30%@224 hit@5=37%@224 hit@10=44%@224 MRR=0.256
retrieval_synthetic | dense_matn | Dense only | dataset=synthetic_eval.jsonl n=224 section=5 | hit@1=14%@224 hit@3=20%@224 hit@5=26%@224 hit@10=32%@224 MRR=0.189
answer_quality | upgraded | Upgraded (3-run mean) | dataset=golden.jsonl section=29 | Correct_citation=96%@27 Invalid_citation_attempts_(raw)=0%@30 Missing_citation_attempts_(raw)=0%@30 Non-gold_citation_from_context=3.3%@30 False_refusals=4%@27 Correct_refusals=6/9
answer_quality | hybrid_rerank | Hybrid + rerank (baseline, 3-run mean) | dataset=golden.jsonl section=29 | Correct_citation=81%@27 Invalid_citation_attempts_(raw)=0%@30 Missing_citation_attempts_(raw)=0%@30 Non-gold_citation_from_context=8%@30 False_refusals=0%@22 Correct_refusals=3/3
answer_quality | hybrid_rrf | Hybrid (RRF) | dataset=golden.jsonl section=29 | Correct_citation=63%@27 Invalid_citation_attempts_(raw)=0%@30 Missing_citation_attempts_(raw)=0%@30 Non-gold_citation_from_context=23%@30 False_refusals=0%@20 Correct_refusals=3/3
sanad_attachment | default_3runs | Sanad-attached answers (3 runs) | dataset=golden.jsonl section=30 | Attachment_coverage=95.9%@220 Unique_hadith_coverage=97.4%@76 Median_latency_ms=2.226 p95_latency_ms=3.444
```

**البصمات canonical.** بتتحسب بعد تحويل `CRLF` إلى `LF`، عشان
نفس اللقطة النصية تدّي نفس البصمة على ويندوز ولينكس وماك. قبل
كده الـ checkout هو اللي كان بيحدّد البصمة، فالبوابة كانت
بتفشل على نسخة تانية من نفس الـ commit من غير ما تتغير أي
بيانات. نهاية السطر هي الفرق الوحيد اللي الهاش بيتجاهله —
أي تغيير في محتوى أو ترتيب أو رقم حديث بيغيّره، وده متغطّى
باختبارات في `tests/test_check_docs.py`.

**مفيش أي بيانات تقييم اتغيرت في الإصلاح ده.** بصمتا
`golden.jsonl` و`synthetic_eval.jsonl` هما نفسهما المسجّلين
من الأول، والأرقام كلها اتعاد إنتاجها بالظبط عليهما. اللي
اتحدّث هو بصمة `muslim.json` بس — من صيغة الـ CRLF للصيغة
الـ canonical، من غير ما يتغير حرف في الملف. الإفصاح تحت عن
تعديل الـ ground truth باقي زي ما هو. (جدول التجربة 10
بيسجّل بصمات البايتات الخام وقت قياس الربط، فبصمة
`muslim.json` هناك مختلفة عن دي عن قصد.)

### ⚠ إفصاح: الـ ground truth اتعدّل بعد رؤية نتائج الموديل

**المجموعة اليدوية مش مُعمّاة (not blind).** أثناء التطوير، فحص
النتايج السيئة كشف أخطاء حقيقية في المرجع، واتعدّلت **بعد**
رؤية مخرجات النظام. كل تعديل متحقَّق منه بالبحث في نص المتن،
لكن الترتيب الزمني ده يرفع الأرقام ولازم يتقال:

| السؤال | التعديل | متى |
|---|---|---|
| فضل سورة الكهف يوم الجمعة | كان مرجعه 9052 خطأً؛ لا وجود للحديث في مسلم أصلًا فتحوّل لسؤال رفض | بعد رؤية النتايج |
| كم عدد ركعات الوتر | 8889 و8927 و8928 أضيفت — النظام أرجع 8928 «الوتر ركعة من آخر الليل» في المركز 4 وكان خارج القائمة | بعد رؤية النتايج |
| حكم صيام عاشوراء | 9802–9821 أضيفت — كلها تحمل الحكم، والقائمة كانت رقمًا واحدًا | بعد رؤية النتايج |
| حكم الغش في البيع | **10762 حُذف** — طابق «من غش» نصيًا وهو «من غشيانهن»، كلمة مختلفة | بعد رؤية النتايج |
| ما هي الأحاديث عن النية | السؤال أُعيدت صياغته ليصير محدِّدًا؛ الفضفاض لا مرجع قاطع له | بعد رؤية النتايج |
| شرط كمال الإيمان | 7355 أضيف بنفس المعنى بلفظ آخر | بعد رؤية النتايج |

الـ 21 سؤالًا الباقية لم تُمَس بعد كتابتها. **المجموعة المولَّدة
(224) لم تُعدَّل إطلاقًا بعد التوليد** — لا سؤال حُذف ولا مرجع
غُيِّر بناءً على أداء أي إعداد، فهي المجموعة المُعمّاة الوحيدة،
وهي المستخدمة في كل قرارات الاختيار.

**الخلاصة العملية:** أرقام المجموعة اليدوية سقفها متفائل بقدر
غير مقيس. الاتجاهات بين الإعدادات مؤكَّدة على المجموعة المُعمّاة.
أي مقارنة مستقبلية لازم تكون مع نفس البصمة أعلاه، وإلا فالفرق
قد يكون في البيانات لا في النظام.

---

## مجموعات التقييم

| المجموعة | الحجم | كيف بُنيت | تُستخدم لـ |
|---|---|---|---|
| `data/raw/golden.jsonl` | 33 (27 مقيسة + 3 رفض + 3 رواة) | مكتوبة بإيد ومتحقَّق منها بالبحث في المتن | **الإبلاغ** — الأرقام اللي تتقال |
| `data/raw/synthetic_eval.jsonl` | 224 | Gemini يولّد سؤال من متن كل حديث (known-item) | **الاختيار** بين الإعدادات |

**تحيّز معلن في المجموعة المولَّدة:** الأسئلة مشتقة من المتون
فبتشارك ألفاظها، وده بيحابي BM25. مخفَّف بفلتر تداخل معجمي
(حد 60%، المتوسط الفعلي 0.26) وببرومبت بيمنع إعادة استخدام
الألفاظ المميزة. الميل باقٍ: BM25 ‏hit@1 ‏18% مقابل 14% للدلالي.

**تحيّز معلن في المجموعة اليدوية:** أسئلتها عن أحاديث مشهورة
بمتون مميزة، فهي **أسهل بشكل منهجي** من عيّنة عشوائية —
`hit@5` عليها 74% مقابل 37% على المولَّدة بنفس النظام.
المستويات المطلقة مش قابلة للمقارنة بين المجموعتين؛ الاتجاهات
هي اللي بتتقارن.

---

## 1. صيغة تمثيل الوثيقة

السؤال: الحديث يدخل الفهرس بسنده، أم بمتنه، أم بمتنه مسبوقًا
بعنوان الباب؟

**golden — 27 سؤال**

| الصيغة | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| السند + المتن | 22% | 33% | 52% | 59% | 0.316 |
| **المتن فقط** | **41%** | **56%** | **59%** | 63% | **0.493** |
| عنوان الباب + المتن | 37% | 44% | 52% | 63% | 0.436 |

**synthetic — 224 سؤال**

| الصيغة | hit@1 | hit@5 | MRR |
|---|---|---|---|
| السند + المتن | 11% | 22% | 0.157 |
| المتن فقط | 14% | 26% | 0.189 |
| عنوان الباب + المتن | 15% | 26% | 0.199 |

**القرار: المتن فقط.** سلسلة الرواة ضوضاء بالنسبة لسؤال عن
المعنى — شيلها رفع MRR بنسبة 56% على المجموعة اليدوية.

**فرضية مكذَّبة:** توقّعنا إن عنوان الباب هيساعد الأسئلة
الموضوعية. الأرقام تقول لأ — على المجموعة اليدوية أسوأ من
المتن وحده. السبب ظهر في الفحص: العنوان بيسيطر على المتّجه
فبترجع أحاديث من **نفس الكتاب** بأرقام متلاصقة، الكتاب الصح
والحديث الغلط.

---

## 2. التشكيل

`intfloat/multilingual-e5-base` بيقطّع العربي المشكول لحروف
مفردة:

```
بتشكيل   : ['▁ح','َ','د','َّ','ث','َ','ن','ِ','ي','▁أ','َ','ب','ُ','و']
من غير   : ['▁حدث','ني','▁أبو','▁خ','يث','مة','،','▁زه','ير','▁بن','▁حرب']

عدد التوكنز: 92,305 مقابل 25,676  →  3.59×
```

**A/B على نفس الصيغة — 9 أسئلة** (نسخة مبكرة من المجموعة اليدوية)

| | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| بالتشكيل | 33% | 33% | 56% | 0.368 |
| **من غير تشكيل** | 33% | **56%** | **67%** | **0.429** |

**القرار: الفهرسة على النص المجرَّد، والعرض بالنص المشكول.**

**لكن المكسب مش موحَّد:** سؤال «كفالة اليتيم» كان في المركز
الأول **بالتشكيل** واختفى من غيره. التشكيل بيحمل إشارة مفيدة
لما اللفظ نادر — وده جزء من مبرر البحث الهجين.

أثر جانبي: الحد 450 توكن بقى يتقاس على النص المجرَّد، فعدد
الـ chunks نزل من 10,046 لـ 7,570 لنفس الـ 7,459 حديث. يعني
2,587 حديث كانوا بيتقطّعوا من غير داعي.

---

## 3. فصل السند عن المتن

الأنماط الأصلية كانت مكتوبة بتشكيل ثابت و`.find()` بيقارن
حرفيًا، فكانت بتفشل تقريبًا دايمًا.

| | نسبة الفصل الناجح (أجزاء أولى) | نتايج مشوَّهة |
|---|---|---|
| أنماط مشكولة، مطابقة حرفية | **0.1%** (9 / 7,459) | 49 |
| تطبيع + حدود كلمات + مسار احتياطي | **80.8%** | **0** |

التحسينات: المطابقة على نسخة مطبَّعة مع خريطة مواضع ترجع
للنص الأصلي؛ حدود كلمات تمنع مطابقة «ان رسول الله» جوه
«كان رسول الله»؛ مسار احتياطي للأحاديث الموقوفة يدوّر على
آخر حلقة سند ثم أول فعل قول؛ وحارس يرجّع النص كامل لو الناتج
أقصر من 25 حرف.

**نافذة السند = 800 حرف.** توزيع طول السند في الحالات
المؤكدة: الوسيط 206، المئين 90 = 406، المئين 98 = 801. من غير
الحد ده كانت الأحاديث الطويلة تتقص جوه المتن لأن «عن» و«قال»
بيتكرروا في السرد.

---

## 4. المتابعات بلا متن

460 chunk من 7,570 (**6.1%**) نصها إحالة لحديث سابق:
«عن النبي ﷺ بنحو حديثهم»، «بهذا الإسناد». بتتخزّن ومتشالش
(ليها أرقام في المصدر) لكن **مستبعدة من فهرس البحث**.

الكاشف بيشترط شرطين معًا: متن أقصر من 150 حرف **و** صيغة
إحالة صريحة. الطول وحده كان بيوقّع أجزاء فيها محتوى حقيقي.

---

## 5. البحث الهجين

BM25 (بتقطيع عربي: تطبيع، وشيل «ال» التعريف) + بحث دلالي،
مدموجين بـ Reciprocal Rank Fusion على المراتب لا الدرجات.

**golden — 27 سؤال**

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| دلالي (متن) | 41% | 56% | 59% | 63% | 0.493 |
| BM25 (متن) | 33% | 59% | 63% | 67% | 0.464 |
| **هجين** | **44%** | **67%** | **74%** | **85%** | **0.565** |

**synthetic — 224 سؤال**

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| دلالي (متن) | 14% | 20% | 26% | 32% | 0.189 |
| BM25 (متن) | 18% | 25% | 29% | 37% | 0.228 |
| **هجين** | 18% | **30%** | **37%** | **44%** | **0.256** |

**الدليل على التكامل:** سؤال «فضل كفالة اليتيم» لم يظهر في
أول 10 عند أي من الباحثين منفردًا، وظهر في **المركز 3** بعد
الدمج — الإشارتان الضعيفتان اجتمعتا.

**التكلفة:** الهجين بيخسر لما باحث يكون واثق والتاني أعمى.
«من دل على خير» كان المركز 1 في BM25 وخرج من أول 10 بعد
الدمج. ودي حجة إضافية للـ reranker: ندمج للـ recall ونعيد
الترتيب للـ precision.

---

## 6. إعادة الترتيب (Reranker)

إعادة ترتيب أول **10** نتايج من الهجين.

**ليه 10؟ (مقيس، وتصحيح لصياغة قديمة).** كان مكتوب هنا إن
`hit@10 = hit@20 = hit@50 = 89%`، وده **غلط**: سقف الهجين
على المجموعة اليدوية هو `hit@10 = 23/27 = 85.19%` بينما
`hit@20 = hit@50 = 24/27 = 88.89%` — أي فرق **سؤال واحد**،
وهو نفس الفرق اللي القسم 7 بيقول إنه ضوضاء.

التعميق ما بيحسّنش الترتيب الأعلى. بنفس الـ reranker
(mmarco) مع تغيير عمق المرشحين وحده:

| top_k_in | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| **10** (المستخدم) | 15/27 | 20/27 | **22/27** | 0.665 |
| 20 | 15/27 | 20/27 | 21/27 | 0.671 |
| 50 | 15/27 | 20/27 | 20/27 | 0.658 |

`hit@1` واحد بالظبط في التلاتة، و`hit@5` **بينزل** كل ما
القائمة تعمق. فالسبب الحقيقي للعمق 10 هو دقة مقيسة أعلى في
أول 5 وزمن أقل، مش تساوي السقوف. القيمة المستخدمة في الكود
(`DEFAULT_TOP_K_IN = 10`) ما اتغيرتش.

**golden — 27 سؤال**

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR | ث/سؤال |
|---|---|---|---|---|---|---|
| هجين | 44% | 67% | 74% | 85% | 0.565 | — |
| + bge-reranker-v2-m3 (568M) | **67%** | **81%** | **85%** | 85% | **0.738** | 3.0–6.2 |
| + mmarco-mMiniLMv2 (33M) | 56% | 74% | 81% | 85% | 0.665 | **0.51** |

**synthetic — 224 سؤال**

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR | ث/سؤال |
|---|---|---|---|---|---|---|
| هجين | 18% | 30% | 37% | 44% | 0.256 | — |
| + bge-reranker-v2-m3 | 27% | 39% | 42% | 44% | 0.338 | 5.4 |
| + mmarco-mMiniLMv2 | 27% | 37% | 41% | 44% | 0.330 | **0.58** |

**فرضية مكذَّبة:** توقّعنا إن الـ cross-encoders المتدربة على
بحث ويب حديث ممكن ما تنفعش مع الحديث النبوي بلغته الكلاسيكية.
الأرقام تقول العكس على المجموعتين. **صفر من 100 وثيقة** تعدّت
حد الـ 512 توكن، لأن المُدخل هو المتن المجرَّد من التشكيل.

### اختيار الموديل — اختبار McNemar المزدوج

الفجوة الظاهرة على المجموعة اليدوية (67% مقابل 56% في
`hit@1`) هي **3 أسئلة**. الاختبار على النتايج المزدوجة:

| المجموعة | المقياس | bge فقط | mmarco فقط | p |
|---|---|---|---|---|
| golden (27) | hit@1 | 3 | 0 | 0.250 |
| golden (27) | hit@5 | 1 | 0 | 1.000 |
| synthetic (224) | hit@1 | 11 | 11 | **1.000** |
| synthetic (224) | hit@5 | 5 | 2 | 0.453 |

**لا فرق معنوي في أي مقياس على أي مجموعة.** وعلى المجموعة
الأكبر والأصعب: تعادل تام 11-11.

**القرار: `mmarco-mMiniLMv2-L12` هو الافتراضي** — أصغر 17 مرة
وأسرع ~6 مرات (0.5 ثانية مقابل 3+ ثواني لكل سؤال على CPU).
القاعدة كانت مكتوبة في الخطة **قبل** رؤية الأرقام: عند فرق
أقل من نقطتين على المجموعة الكبيرة، يُختار الأسرع.

الاتجاه على المجموعة اليدوية لصالح bge (3-0) لكنه غير معنوي
وغير مؤكَّد على العينة الأكبر. تبديل الافتراضي سطر واحد في
`src/rerank.py`.

**درس منهجي:** الحكم الأول على mmarco كان بزوج اختبار واحد
أعطى ترتيبًا مقلوبًا، فاستُنتج أنه لا يميّز. القياس الكامل
كذّب ذلك تمامًا. زوج واحد ليس قياسًا.

### موديلات لم تعمل

| الموديل | السبب |
|---|---|
| `jinaai/jina-reranker-v2-base-multilingual` | كوده المخصص يستورد `create_position_ids_from_input_ids`، وهي دالة أُزيلت من `transformers` الحديثة — `ImportError` عند التحميل |
| `Alibaba-NLP/gte-multilingual-reranker-base` | يُحمَّل لكنه يفشل عند الاستنتاج: `IndexError` في تنفيذ RoPE المخصص |

الحل بتثبيت نسخة أقدم من `transformers` كان سيكسر
`sentence-transformers` و e5 ويستلزم إعادة بناء كل المتجهات —
تكلفة غير مبررة لأجل مقارنة.

---

## 7. ضبط بارامترات الدمج — نتيجة سلبية

مسح على **224 سؤال مولَّد** (الفروق هنا أصغر من أن تُقاس
على 27).

**حجم قائمة المرشحين**

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| 25 | 17% | 32% | 38% | 44% | 0.259 |
| **50** (الافتراضي) | 18% | 30% | 37% | 44% | 0.256 |
| 100 | 18% | 29% | 35% | 44% | 0.250 |
| 200 | 18% | 28% | 37% | 46% | 0.254 |

**أوزان RRF (دلالي : BM25)**

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| **1.0 : 1.0** (الافتراضي) | 18% | 30% | 37% | 44% | **0.256** |
| 1.5 : 1.0 | 18% | 29% | 33% | 38% | 0.242 |
| 1.0 : 1.5 | 18% | 29% | 35% | 42% | 0.253 |
| 1.0 : 2.0 | 19% | 29% | 36% | 42% | 0.254 |
| 2.0 : 1.0 | 19% | 29% | 34% | 38% | 0.248 |

**لا مكسب.** مدى MRR كله 0.242–0.259 — والأوزان المتساوية
هي الأفضل فعليًا. الافتراضيات كانت عند المثالي بالفعل.

**تصحيح لملاحظة سابقة:** سُجِّل مبكرًا أن رفع المرشحين من 50
إلى 100 رفع `hit@10` من 85% إلى 89%. ذلك كان على 27 سؤالًا
أي **سؤال واحد**، والمسح على 224 لا يُظهر أي أثر لحجم قائمة
المرشحين. الملاحظة الأولى كانت ضوضاء.

---

## 8. إزالة المتون المكررة — نتيجة سلبية

7 من 27 سؤال فيهم متون مكررة في أول 5 (مسلم يروي المتن الواحد
بأسانيد مختلفة). الفرضية: إزالة التكرار تحرّر خانات وترفع
النتيجة.

| | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| الأساس | 41% | 59% | 74% | 89% | 0.535 |
| مع إزالة التكرار | 41% | 59% | 74% | 89% | 0.537 |

**صفر مكسب.** المتون المكررة بتيجي تحت الإجابة الصح مش فوقها.
الفكرة اتشالت قبل ما تتبني.

---

## 9. جودة الإجابة

30 سؤال (27 مقيسة + 3 رفض)، استرجاع هجين، `k=5`.
كل المقاييس محسوبة برمجيًا. **محاولات الاستشهاد الباطل
مقيسة على المخرَج الخام قبل أي تصفية** — لو قِسناها بعد
التصفية لطلعت صفرًا دايمًا بحكم البناء.

| المقياس | gpt-oss-120b | **gemini-2.5-pro** |
|---|---|---|
| محاولات استشهاد باطل | 0% | **0%** |
| استشهاد بحديث خطأ من السياق | 20% | **13%** |
| استشهاد صحيح | 63% | **70%** |
| رفض كاذب (الحديث كان موجودًا) | 0% | **0%** |
| رفض صحيح على أسئلة الرفض | 3/3 | **3/3** |
| ذكر مصدرًا أثناء الرفض | 0% | **0%** |

**القرار: `gemini-2.5-pro` عبر Vertex.** موديل واحد ثابت —
التنقل بين الموديلات كان بيفسد كل مقارنة.

### هل تحسين الاسترجاع يتحوّل لإجابات أصح؟

نفس المولّد، ثلاثة إعدادات:

| المقياس | هجين | **+ reranker** | + reranker + CRAG |
|---|---|---|---|
| استشهاد صحيح | 70% | **81%** | 81% |
| استشهاد بحديث خطأ من السياق | 13% | 10% | 7% |
| وصل الحديث الصح للسياق | 20 | **22** | 22 |
| محاولات استشهاد باطل | 0% | 0% | 0% |
| رفض كاذب | 0% | 0% | 0% |
| رفض صحيح على أسئلة الرفض | 3/3 | 3/3 | 3/3 |
| نداءات LLM لكل سؤال | 1 | 1 | **3** |

**نعم — الاسترجاع هو عنق الزجاجة، لا الطبقة اللغوية.**
الـ reranker أوصل الحديث الصح لسياق سؤالين إضافيين ورفع
الاستشهاد الصحيح 11 نقطة. المولّد بيحوّل تقريبًا كل ما يصله.

**CRAG (تقييم ذاتي + إعادة صياغة واحدة): نتيجة سلبية.**
الاستشهاد الصحيح **لم يتغير** (81% ← 81%). أعاد الصياغة في
4 أسئلة وغيّر نتيجة واحدة (استشهاد خاطئ 10% ← 7%، أي سؤال
واحد على 30 = ضوضاء). التكلفة **ثلاثة أضعاف نداءات LLM**.
مُنفَّذ في `answer.py` لكن **مُعطَّل افتراضيًا** — لا مبرر
مقيس لتشغيله.

**ملاحظة تدعم اختيار الـ reranker السريع:** فجوة الـ 11 نقطة
في `hit@1` بين bge وmmarco على المجموعة اليدوية **لم تظهر في
جودة الإجابة** — mmarco أعطى 81% استشهادًا صحيحًا مقابل 78%
لـ bge. الفرق في الاسترجاع لم يكن حقيقيًا بما يكفي ليُحدث
أثرًا في المخرَج.

خط الأساس قبل الإصلاحات (llama-3.3-70b، سياق كامل بالسند،
برومبت باستشهاد غير مشروط): **7 من 10 رفض** حتى في أسئلة
إجابتها موجودة، واستشهادات مخترعة («حديث رقم 760»)، وتسرّب
حروف من لغات أخرى.

الإصلاحات: سياق بالمتن فقط مع رقم الحديث والباب (388 حرف
لسؤالين بدل آلاف)؛ استشهاد مشروط بوجود إجابة؛ `temperature=0`؛
وفرض صحة الاستشهاد في الكود — **رقم خارج السياق ⟵ إعادة توليد
مرة واحدة ⟵ رفض**، لا حذف الرقم، لأن إجابة بلا مصدر في هذا
المجال أسوأ من الاعتراف بعدم المعرفة.

---

## منهجية

**ثلاث مرات ظهر أن «فشل النظام» كان خطأ في الـ ground truth:**

1. «صيام عاشوراء» — النظام رجّع 9803 و9806 و9808 وكلها فيها
   الحكم، والمرجع كان يحوي رقمًا واحدًا.
2. «عدد ركعات الوتر» — النظام رجّع 8928 «الوتر ركعة من آخر
   الليل» في المركز 4، ولم يكن في قائمة الإجابات.
3. «الغش في البيع» — الحديث 10762 كان في القائمة لأن بحثًا
   نصيًا طابق «من غش»، والكلمة في الحديث **«من غشيانهن»**.

ومنها كمان: «فضل سورة الكهف يوم الجمعة» لا وجود له في مسلم
أصلًا، فتحوّل لسؤال اختبار رفض.

لذلك `src/validate_golden.py` بوابة تُشغَّل قبل أي تقييم:
تتحقق من وجود كل رقم، ومن ظهور نص المتن في أحد الأرقام
المذكورة، ومن أن ألفاظ أسئلة الرفض **غائبة فعلًا** عن المتن.

**قواعد ثابتة:** كل رقم معه حجم عينته ومصدره · فرق أقل من
~4 نقاط على الـ 27 = سؤال واحد = اتجاه لا نتيجة · أي فرضية
تُقاس قبل أن تُبنى.

**ترتيب العمل لأي ميزة جديدة:**

```
implement → test → measure → document
```

لا يُكتب في `README.md` وصفٌ لشيء غير موجود. ما لم يُبنَ بعد
مكانه قسم [Planned](README.md#planned) بصيغة المستقبل الصريحة.
السبب: النسخة الأولى من هذا الملف وصفت معمارية وكلاء وجرافًا
معرفيًا وخادم MCP بصيغة الماضي، ولم يكن أيٌّ منها موجودًا —
وهو أسوأ نوع من الادعاء لأنه غير قابل للاكتشاف من قراءة الوثيقة
وحدها.

---

## 10. بوابة ربط حديث صحيح مسلم ↔ MIS

**تاريخ القياس:** 2026-08-16

### HYPOTHESIS

النهاية المطبَّعة المكوّنة من 10 كلمات تستطيع توليد مرشح MIS
فريد لمعظم أحاديث مجموعتنا، ويمكن قبول المرشح آليًا فقط إذا
دعمه تشابه كامل للنص (`SequenceMatcher.ratio >= 0.90`).

### WHY THIS HYPOTHESIS MATTERS

أي ربط خاطئ هنا سينسب سلسلة رواة كاملة إلى حديث آخر. لا يجوز
بناء graph أو بدء مطابقة الرواة قبل قياس التغطية والدقة وسلامة
الخريطة عالميًا.

### BASELINE

الربط العددي `idInBook == HadithNo`: يوجد الرقم في MIS لكل
السجلات المحلية، لكن النص يتفق في **1 / 7,459 فقط = 0.0134%**.

**FAILED / NEGATIVE RESULT:** المساواة الرقمية مرفوضة كـ join.

### ONE VARIABLE CHANGED

استُبدل الربط العددي بمرشح وحيد من توقيع آخر 10 كلمات بعد
التطبيع، مع معيار قبول نصي كامل ثابت عند 0.90. لم يُستخدم
الترتيب لتغيير أي زوج.

ملاحظة تنفيذية: النسخة الأولى استعملت
`SequenceMatcher.quick_ratio()`، وهو حد أعلى لا score قبول.
أُعيد القياس بـ `ratio()`. **لم يتغير أي قرار عند حد 0.90**:
الطريقتان قبلتا 7,015 زوجًا، فتصحيح الدالة مهم منهجيًا لكن
نتيجته العددية سلبية في هذه البيانات.

### DATASET

| الملف | السجلات | sha256 |
|---|---:|---|
| `data/raw/muslim.json` | 7,459 | `e3ae9dc8b4a03e19dd19b13e595881cb5730b094e72a393b7d1d69e93c67742a` |
| MIS hadith content | 7,748 | `7bc22f27ec9230544e083f3dae1f2e3db2d75994e5bcdc52c952e51822923334` |
| MIS narrator nodes | 2,092 | `301c336b3581954b9e5509b6ee9c5721386787ec12c2d510cd909c2f5330561b` |
| MIS isnad edges | 63,642 | `e98e7de910b4ce8ac106536a752a23f07c2c3e04c28c298ea1f9938102556820` |

### METRIC / RESULT

#### Candidate generation and automated acceptance

| الحالة | العدد | نسبة المحلي |
|---|---:|---:|
| unique tail candidate | 7,111 | 95.3345% |
| ambiguous tail | 300 | 4.0220% |
| no tail candidate | 48 | 0.6435% |
| accepted unique pair (`ratio >= 0.90`) | **7,015** | **94.0475%** |
| unique candidate below threshold | 96 | 1.2870% |
| local not accepted (all causes) | 444 | 5.9525% |
| MIS records not linked by accepted map | 733 | 9.4605% |

هذه **تغطية ربط آلية** وليست precision.

#### Global cardinality

| المقياس | العدد |
|---|---:|
| accepted pairs | 7,015 |
| one-to-one pairs | 7,015 |
| local records with one-to-many accepted links | 0 |
| MIS records with many-to-one accepted links | 0 |
| duplicate accepted pairs | 0 |

لم يُفرض قيد 1:1 بعد النتيجة؛ القياس الخام نفسه خرج 1:1.

#### Ordering corroboration

على الترتيب الخام: Spearman =
**0.9298492117875622736489439168672199411435**، Kendall tau-b =
**0.9532260598444694970104592769455488778070**، وعدد الانعكاسات
**575,357 / 24,601,605** بمعدل
**0.02338697007776525149477036152722556109652**. سبب معظم
الانخفاض rotation واضح بين الطبعتين: المحلي 1–7,368 يصطف مع
MIS 102–7,748، ثم مقدمة مسلم المحلية تلتف إلى MIS 2–100.

بعد **فك هذا الالتفاف لأغراض التشخيص فقط**: Spearman =
**0.9999999999652385223894495483798909665792**، Kendall tau-b =
**0.9999999187044910281260104777716738399791**. يوجد انعكاس واحد
بالضبط من 24,601,605، بمعدل
**0.00000004064775448593699476111416308001043021380**: المحلي
3,487 → MIS 3,684 يسبق المحلي 3,488 → MIS 3,683. فك الالتفاف لم
ينشئ ولم يعدّل أي link، ولا يجوز وصف القيم بأنها perfect.

#### MIS structural integrity

* 63,642 / 63,642 edge labels parse with explicit order.
* 0 duplicate edge labels; 0 hadith/sanad label mismatches.
* 0 chains with duplicate or non-contiguous order.
* 0 edge narrator IDs absent from the 2,092-node table after safe
  int/string normalization.
* 0 edge hadith IDs absent from content; 0 content hadiths without edges.
* 14,155 distinct chains; 3,586 hadiths with multiple chains; maximum 24.

### ACCEPTED-LINK PRECISION SAMPLE

أنشئت عينة عشوائية بسيطة **بدون إرجاع** من population القبول
البالغ 7,015:

* sample size: **361**
* seed: `20260816`
* population hash: `99b40085d8c2c9d3325d36d65fb6d3ed8d26538b0bf0ceff297b85c5edb81d2f`
* sizing assumption: expected precision 99%, confidence 95%, target
  margin ±1 percentage point, with finite-population correction
* post-review interval: two-sided 95% Wilson interval
* visible reviewer file hides score, threshold, strategy, chapter,
  positions, and signature
* hidden metadata is in a separate file and must not be joined before
  final labels

**MANUAL LABELS:** 0 / 361. لذلك precision وconfidence interval
**UNKNOWN**. العينة التشخيصية المنفصلة ما زالت 89 صفًا بلا أحكام؛
وظيفتها اكتشاف أنماط الفشل لا تقدير الدقة.

#### AI/computational textual-identity audit

أُضيفت لاحقًا إلى reviewer CSV ثلاثة أعمدة آلية (`ai_verdict`,
`ai_reason`, `base_text_equal_after_diacritics_removal`). أُعيد القياس
بشكل مستقل وقابل للتكرار بواسطة
`python -m src.audit_linkage_validation_identity`:

| المقياس | النتيجة |
|---|---:|
| rows audited | 361 |
| raw strings exactly equal | 0 |
| exact after NFC + Arabic combining-mark/tatweel removal + whitespace folding | **361** |
| computational textual mismatches | **0** |
| disagreements with supplied AI verdict | 0 |
| nonblank `manual_verdict` | **0** |

لم تُوحّد حروف الألف/الهمزة/الياء/التاء المربوطة، ولم تُحذف كلمات
أو علامات ترقيم. hash ملف الإدخال بعد إضافة أعمدة AI هو
`4945fb8ce21a4646775a69147649cd013ffe7610035155b325e43fbcfd138284`؛
وسجل القياس الناتج هو
`data/processed/linkage_validation_ai_identity_audit.json` (sha256
`98056b56be2554f8a03cb7360ad202ad1a52b35742d638b5a5af22c85975dfa8`).

هذا **دليل تطابق نصي حاسوبي** قوي، وليس human precision measurement.
لكنه لا يحدد وحده occurrence identity إذا كان النص نفسه مكررًا. كذلك،
وجود verdict آلي داخل الملف المرئي قبل المراجعة البشرية يعني أن هذه
النسخة لم تعد blind review artifact. أضيف guard إلى sample builder كي
لا يقبل silent schema leakage من هذا النوع. حُفظ ملف AI كما هو، وأصدر
الـ builder نسخة بشرية نظيفة منفصلة في
`data/processed/linkage_validation_human_review.csv` (361 صفًا، سبعة
أعمدة فقط، 0 labels، sha256
`3e6a0db164de3abdae876c7e8697d9c4fad27ad6af045085c11b831e37b82df7`).

#### Full normalized-text / occurrence-ambiguity audit

قيس corpus كاملًا بنفس `normalize_narrow_identity` دون أي توحيد لحروف
العربية أو حذف punctuation أو fuzzy/semantic matching.

**Full-corpus cardinality:** محليًا يوجد 7,457 نصًا مطبعًا مميزًا،
ومجموعتا duplicate فقط تشملان 4 سجلات (أقصى حجم 2). في MIS يوجد
7,547 نصًا مميزًا، و5 مجموعات duplicate تشمل 206 سجلات؛ أكبرها 197
سجلًا نصها فارغ. لا توجد سجلات محلية فارغة.

تصنيف كل accepted link مقابل تكرار نصه في corpus الكامل:

| collision class | count | percent of 7,015 |
|---|---:|---:|
| `UNIQUE_UNIQUE` | **7,015** | **100.000000%** |
| `UNIQUE_MULTI` | 0 | 0% |
| `MULTI_UNIQUE` | 0 | 0% |
| `MULTI_MULTI` | 0 | 0% |

إذن عدد duplicate normalized-text groups المشاركة في accepted map هو
**0**: لا توجد collision group لتصنيفها `STRUCTURALLY_RESOLVED` أو
`AMBIGUOUS`، ولم يحدث deduplication صامت.

لكن فحص الهوية النصية الكامل كشف limitation لم تظهر في العينة:

| full accepted identity | count | percent |
|---|---:|---:|
| narrow-normalized exact | **7,004** | **99.843193%** |
| non-exact under allowed normalization | **11** | **0.156807%** |

كل الـ 11 فريد نصيًا على الجانبين ومحاط بزوجين `UNIQUE_UNIQUE` exact
في الترتيب المفكوك. في 4 / 11 يتطابق كذلك gap pattern والـ position
offset بين الجارين. هذا corroboration، لا يحول اختلاف النص إلى exact
identity.

| our `idInBook` | MIS `HadithNo` | deterministic delta |
|---:|---:|---|
| 217 | 325 | local has an additional 125-character leading segment |
| 388 | 503 | MIS has an inserted timestamp/date string |
| 4,663 | 4,903 | retained directional-format mark only |
| 4,862 | 5,109 | local has an additional 61-character leading segment |
| 5,256 | 5,516 | MIS has an additional Arabic comma |
| 5,361 | 5,622 | local has an additional 61-character leading segment |
| 5,677 | 5,962 | local has six additional backslash characters |
| 5,777 | 6,066 | local has an additional 173-character leading segment |
| 7,043 | 7,402 | local has an additional 94-character leading segment |
| 7,114 | 7,477 | MIS has an additional `ح` transmission marker |
| 7,249 | 7,623 | local has an additional 79-character leading segment |

ثلاث حالات فقط لها نفس Arabic word/base-letter sequence وتختلف في
punctuation/format؛ ثماني حالات تختلف في word/base-letter sequence.
لم تُحسم أي حالة آليًا. أنشئت complete-census review من 11 صفًا فقط في
`data/processed/linkage_non_exact_review.csv`، دون score أو strategy أو
hidden metadata (sha256
`c933254d454cc3810536c44f6db4fb98ed7bc03182dd32487d5b930235830236`).

سجل القياس الكامل:
`data/processed/linkage_ambiguity_audit.json` (sha256
`4fecb055411bcc2c3131fbd9797e7754451d4862a6a833122d1a23bd091b3d65`).

#### Targeted AI-assisted adjudication and deterministic verification

تقرير adjudication المقدم (sha256
`5bcc1c9f544a9e7e33fe2a2241d982d83c2f8c89ec12e801e00945aaf95e593b`)
صرح بوضوح أنه **AI-assisted وليس independent human validation**، وسجل
`correct=11`, `wrong=0`, `uncertain=0`. لم يُكتب شيء في
`manual_verdict` أو `notes`؛ كلاهما ما زال فارغًا في 11 / 11.

لم تُقبل الأحكام لمجرد ورودها في التقرير. تحقق
`python -m src.validate_linkage_ai_adjudication <report>` من كل صف
بقاعدة exception ضيقة قابلة للتكرار، دون تغيير normalizer العام:

| deterministic exception shape | count |
|---|---:|
| local-only leading segment ending at standalone `ح`, followed by an exact MIS suffix | 6 |
| removable MIS-only timestamp/date insertion | 1 |
| removable MIS-only bidi format mark | 1 |
| removable MIS-only Arabic comma | 1 |
| removable local-only literal backslashes | 1 |
| removable MIS-only standalone `ح` marker | 1 |

كل rule يزيل فقط الـ measured delta الخاص بالصف، ثم يشترط exact retained
text. قيس retained core الناتج عبر الـ corpora كاملة أيضًا: **11 / 11
`UNIQUE_UNIQUE`** بعد exception، و0 retained-core collisions. النتيجة:
**11 deterministically supported / 0 unresolved**، ومتوافقة مع aggregate
AI report. سجل provenance والقياس:
`data/processed/linkage_non_exact_ai_adjudication.json` (sha256
`bdb200c9b872e2de1077718fdedc8c520788e86cdda206c52165f8eda8251748`).

الهوية النهائية للـ accepted population أصبحت:

* 7,004 narrow-normalized exact و`UNIQUE_UNIQUE`.
* 11 `UNIQUE_UNIQUE` مع exception delta محصور ومثبت حتميًا.
* 0 accepted collision groups.
* 0 unresolved accepted links.

### STATISTICAL / SAMPLE-SIZE LIMITATION

هامش ±1% في sizing يفترض precision=99%. لكن بعد إثبات أن 7,004 زوجًا
`UNIQUE_UNIQUE` ومتطابق deterministic، وشرح كل الـ 11 الباقية بقواعد
exception exact ومحصورة، تكرار visual confirmation لا يوفر record-level
evidence مستقلة ولا يفيد Wilson estimate علميًا. لم تحدث مراجعة بشرية،
ولا يجوز وصف النتيجة بأنها human precision؛ قرار البوابة يعتمد على
deterministic full-population evidence لا على تحويل AI labels إلى human.

### DECISION

**GATE OPEN.** كل الـ 7,015 accepted links لها record identity قابلة
للدفاع: 7,004 exact unique، و11 unique ذات exception delta حتمي ومحصور؛
0 collision ambiguity و0 unresolved. هذا قرار evidence gate فقط، وليس
تفويضًا بالانتقال للمرحلة التالية. لا يبدأ entity resolution أو graph
construction قبل موافقة المستخدم الصريحة.

---

## 11. Full Itqan profile / grading / provenance audit

**تاريخ القياس:** 2026-08-16 · Itqan manifest version `1.20`

### HYPOTHESIS

الملفات الكاملة توفر IDs سليمة وحقول هوية/علاقات/درجات كافية
للتجارب اللاحقة، لكن تصادم الأسماء واختلاف أحكام المصادر
سيمنعان أي exact-name join أو grade موحد بلا قياس.

### DATASET / PARSE VALIDATION

كل ملفات JSON المنزلة وعددها **11 / 11** قُرئت كاملة. ملفات
profiles السبعة تطابق manifest في العدد، والمجموع **115,735**.

**Discrepancy:** manifest و`by_name.json` يسجلان 217,762 variant،
لكن مجموع عناصر `namings[]` في profile shards هو **196,488**.
الرقم الأول ليس مجموع `namings[]`، ولا يجوز استخدامهما بالتبادل.

### PROFILE METRICS

* IDs: 115,735 unique؛ 0 null/blank؛ 0 duplicate.
* Arabic-script full names: 115,733.
* distinct normalized full names: 85,234.
* 10,014 normalized names مشتركة بين أكثر من profile؛ تشمل
  40,513 profile، وأكبر collision يحمل 566 profile.
* non-empty `namings[]`: 115,726 / 115,735 = **99.9922%**.
* distinct normalized variants: 173,770؛ منها 10,206 تشير لأكثر
  من profile وتلمس 22,242 profile.
* 367 variant duplicates داخل profile نفسه؛ لم تُحسب كتصادم
  بين profiles.

Field coverage (filled, with `None` and sentinels treated as missing):

| field | filled |
|---|---:|
| kunya | 65,783 |
| nasab | 16,907 |
| laqab | 1,688 |
| death | 37,119 |
| tabaqat | 11,235 |
| generation | 1,205 |
| city | 4,488 |
| grade_en | 115,735 |
| grade_ar | 84,437 |
| dhahabi | 5,238 |

Teacher/student data: 309,642 teacher refs and 306,158 student refs;
0 null refs and 0 targets missing from profile IDs. There are 17 and 4
duplicate references within individual teacher/student lists respectively.

### GRADING DISAGREEMENT

`classical_sources` exists non-empty for 106,011 profiles, covering
167,168 source entries from 22 named sources; every entry has `entry_id`,
and `provenance.sources` agrees with the source/entry pair list in every
profile.

Three different measurements must not be conflated:

| definition | numerator / denominator | rate | interpretation |
|---|---:|---:|---|
| raw Arabic wording differs, among profiles with ≥2 nonblank raw grades | 12,531 / 14,417 | 86.9182% | wording variation; not automatically semantic disagreement |
| Itqan category differs across all multi-source profiles | 17,572 / 21,593 | 81.3782% | contaminated by blank grades represented as `unknown` |
| Itqan category differs where ≥2 source entries have nonblank raw grades | 9,961 / 14,417 | **69.0920%** | strongest like-for-like dataset-category disagreement measure |

There are **57,091** source entries where `grade_en="unknown"` and
`grade_ar` is blank. The 81.4% historical claim is therefore not an
honest standalone “scholars disagree” statistic.

`grade_en` is Itqan's supplied seven-category field. The downloaded
manifest does not document the equivalence mapping for every Arabic phrase;
no new scholarly normalization was invented here.

### PROVENANCE CAPABILITY

Each source entry contains only `entry_id`, `grade_ar`, and `grade_en`.
There is no volume/page/edition field. IDs are reused across profiles inside
several named sources (for example one `siyar` entry is shared by as many as
24 profiles), so `entry_id` is not a unique narrator identifier.

Strongest currently defensible statement:

> According to the named source entry represented in Itqan, narrator X is
> recorded as [verdict] (Itqan entry_id Y).

Not currently defensible:

> Directly cited from volume/page Z of a printed classical edition.

The downloaded shards do not contain a dereference table from `entry_id` to
printed edition/page. Direct dereference semantics remain **UNKNOWN**.

### DECISION

The files are profileable and internally consistent enough for a future,
separately evaluated entity-resolution phase. The linkage evidence gate is
open, but phase transition still requires explicit user approval; entity
resolution remains **not implemented** here.

---

## 12. Narrator Entity Resolution — Phase 2

**Measurement date:** 2026-08-16
**Status:** deterministic candidate audit only; no production identity map

### QUESTION

How many of the 2,092 MIS narrator identities have zero, one, or multiple
Itqan candidates under raw canonical equality, narrow normalized canonical
equality, and documented `namings[]` equality? The safety objective is to
minimize false merges; abstention is preferred to forcing a match.

### DATASETS

* MIS nodes: 2,092 rows; SHA-256
  `301c336b3581954b9e5509b6ee9c5721386787ec12c2d510cd909c2f5330561b`.
* MIS edges: 63,642 rows; SHA-256
  `e98e7de910b4ce8ac106536a752a23f07c2c3e04c28c298ea1f9938102556820`.
* Itqan: 115,735 profiles in seven shards; manifest version `1.20`;
  combined shard hash
  `24b2df2819ec230bec206087b81f6a8275a3ccf2605ce8080f013a77af410940`.
* Accepted Hadith ↔ MIS linkage frozen as `hadith_mis_linkage_v1`: 7,015
  rows; SHA-256
  `9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77`.
  It is an immutable input to this experiment and was not retuned.
* MIS narrator IDs had 1,999 integer and 93 string raw values. Safe
  normalization produced 2,092 unique non-null IDs, zero collisions, and no
  cardinality change. Numeric strings with significant formatting such as
  `"001"` are not blindly integer-coerced.

### NORMALIZATION

Identity normalizer
`narrow_arabic_name_v1_nfc_marks_tatweel_whitespace` applies only Unicode
NFC, Arabic combining-mark removal, tatweel removal, and whitespace
collapse. Canonical source values are retained. It performs no
alif/hamza, ya/maqsura, or ta-marbuta substitution and removes no words or
punctuation.

Separate, non-resolution experiments on the 2,001 still-unmatched names
measured the risk of letter folds:

| experimental fold | new unique | new ambiguous | largest group | used |
|---|---:|---:|---:|---|
| alif/hamza → alif | 3 | 0 | 1 | no |
| ta-marbuta → ha | 0 | 0 | 0 | no |
| ya-maqsura → ya | 393 | 70 | 7 | no |

The ya/maqsura fold materially increases collisions. None of these results
were promoted into an identity rule.

### BASELINE A — RAW EXACT

Raw MIS name equals raw Itqan canonical `full_name`:

| candidates per MIS narrator | count |
|---|---:|
| 0 | 2,052 |
| 1 | 33 |
| 2 | 5 |
| 3–5 | 2 |
| >5 | 0 |

The pre-conflict unique rate is 33 / 2,092 = **1.577438%**. A unique raw
canonical candidate is not retained automatically if aliases introduce a
different profile; after that conservative union check, 30 remain
`EXACT_RESOLVED`.

### BASELINE B — NARROW NORMALIZED

The narrow-normalized canonical distribution is identical to raw exact:
2,052 zero, 33 one, 5 two, 2 with 3–5, and 0 above five. It contributes
**0 incremental unique candidates**, so `NORMALIZED_RESOLVED = 0` in this
dataset. This negative result is retained rather than broadening the
normalizer.

### BASELINE C — ALIAS

Alias lookup was evaluated for the 2,059 narrators without a unique narrow
canonical result:

| alias candidates | count |
|---|---:|
| 0 | 2,001 |
| 1 | 54 |
| 2 | 3 |
| 3–5 | 1 |
| >5 | 0 |

Fifty-one narrators have a single union candidate solely through a
documented Itqan alias and are provisionally `ALIAS_RESOLVED`. Eight MIS
narrators have canonical-vs-alias conflicts. Alias collisions and any union
with more than one candidate remain ambiguous; Itqan confidence was not
used to select among profiles.

### COLLISION ANALYSIS

For the 2,092 MIS names, candidate cardinality was measured separately:

| lookup population | 0 | 1 | 2 | 3–5 | >5 | largest |
|---|---:|---:|---:|---:|---:|---:|
| canonical name | 2,052 | 33 | 5 | 2 | 0 | 5 |
| alias, all MIS names | 2,007 | 81 | 3 | 1 | 0 | 3 |
| canonical + alias union | 2,001 | 81 | 7 | 3 | 0 | 5 |

All ten union collision groups are preserved in full in the collision
artifact; none is silently deduplicated or automatically resolved.

### BIOGRAPHICAL EVIDENCE COVERAGE

The ambiguous population contains 10 MIS narrators and 26 Itqan candidate
rows. MIS provides no direct kunya, nasab, laqab, death, tabaqa, or city
field. MIS generation is available for all ten, but no validated crosswalk
to Itqan's sparse generation representation exists. Therefore direct
candidate-discriminating and contradiction rates are currently zero or
unknown, not negative evidence.

| Itqan field | any candidate filled | all candidates filled | values differ between candidates | usable with MIS now |
|---|---:|---:|---:|---:|
| kunya | 8 / 10 | 4 / 10 | 4 / 10 | 0 |
| nasab | 9 / 10 | 2 / 10 | 1 / 10 | 0 |
| laqab | 0 / 10 | 0 / 10 | 0 / 10 | 0 |
| death | 7 / 10 | 2 / 10 | 2 / 10 | 0 |
| tabaqat | 10 / 10 | 0 / 10 | 0 / 10 | 0 |
| city | 4 / 10 | 0 / 10 | 0 / 10 | 0 |
| generation | 5 / 10 | 0 / 10 | 0 / 10 | 0 |

`FALSE` was not assigned when MIS or Itqan evidence was absent. No explicit
biographical contradiction was established, so no record was quarantined.

### SANAD-STRUCTURE EVIDENCE

The measured MIS edge direction is earlier narrator → later narrator. Of
2,092 MIS narrators, 1,881 have teacher neighbors and 1,877 have student
neighbors; 81 provisional Itqan profiles are available as resolved-neighbor
anchors. Those anchors occur among the teacher neighbors of 249 MIS
narrators and the student neighbors of 270.

Across the 26 ambiguous candidate rows, teacher support states are 1
`TRUE` / 25 `UNKNOWN`, and student support states are likewise 1 `TRUE` /
25 `UNKNOWN`. Fourteen candidate rows contain some Itqan teacher records
and 12 contain student records. Only one ambiguous narrator has a resolved
teacher anchor and one has a resolved student anchor; one narrator has
exactly one candidate with relationship support. This is supporting
evidence only: missing Itqan relationships are `UNKNOWN`, not
contradictions, and no
`COMPOSITE_RESOLVED` tier was assigned without labelled validation.

### CANDIDATE TIERS

| provisional tier | count | share of 2,092 |
|---|---:|---:|
| `EXACT_RESOLVED` | 30 | 1.4340% |
| `NORMALIZED_RESOLVED` | 0 | 0% |
| `ALIAS_RESOLVED` | 51 | 2.4379% |
| `COMPOSITE_RESOLVED` | 0 | 0% |
| `AMBIGUOUS` | 10 | 0.4780% |
| `UNMATCHED` | 2,001 | 95.6501% |
| `QUARANTINED` | 0 | 0% |

The provisional deterministic auto-resolution population is **81 / 2,092
= 3.871893%**. These are evaluation candidates, not a final production
identity map.

### AMBIGUITY

Ten narrators retain 2–5 plausible profiles: seven have two union
candidates and three have 3–5. Eight include canonical-vs-alias conflicts.
All candidate provenance (`canonical_exact`, `normalized_canonical`,
`alias`) and the 26 candidate feature rows are retained. No weighted score,
fuzzy metric, LLM decision, or confidence-based tie-break was applied.

### UNMATCHED

**2,001 / 2,092 = 95.650096%** have no canonical or alias candidate under
the narrow identity representation. This high abstention is intentional at
the first stop point. Experimental letter-fold hits are not accepted as
identities.

### EVALUATION DESIGN

The frozen reviewer-facing sample has 117 deduplicated rows and seed
`2026081602`. The auto-resolved population is 81. A normal-approximation
proportion sizing calculation with finite-population correction, assumed
precision 99%, 95% confidence, and target margin ±1 percentage point gives
67 precision rows. Allocation is a census of all 30 exact-tier rows plus a
simple random sample of 37 / 51 alias-tier rows; tier inclusion
probabilities are stored for weighted aggregation.

Diagnostics, excluded from the precision denominator, include all ten
ambiguities, 30 unmatched narrators, all repeated/collision cases through
the ambiguity census, and ten additional common kunya/nasab-form cases.
There are no MIS names meeting the defined short-name risk flag (at most two
normalized tokens), so that requested diagnostic stratum has population
zero.

The visible CSV has blank human fields and omits auto tier, Itqan
confidence, candidate provenance, risk stratum, and the automatic selected
ID. Those fields are held separately. Candidate profile evidence and IDs
remain visible because a reviewer needs them to judge identity. Allowed
verdicts are `correct`, `wrong`, `uncertain`, and
`NEEDS_DOMAIN_EXPERT`. At generation, manual labels are **0 / 117**.

After labelling, report precision and false-merge rate overall and by tier;
do not blend diagnostic rows into that denominator. False-split rate is not
yet measurable from this candidate-only review design.

### LIMITATIONS

* Deterministic names and aliases provide only 3.87% provisional coverage.
* MIS lacks the direct biographical fields needed to compare most Itqan
  candidate attributes; contradiction rates therefore remain unknown.
* Itqan teacher/student omissions cannot be interpreted as incompatibility.
* A unique string/alias candidate is not proof of person identity until the
  labelled false-merge evaluation is complete.
* The review can hide resolver metadata but cannot hide the candidate
  profiles that must be judged; this is evidence blinding, not total
  identity blinding.
* No fuzzy matching, scoring, ML, LLM adjudication, final mapping, grading
  flattening, graph node construction, or graph traversal was performed.

### DECISION

**ENTITY-RESOLUTION GATE CLOSED.** The candidate landscape, collisions,
evidence availability, provisional tiers, and frozen review design are
measured. Opening the gate requires human/domain review of the frozen set,
then precision and false-merge reporting overall and by tier. The next
permitted action is review, not fuzzy matching or graph construction.

---

## 13. Unmatched Narrator Name-Gap Diagnostic — Phase 2A

**Measurement date:** 2026-08-16
**Status:** representation-gap characterization only; frozen Phase 2 tiers

### QUESTION AND INVARIANTS

Why do 2,001 / 2,092 MIS narrators have no narrow-exact Itqan canonical or
documented-alias candidate? The input candidate artifact remains SHA-256
`8343fceb18e3e517504616b7205a4737377c6a414353e77058e3a88162544892`.
Its 30 `EXACT_RESOLVED`, 51 `ALIAS_RESOLVED`, 10 `AMBIGUOUS`, and 2,001
`UNMATCHED` rows were not changed. The pre-existing 117-row review artifact is
also checked byte-for-byte on every run. No diagnostic candidate is a match.

### DATASET NAME SEMANTICS

The MIS paper defines `NarratorNameAr` as “Narrator Complete Name in Arabic
Text” and `NarratorNameAr-Mapped` as “Narrator Short Name in Arabic Text.” Both
are nonblank for all 2,092 local rows, only 57 pairs are narrow-equal, and the
short field has fewer tokens in 1,500 rows. Phase 2's original candidate lookup
used the documented complete-name field.

Narrow-exact lookup of the documented short field against Itqan canonical names
plus `namings[]` produces this diagnostic distribution for the 2,001 otherwise
unmatched rows:

| short-field candidate profiles | rows |
|---|---:|
| 0 | 794 |
| 1 | 890 |
| 2 | 214 |
| 3–5 | 88 |
| 6–20 | 14 |
| >20 | 1 |

This is strong evidence of a systematic representation mismatch, but not proof
that the unique string candidate is the same person. Six unique short-field
candidates among the frozen 81 disagree with the existing provisional profile,
which independently demonstrates why automatic promotion is unsafe.

Itqan's local v1.20 snapshot contains 115,735 profiles, 196,488 raw
`namings[]` items, and 270,236 within-profile-unique canonical-or-naming
representations. Upstream describes variants across manuscripts and a merge of
three structured datasets plus 22 parsed classical texts. The local manifest
does not guarantee alias completeness; whether source-specific forms are omitted
and the upstream commit of this snapshot remain unknown.

### STRUCTURAL DISTRIBUTIONS

Median complete-name size is similar rather than sharply shorter in MIS:

| population | rows | mean chars | median chars | mean tokens | median tokens |
|---|---:|---:|---:|---:|---:|
| all MIS | 2,092 | 33.01 | 34 | 6.76 | 7 |
| frozen resolved MIS | 81 | 30.75 | 32 | 6.79 | 7 |
| ambiguous MIS | 10 | 32.40 | 34.5 | 7.50 | 8 |
| unmatched MIS | 2,001 | 33.10 | 34 | 6.76 | 7 |
| Itqan canonical | 115,735 | 40.91 | 33 | 8.81 | 7 |
| Itqan all profile representations | 270,236 | 38.35 | 29 | 8.13 | 6 |

The standout difference is orthographic: 1,894 / 2,001 unmatched complete
names contain alif maqsura and 1,628 have a structurally detected nisba-like
ending, versus 17 / 81 and 16 / 81 in the frozen resolved group. This is
descriptive association, not causality. Ninety-three unmatched names contain
punctuation; the source includes bracket annotations and contextual labels.

### CONTROLLED NORMALIZATION ABLATION

All transformations are diagnostic and `used_for_resolution=false`:

| transformation | coverage | unique | ambiguous | largest | frozen unique→ambiguous | new global collision keys |
|---|---:|---:|---:|---:|---:|---:|
| narrow / whitespace control | 0 | 0 | 0 | 0 | 0 | 0 |
| alif variants | 3 | 3 | 0 | 1 | 1 | 118 |
| ya/maqsura | 463 | 393 | 70 | 7 | 6 | 581 |
| ta-marbuta → ha | 0 | 0 | 0 | 0 | 0 | 51 |
| hamza carriers | 0 | 0 | 0 | 0 | 0 | 22 |
| ibn/bin | 0 | 0 | 0 | 0 | 1 | 293 |
| punctuation removal | 0 | 0 | 0 | 0 | 1 | 1,039 |
| alif + ya | 467 | 395 | 72 | 7 | 7 | 812 |
| alif + ya + bin + punctuation | 471 | 394 | 77 | 7 | 9 | 2,180 |

All 393 ya/maqsura-only unique hits differ solely at `ى`/`ي`, with no
additional character or token difference. Nonetheless, the fold creates 581
new global collision keys involving 1,542 profiles and makes six frozen unique
candidates ambiguous. It is not promoted.

### TOKEN AND DIRECTIONAL DIAGNOSTICS

Exact conservative token checks over the unmatched population find an Itqan
representation as an ordered subsequence of the longer MIS complete name for
1,931 rows; the reverse occurs for 72. These are usually highly ambiguous: the
former has a median 11 positive candidates and maximum 353, while the latter
has median 1 and maximum 14. Same-first-token occurs for 1,994 rows but has
median 409 positive candidates, so it is not useful identity evidence alone.

Against the top character diagnostic candidate, MIS is longer in 1,192 rows,
shorter in 223, and has the same token count in 586. This top-candidate
direction is diagnostic, not ground truth or recall measurement.

### FAILURE STRATA AND REVIEW

Priority-ordered, mutually exclusive descriptive strata are:

| stratum | population |
|---|---:|
| documented short name — one exact profile | 890 |
| documented short name — multiple exact profiles | 317 |
| normalization-only unique candidate | 72 |
| multiple normalization candidates | 16 |
| MIS name contained in Itqan representation | 27 |
| Itqan representation contained in MIS name | 649 |
| token-set containment with order difference | 11 |
| format/Unicode anomaly without prior candidate | 13 |
| no exact structural candidate | 6 |

The frozen unmatched diagnostic review has 146 rows (up to 20 per stratum),
seed `2026081604`, blank human labels, source complete and short names, and raw
candidate evidence. Scores and stratum metadata are stored separately. Its
allowed verdicts are `same_person`, `different_person`,
`plausible_but_uncertain`, `no_candidate`, and `NEEDS_DOMAIN_EXPERT`.

The full auto-resolved census has all 81 rows, seed `2026081603`, zero labels,
and hides tier, confidence, candidate counts, and selection rationale. The
original 117-row artifact is unchanged.

### DIAGNOSTIC DISCOVERY AND RELATIONSHIPS

Character trigram Jaccard, token Jaccard, and SequenceMatcher each retain top
three blocked candidates. Documented short-name narrow equality is included as
an unranked exact diagnostic method. Every row is labelled
`DIAGNOSTIC_CANDIDATE`, never `MATCH`; no recall claim is made.

Only the frozen 81 provisional profiles may serve as relationship anchors. Of
the unmatched rows, 233 have a resolved teacher anchor and 256 a resolved
student anchor. Some relationship support appears for 326 narrators / 363
diagnostic candidate rows. Missing support remains `UNKNOWN`; unresolved
candidates never anchor each other and nothing is promoted.

### CENTRAL ANSWER, LIMITATIONS, AND DECISION

The 2,001 narrators cannot be classified as genuinely absent from Itqan. The
data show a large systematic representation gap: 1,207 rows have at least one
exact candidate through MIS's documented short-name field, and most remaining
rows have exact normalization or token-containment structure. But neither that
evidence nor the diagnostic similarity lists establish person identity, and
the competing candidates are often numerous. Genuine absence versus same-person
alternative representation therefore remains unknown pending blinded human or
domain review.

Negative results are retained: baseline/whitespace, ta-marbuta, hamza, ibn/bin,
and punctuation each add zero unmatched coverage; gross name-length medians do
not support a simple “MIS is abbreviated” population-wide explanation; sparse
relationships do not justify propagation. No fuzzy resolver, weighted score,
ML/LLM adjudication, final narrator map, or graph was created.

**ENTITY-RESOLUTION GATE CLOSED.** The next permitted step is human/domain
review of the 81-row census and 146-row diagnostic sample, followed by measured
error and failure-mode reporting. Any resolver proposal must be a new versioned
experiment after that evidence exists.

## 14. Itqan Internal Identity / Duplication Audit

### QUESTION

Is an Itqan profile ID already a canonical historical-narrator identity, or can
multiple Itqan profile IDs represent records concerning the same person?

### WHY THIS BLOCKS MIS→ITQAN RESOLUTION

An MIS narrator cannot safely target exactly one Itqan profile if the target
profile set itself retains unresolved cross-source multiplicity. Conversely,
same-name Itqan profiles cannot be collapsed because homonyms and contradictory
biographies are also present. Record identity, upstream source-record identity,
and historical-person identity must therefore remain separate.

### ITQAN ID SEMANTICS

- **CONFIRMED:** the audited builder preserves foundation profile IDs and
  allocates sequential IDs for unmatched parsed entries. An ID is therefore a
  generated profile-record key.
- **INFERRED:** the README's “unified” framing indicates person-oriented intent,
  but neither code nor measured data guarantees one profile per historical
  narrator.
- **UNKNOWN:** no separate official canonical historical-person ID or complete
  profile-to-person crosswalk was found.

The audited upstream revision is
`199d870da5b726356b4a8dbaa096140cffb7d0ab`. The evidence paths and pinned URLs
are recorded in `itqan_profile_duplication_audit.json`.

### DATA GENERATION / MERGE SEMANTICS

The current builder starts from an AR-Sanad foundation, matches parsed classical
entries by exact normalized name and then unique four-/three-token prefixes,
adds a matched entry to `classical_sources[source]`, and creates a new profile
when no match is found. One profile can therefore contain multiple classical
sources. Kaggle `scholar_indx` is preserved as `global_id`; classical
`entry_id` values are source-local parser identifiers.

A separate deduplication script uses deterministic but heuristic
name/death/kunya/city rules and union-find absorption. The checked-in v1.20 data
and current code disagree: v1.20 profiles contain provenance/scoring fields the
current builder does not create, the current builder writes a 3.0 manifest,
and IDs listed as absorbed in `src/dedup_logs/dedup_layer2.json` remain in the
shipped v1.20 shards. The log is not evidence that the shipped snapshot had
those merges applied.

### DUPLICATION CANDIDATE METHOD

All 115,735 profiles were grouped under narrow exact normalization only:
Unicode NFC, Arabic combining-mark/tatweel removal, and whitespace collapse.
No Arabic base letters were substituted. Candidate grouping uses exact
canonical-name collisions, exact canonical-plus-`namings[]` collisions, exact
upstream record-key overlap, and deterministic biographical/source evidence.
No fuzzy match, weighted score, classifier, LLM adjudication, or merge is used.

`SAME_NAME_ONLY` means the exact representation has no qualifying composite
evidence. `POSSIBLE_DUPLICATE_PROFILE` requires shared source identity or an
identity-bearing exact representation plus an explicit conjunction/contradiction
rule. Missing values are `UNKNOWN`, never `FALSE`. Multiple grouping keys for
the same profile set are deduplicated for reported conceptual-group totals but
retained in the JSONL for reproducibility.

Strong duplication requires a group-wide upstream record key and no parsed
death contradiction. Strong distinctness is limited to a two-profile,
identity-bearing exact group whose parsed death ranges differ by more than five
years and which shares neither an upstream record key nor a classical source
entry. Source/key plus death conflict remains unresolved.

### GLOBAL RESULTS

| measure | result |
|---|---:|
| total profiles | 115,735 |
| distinct nonempty narrow canonical names | 85,890 |
| singleton canonical-name groups / profiles | 76,259 |
| duplicate canonical-name groups | 9,631 |
| profiles in duplicate canonical-name groups | 39,476 |
| exact canonical-plus-alias collision keys | 19,253 |
| profiles in any exact representation collision | 55,305 |
| candidate grouping keys with composite/contradictory evidence | 9,636 |
| unique suspected profile sets | 9,370 |
| profiles in suspected profile sets | 36,713 |
| strongly supported duplicate profile sets | 445 |
| strongly supported distinct-person sets (unique profile-ID sets) | 1,524 |
| unresolved profile-multiplicity sets | 7,401 |
| suspected sets containing strong death contradictions | 3,951 |

The largest canonical-name groups have 566, 351, 301, 291, and 283 profiles.
The largest alias collision is the contextual form `أبيه` with 1,301 profiles;
this is measured but excluded as identity-bearing evidence. These extremes also
indicate source/parser replication and contextual naming behavior, not just
ordinary homonymy.

### MIS-RELEVANT RESULTS

Current exact complete-name/alias candidates plus unmatched exact short-name
candidates touch 1,231 unique suspected Itqan profile sets: 41 have strong
upstream-key support without parsed death conflict, 233 have strong distinctness
evidence, and 957 remain unresolved. In all, 974 of 2,092 MIS narrators touch at
least one such set. These are exposure counts, not resolutions and not mutually
exclusive at the narrator level.

### PROVENANCE EVIDENCE

Profiles originate as 95,830 classical, 10,181 merged, 4,512 AR-Sanad, 3,508
GK imports, 1,081 Kaggle, and 623 AR-Sanad restores. `global_id` occurs on
11,262 profiles and equals `provenance.kaggle_id` throughout. It has 10,758
unique values, including 504 duplicated values spanning 1,008 profiles.

All 112,220 populated `provenance.arsanad_id` values equal their Itqan profile
ID, so that field is not an independent cross-profile identity key in this
snapshot. Top-level `gk_id` has 26,399 unique populated values and no duplicate.
There are 125,496 `(classical source, entry_id)` keys; 16,829 occur on multiple
profiles and touch 48,084 profiles. Parser construction and observed groups up
to size 24 show that these are source-local references, not canonical person
IDs. All per-source grades remain attached to their individual source entries.

### CONTRADICTIONS

Of the 504 duplicated Kaggle record keys, 445 profile pairs have no parsed
death contradiction and meet the strong-support rule; 59 contain incompatible
death evidence and remain unresolved. For example, Itqan profiles 7,922 and
9,331 both carry `global_id=11538`, but their death fields are 268 AH and 113
AH and their biographies differ. This is direct evidence that an upstream
record key must not be treated as infallible historical-person truth.

Across all suspected sets, 3,951 contain at least one strong death
contradiction. Only 1,524 two-profile sets meet the strict distinct-person rule;
larger, mixed, or source-conflicted groups remain unresolved.

### IMPACT ON 81 PROVISIONAL RESOLUTIONS

The frozen tiers remain 30 `EXACT_RESOLVED` and 51 `ALIAS_RESOLVED`. Of their
target profiles, 32 are audit-singletons, 49 belong to at least one suspected
profile set, and 37 touch a set with conflicting evidence. No status or mapping
was changed.

### IMPACT ON 890 SHORT-NAME UNIQUE CANDIDATES

The 890 remain diagnostic and unpromoted. Their target profiles split into 263
audit-singletons and 627 that belong to at least one suspected set. Overlapping
risk indicators include 10 targets in strongly supported duplicate sets, 132
in strongly supported distinct sets, 604 in unresolved sets, and 542 touching
contradictory evidence. “One exact representation candidate” is therefore not
equivalent to “one historical-person target.”

### REVIEW DESIGN

A new blinded 140-pair review CSV samples 20 rows each from exact same-name,
same-name-plus-kunya, same-name-plus-death, source-overlap, apparent
contradiction, large-collision, and MIS-relevant strata. Visible rows show raw
profile, biography, provenance, source, and mechanical shared evidence only.
Automatic class, candidate status, contradictions, and sampling stratum are in
the hidden companion. No automatic label, score, grouping confidence, or rank
is visible. Allowed verdicts are `SAME_PERSON`, `DIFFERENT_PERSON`, `UNCERTAIN`,
and `NEEDS_DOMAIN_EXPERT`; all reviewer fields start blank and the generator
refuses to overwrite nonblank reviewer values.

The 20 selected strict-triage cases were traced to complete profiles. All eight
diagnostic “duplication suspected” cases remain unresolved under primary
provenance rules. Two of ten “true person ambiguity” cases meet the mechanical
strong-distinct rule; the other eight remain mixed or incomplete. Both “mixed
uncertain” cases remain unresolved. These results audit selector labels and do
not convert them into human ground truth.

### LIMITATIONS

The current source tree does not fully reproduce the shipped v1.20 schema, so
some build history is unknown. Exact source keys can themselves carry erroneous
linkage, source-local entry IDs collide, alias fields contain contextual text,
and death parsing cannot interpret undated prose. Exact field agreement is
evidence, not historical proof. Large multi-profile groups and close
biographical distinctions require a hadith/rijal domain expert.

### DECISION

Model A (`MISNarrator → ItqanProfile`) is unsafe as a one-to-one identity model.
Model C is unsupported because no canonical Itqan historical-person identity
was found. The evidence requires a future Model B:
`MISNarrator → HistoricalNarrator → one or more ItqanProfiles`, with every
classical source judgement retained separately. No `HistoricalNarrator` layer,
canonical person ID, mapping, profile merge, grade collapse, or graph was
created in this milestone.

**ENTITY-RESOLUTION GATE CLOSED.** The next step is blinded review and domain
adjudication of the new pair artifact, followed by precision/failure-mode
measurement and only then a versioned canonical-person-layer design.

## 15. Itqan Source-Attachment Integrity and Identity-Evidence Audit

### QUESTION

Track A asks how often a namespaced upstream/classical source record is attached
to more than one Itqan profile and whether those attached profiles contain
explicit populated-field disagreements. Track B asks what provenance-bearing
evidence a future historical-person layer would require. The tracks remain
independent: this experiment does not create, cluster, or merge historical
identities.

### WHY SOURCE RECORD DUPLICATION != PERSON IDENTITY

A source key on two profiles proves only that one source-record identifier was
attached twice. That behavior can result from correct cross-profile linkage,
duplicate parsing, reused source-local numbering, or an incorrect builder
attachment. It is not historical same-person ground truth. Likewise, different
profile death fields are attachment-risk evidence and an automatic-merge
blocker, not adjudicated proof of two people.

The audit therefore keeps three units distinct:

1. namespaced source record;
2. Itqan profile;
3. future historical narrator.

### SOURCE ID SEMANTICS

Every key is a `(source_namespace, source_record_id)` pair. Numeric IDs from
different books or datasets are never mixed.

- `kaggle:scholar_indx` deduplicates top-level `global_id` and
  `provenance.kaggle_id` as two fields pointing to the same Kaggle record.
- `classical:<source>` uses each book name plus its source-local `entry_id`.
- `gk:top_level_id` and `gk:provenance_id` remain separate because their exact
  equivalence is not documented by the shipped v1.20 build.
- `arsanad:profile_row` is retained as row provenance. In all 112,220 populated
  cases it equals the Itqan profile ID and is not an independent person key.
- Repeated `classical_sources` and `provenance.sources` references to the same
  book/entry are one dependency, not two confirmations.

### SOURCE-KEY MULTIPLICITY

The corpus contains 320,557 source-record attachments over 278,381 namespaced
keys. Of these, 261,048 keys are singletons and 17,333 are attached to multiple
profiles. Multiprofile keys touch 48,556 distinct profiles.

| namespace | attachments | unique keys | singleton | exactly 2 | 3–5 | >5 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| arsanad:profile_row | 112,220 | 112,220 | 112,220 | 0 | 0 | 0 | 1 |
| classical:dhayl_diwan | 575 | 575 | 575 | 0 | 0 | 0 | 1 |
| classical:diwan_ducafa | 4,972 | 4,968 | 4,964 | 4 | 0 | 0 | 2 |
| classical:durar_kamina | 4,621 | 2,647 | 679 | 1,962 | 6 | 0 | 3 |
| classical:isaba | 10,132 | 9,427 | 8,722 | 705 | 0 | 0 | 2 |
| classical:jarh | 17,210 | 2,786 | 404 | 44 | 275 | 2,063 | 11 |
| classical:kamil | 2,247 | 2,178 | 2,109 | 69 | 0 | 0 | 2 |
| classical:kashif | 6,814 | 6,811 | 6,808 | 3 | 0 | 0 | 2 |
| classical:lisan_mizan | 9,899 | 8,455 | 7,032 | 1,402 | 21 | 0 | 3 |
| classical:macrifa_qurra | 625 | 624 | 623 | 1 | 0 | 0 | 2 |
| classical:mizan | 11,289 | 9,575 | 7,882 | 1,673 | 20 | 0 | 4 |
| classical:mucin_tabaqat | 1,998 | 1,998 | 1,998 | 0 | 0 | 0 | 1 |
| classical:mucjam_shuyukh | 832 | 832 | 832 | 0 | 0 | 0 | 1 |
| classical:mughni_ducafa | 6,115 | 6,115 | 6,115 | 0 | 0 | 0 | 1 |
| classical:siyar | 5,695 | 456 | 42 | 39 | 48 | 327 | 24 |
| classical:tabaqat | 4,435 | 4,194 | 3,954 | 239 | 1 | 0 | 3 |
| classical:tadhkirat_huffaz | 1,160 | 1,160 | 1,160 | 0 | 0 | 0 | 1 |
| classical:tahdhib_kamal | 11,153 | 7,276 | 3,723 | 3,264 | 289 | 0 | 5 |
| classical:tahdhib_tahdhib | 11,078 | 2,415 | 1,346 | 156 | 62 | 851 | 16 |
| classical:taqrib | 8,975 | 8,104 | 7,234 | 869 | 1 | 0 | 3 |
| classical:tarikh | 7,986 | 7,174 | 6,362 | 812 | 0 | 0 | 2 |
| classical:tarikh_islam | 23,189 | 23,189 | 23,189 | 0 | 0 | 0 | 1 |
| classical:thiqat | 16,168 | 14,537 | 12,914 | 1,615 | 8 | 0 | 3 |
| gk:provenance_id | 3,508 | 3,508 | 3,508 | 0 | 0 | 0 | 1 |
| gk:top_level_id | 26,399 | 26,399 | 26,399 | 0 | 0 | 0 | 1 |
| kaggle:scholar_indx | 11,262 | 10,758 | 10,254 | 504 | 0 | 0 | 2 |

The high multiplicities in `jarh`, `siyar`, and `tahdhib_tahdhib` show that
their parsed entry numbers cannot be treated as global historical-person IDs.

### BIOGRAPHICAL CONTRADICTIONS

For every multiprofile source key, populated canonical name, kunya, nasab,
death, city, tabaqa, and generation values are compared as `CONSISTENT`,
`CONTRADICTORY`, or `UNKNOWN`. Alias and teacher/student overlap can support
compatibility; absence of overlap remains `UNKNOWN` because those lists are
incomplete.

The attachment categories are:

| category | keys |
|---|---:|
| SOURCE_KEY_SINGLETON | 261,048 |
| SOURCE_KEY_MULTIPROFILE_NO_VISIBLE_CONTRADICTION | 547 |
| SOURCE_KEY_MULTIPROFILE_WITH_BIOGRAPHIC_CONTRADICTION | 16,786 |
| SOURCE_KEY_MULTIPROFILE_INSUFFICIENT_EVIDENCE | 0 |

Death comparisons retain raw fields, parsed intervals, minimum interval gap,
maximum endpoint difference, and a descriptive bucket. Across comparable
profile pairs inside duplicated keys: 356 have exactly equal death text, 802
overlap or have zero minimum gap, 815 have a 1–5 year gap, 2,742 have a 6–25
year gap, and 15,930 have a gap above 25 years. These thresholds prioritize
data-quality review only; they have no asserted historical meaning.

### HIGH-RISK ATTACHMENT CASES

The ranked CSV orders explicit contradictions first, then raw death spread,
number of contradictory fields, and multiplicity. It contains no identity
probability or weighted score.

`ITQ-DUP-0017` resolves to source key `("classical:tabaqat", "4507")`, attached
to profiles 2,695 and 70,395. Their names differ, their kunyahs differ exactly,
and their death values are 339/151 AH—a raw 188-year gap. The conservative
diagnosis is a suspicious or duplicated `tabaqat` attachment. No same-person or
different-person verdict follows from it.

### IMPACT ON MIS RESOLUTION

Among the frozen 81 provisional targets:

- 14 have `LOW_TARGET_DATA_RISK`;
- 6 have profile-multiplicity risk only;
- 61 have multiple risks;
- 58 contain a duplicated source attachment;
- 49 touch a suspected internal profile set;
- 61 have biographical-contradiction exposure;
- 2 share a duplicated upstream key;
- 58 share duplicated classical entry keys.

Among the 890 exact-short-name unique diagnostic targets:

- 55 have `LOW_TARGET_DATA_RISK`;
- 10 have profile-multiplicity risk only;
- 825 have multiple risks;
- 768 contain duplicated source attachments;
- 627 touch suspected internal profile sets;
- 825 have contradiction exposure;
- 13 share duplicated upstream keys;
- 764 share duplicated classical entry keys.

No tier or mapping changed. These counts answer how many targets point into
structurally clean neighborhoods, not how many narrators are resolved.

### IDENTITY EVIDENCE MODEL

The schema-only model separates stronger identity-bearing evidence, supporting
evidence, contradictions, and missing evidence. Every future evidence item must
retain raw value, source namespace and record ID (or `UNKNOWN`), profile ID,
parser/builder status, dependency group, and review status.

A stable upstream key may become stronger evidence only after both its person
semantics and its attachment integrity are independently confirmed. Names,
aliases, kunya, nasab, city, generation, death, teachers, students, and shared
source references remain supporting evidence until calibrated through review.

### EVIDENCE DEPENDENCE / CORRELATION

There are 21,593 profiles with multiple classical records. However, v1.20 has
no field-level source pointer for `full_name`, `namings`, kunya, nasab, death,
city, tabaqa, generation, teachers, or students. Their independence is
therefore `UNKNOWN`.

All 11,262 profiles with both `global_id` and `provenance.kaggle_id` have equal
values; these are two fields for one linkage, not two confirmations. A
classical grade and its mirrored provenance entry are likewise one dependency.
Matching name/death/kunya values copied from one record count as one correlated
evidence unit.

### FUTURE HISTORICAL NARRATOR CONTRACT

The proposed contract is not instantiated. It minimally requires:

- opaque `historical_narrator_id` assigned only after authorization;
- provenance-backed display name;
- uncertainty-aware identity status;
- profile-membership assertions with supporting and contradicting evidence IDs;
- raw aliases with provenance;
- evidence and contradiction records;
- review events and immutable source-profile links.

Allowed future statuses are `PROVISIONAL`, `REVIEWED`,
`DOMAIN_EXPERT_CONFIRMED`, `AMBIGUOUS`, and `QUARANTINED`. Source profiles are
never absorbed. Singleton and unresolved entities remain valid. Aggregated
`narrator.grade` and merged profile payloads are forbidden.

### EXPERT REVIEW BOUNDARY

Mechanical review covers key reuse, missing fields, exact populated-value
disagreement, parser duplication, and numeric death spread. It does not need a
rijal expert.

The 40-row expert packet contains all 25 biographically compatible cases, all
three relationally compatible cases, and 12 largest death-gap cases without a
shared source key. The 22 source-attachment cases and 35 insufficient-evidence
cases are excluded: the former first require data-quality investigation, and
the latter lack enough material for useful historical adjudication.

Allowed blank expert verdicts are `SAME_HISTORICAL_PERSON`,
`DIFFERENT_HISTORICAL_PERSON`, `UNCERTAIN`, and
`INSUFFICIENT_SOURCE_EVIDENCE`. No automatic label, score, confidence, rank, or
expected answer is visible.

### LIMITATIONS

Different populated names, kunyahs, locations, or dates are attachment-risk
signals, not automatically historical contradictions. Death prose is reduced
only to explicit numeric intervals. Source-local entry numbering may have been
reused by parsing. Field-level provenance is unavailable for most profile
biography fields. The audit therefore measures structural corruption exposure,
not the truth of historical identities or source texts.

### DECISION

Source-attachment integrity must be investigated before source overlap can be
used as historical-person evidence. The explicit identity-evidence contract is
ready for review, but no `HistoricalNarrator` instance, person map, merged
profile, final MIS mapping, grade aggregation, or graph was created.

**ENTITY-RESOLUTION GATE CLOSED.** The next permitted step is mechanical review
of prioritized source-attachment risks and domain review of the bounded
40-case historical packet, followed by measured error and abstention behavior.

---

## 16. Historical Identity Calibration

### QUESTION

Not "how do we merge profiles" but "what observable evidence would be enough to
identify one historical narrator without creating unacceptable false merges?"
A false merge silently corrupts every isnad that touches it; an unresolved
narrator only costs coverage. Abstention is therefore a success state, and every
rule below is measured by the damage it would do rather than the reach it adds.

### WHY PROFILE != PERSON

Established earlier and unchanged: `itqan_id` is a generated record key, not a
canonical historical-person ID. This experiment adds the identity layer's own
consequence — that no amount of agreement between two profiles is confirmation
when the agreeing fields cannot be traced to independent records.

### CALIBRATION INPUT

The frozen 40-row expert packet, reproduced byte-for-byte
(`e8e4335ada47e439573853cba5871511aac47f59c6bfed99c5c81ce5a2a747a0`), plus the
19,757 audited duplication groups and the full 115,735-profile corpus. The
packet composition verifies against its metadata: 25 biographically compatible,
3 relationally compatible, 12 largest death gaps without a shared source record.
Reviewer columns are blank in all 40 rows and no score, rank or automatic label
is among its visible columns.

One blinding gap was found and is recorded rather than patched:
`source_review_id` joins back to the strict triage file, which holds
`assistant_mechanical_triage`. The label is not visible in the packet, but it is
one join away, so future packets must carry an opaque row ID.

### EVIDENCE TAXONOMY

Derived from the fields the corpus actually carries, not from a template.

**A — identity-bearing: empty.** No field in v1.20 identifies a person
independently of the name being compared. `itqan_id` is generated,
`provenance.arsanad_id` equals it in all 112,220 populated cases, classical
`entry_id` is source-local, `gk_id` is assigned by Itqan's own matching, and
`unique_key` is derived from the name itself.

**B — supporting:** full_name, namings, kunya, nasab, laqab, city, death,
tabaqat, generation, teachers, students, classical_sources.

**C — contradicting:** only what a machine can check — an explicit disagreement
between parsed death intervals, or a relational cycle. A differing kunya or
nisba is recorded as `DIFFERENT`, never as a contradiction: whether a variation
is incompatible is a rijal question, not a string comparison.

**D — non-independent:** `global_id` == `provenance.kaggle_id`;
`provenance.arsanad_id` == profile id; a classical grade mirrored into
`provenance.sources`; Itqan's own `unique_key`/`uniqueness`/`confidence`/
`id_score`; and every profile biography field, which has no source pointer.

**E — unknown:** missing stays missing, and is never read as a difference.

### EVIDENCE INDEPENDENCE

The decisive measurement: **0 of the 40 pairs share a single independent source
record.** None share a source key at all, by construction of the packet, and
`arsanad:profile_row` is excluded because it merely repeats the profile ID.

Worse for any future rule, v1.20 carries no field-level provenance, so
`full_name`, `death`, `kunya`, `nasab`, `city`, `tabaqat`, `generation`,
`teachers` and `students` collapse into **one dependency group per profile** of
unknown origin. Two profiles agreeing on five fields is therefore one
unattributable agreement, not five confirmations. Every independence claim in
this corpus is `UNKNOWN`.

### POSITIVE ANCHOR SEARCH

Searched for a genuinely independent identity relation: a shared `unique_key`, a
shared `gk_id`, a shared Kaggle `scholar_indx`, and any explicit cross-reference
field. Across the 40 pairs: 0 share a `unique_key`, and of the 12 pairs where
both profiles carry a `gk_id`, 0 share it.

**NO GOLD-STANDARD POSITIVE IDENTITY ANCHOR FOUND.** This is a result, not a
gap in the search: it means no rule in this corpus can be validated against a
known-correct positive, and the first real positive labels must come from
adjudication.

A related negative result, measured here for the first time: Itqan ships its own
identity machinery — `unique_key`, `uniqueness`, `confidence` (A–F), `id_score`
(15–90), `id_flags`, and `gk_match_method`. It cannot be used. `unique_key` is
computed from the same name evidence being compared, so it is circular; and in
**25.7% of the 99,596 `name_unique` profiles its name core does not match the
profile's own `full_name`**, frequently naming an ancestor from the nasab chain
instead. `gk_match_method` further shows the GK linkage itself was made by
`prefix3_unique`, `naming_variant` and `prefix4_death_±1` heuristics — precisely
the fuzzy matching this project rejected.

### NEGATIVE ANCHOR SEARCH

Four pairs share an exact name form while their reported deaths differ by more
than 25 years — shared representation with strong independent evidence pointing
away from one person. With `ITQ-DUP-0017` (one classical `tabaqat` entry
attached to profiles 188 years apart) these are the corpus's clearest
demonstrations that name agreement, and even record sharing, are not identity.

### 40-CASE CALIBRATION RESULTS

| mechanical status | cases | of which share a name form |
|---|---:|---:|
| REQUIRES_DOMAIN_EXPERT | 16 | 11 |
| SOURCE_DATA_CONTRADICTION | 12 | 4 |
| INSUFFICIENT_EVIDENCE | 10 | 10 |
| STRONGLY_COMPATIBLE_BUT_UNCONFIRMED | 2 | 2 |

No case received `SAME_PERSON` or `DIFFERENT_PERSON`; no authoritative crosswalk
exists to justify either. Relational evidence is mostly absent — 31 of 40 pairs
have no comparable teacher/student neighbourhood, 6 share one, and 3 have
populated neighbourhoods that do not overlap. Chronology found no mechanical
impossibility in any case: 12 show a suspicious death separation, which is
explicitly not the same claim.

### RULE CANDIDATES AND FAILURE ANALYSIS

Seven rules were defined and exercised against the 19,757 audited groups. The
decisive column is the third: a rule that fires on sets the audit already
supports as *distinct people* would manufacture false merges.

**Units.** The audit emits **grouping records**, not profile sets: one set of
profile IDs can appear under more than one grouping key, so the same set is
counted once per key. The corpus holds 19,757 grouping records over 19,410
unique profile-ID sets. In the distinct-person class specifically, 1,569
records — 468 under `NARROW_CANONICAL_NAME` and 1,101 under
`NARROW_EXACT_REPRESENTATION` — collapse to **1,524 unique profile-ID sets**,
which is the figure §14 reports. Both numbers are correct; they count different
things, and neither may be called "sets" without qualification.

Both views are reported below. Neither is precision or accuracy: no adjudicated
historical-person labels exist.

| rule | triggered records | triggered sets | strongly-distinct records | strongly-distinct sets | abstention | status |
|---|---:|---:|---:|---:|---:|---|
| R-01 shared upstream record key | 983 | 837 | 0 | 0 | 95.0% | REJECTED |
| R-02 full biography agreement | 806 | 796 | 0 | 0 | 95.9% | NEEDS_MORE_EVIDENCE |
| R-03 Itqan native identity fields | not testable here | — | — | — | — | REJECTED |
| R-04 adjacent IDs, same name and death | 9 | 9 | 0 | 0 | 99.95% | SAFE_FOR_FURTHER_VALIDATION |
| R-05 arsanad_restore stub absorption | 171 | 171 | 0 | 0 | 99.1% | NEEDS_MORE_EVIDENCE |
| R-06 relational neighbourhood overlap | 3,165 | 3,036 | **305** | **280** | 84.0% | DOMAIN_EXPERT_REQUIRED |
| R-07 exact name equality alone | 19,253 | 19,036 | **1,569** | **1,524** | 2.6% | REJECTED |

R-07 fires on *every* strongly-distinct set in the corpus — all 1,524 of them,
under 1,569 grouping records — while abstaining on
almost nothing — the exact collision behaviour the whole audit exists to
prevent. R-06 touching 305 of them shows a shared teacher list is not identity
evidence either. R-03 could not be exercised on the group payload; reporting it
as "0 triggered" would have read as safe, so it is reported as untested and was
rejected on the direct 25.7% corpus measurement instead.

These are **proxy safety measurements, not precision.** No adjudicated identity
labels exist, so no precision, recall or accuracy figure is computable and none
is reported.

### IMPACT ON THE 81 AND THE 890

Unchanged and unpromoted. The 81 remain 14 `LOW_TARGET_DATA_RISK`, 6
multiplicity-only, 61 `MULTIPLE_RISKS`; the 890 remain 55 / 10 / 825. No tier
moved. Calibration changes what we know about the evidence, not the tiers.

### MECHANICAL AND DOMAIN-EXPERT BOUNDARY

A machine can answer: same source key, same field value, explicit numeric death
disagreement, same teacher or student ID, source independence, and what is
missing. 10 of the 40 cases are closed mechanically as
`INSUFFICIENT_EVIDENCE` — no specialist time is warranted on them.

**30 of 40 require a rijal specialist**, and each carries the specific question
to answer: whether two death reports are accepted opinions for one narrator,
whether an abbreviated or variant name form refers to this narrator, and whether
agreement across every populated field is one narrator recorded twice or two
narrators sharing a name, kunya and death year. Reviewing CSV rows is not the
same skill; these are not questions the engineering owner should be asked to
adjudicate.

### VALIDATION PROTOCOL

Specified in `historical_identity_validation_protocol.md`. The statistical goal
is stated before the sample size: a rule is adopted only if its false-merge rate
is credibly below a ceiling, sized by the rule of three — zero false merges in
`n` adjudications puts the 95% upper bound at `3/n`. A 1% ceiling gives n = 300
per auto-merging rule; a review-flag-only rule is validated at n = 60. Seven
strata, two independent specialists, blind adjudication, kappa >= 0.6 required
before any sample validates anything, and a citation required to support a
`SAME_HISTORICAL_PERSON` verdict.

### HISTORICALNARRATOR CONTRACT

Described, deliberately not instantiated. Calibration adds four requirements the
earlier sketch lacked: every evidence item carries a `dependency_group_id`,
because same-record evidence must never count twice; membership is an assertion
with its own status rather than a foreign key, so a profile can be attached
provisionally and detached without deletion; `QUARANTINED` is distinct from
`AMBIGUOUS`, separating a profile whose own record integrity is in doubt from a
genuinely uncertain identity; and death is a list of reported opinions with
sources, never one canonical value. Singleton and unresolved narrators stay
valid terminal states. Grade aggregation, merged payloads and transitive
identity propagation remain forbidden.

### FAILED / REJECTED RULES

R-07 (name equality alone), R-01 (shared upstream record key), and R-03 (Itqan's
native identity fields) are rejected with recorded reasons. R-06 is confined to
single-hop supporting evidence: propagating it would bootstrap identity across
the graph, which is prohibited.

### UNKNOWN

Whether any of the 40 pairs is one historical person. Whether the agreeing
fields in the 2 strongly-compatible cases are independent or copied. The
direction of derivation between an `arsanad_restore` stub and its classical
counterpart. Whether the 25.7% `unique_key` divergence is a builder defect or an
undocumented convention.

### LIMITATIONS

The taxonomy is derived from one corpus snapshot and one 40-case packet, which
is a calibration sample rather than a representative one. Death evidence is
reduced to explicit numeric intervals; prose disagreement is not parsed. Name
decomposition into ism/nasab/kunya/nisba is not attempted — no deterministic
parser exists and hallucinated decomposition would be worse than none. Rule
safety is measured as exposure to audited classes, and those classes are
evidence labels, not historical ground truth.

### REPRODUCIBILITY AND BLINDING FIXES

Two defects surfaced by this calibration were repaired afterwards.

**Working-directory-dependent data paths.** `ITQAN_DIR`, `MIS_DIR` and the two
default artifact paths in `audit_linkage_validation_identity` were declared
relative, so they resolved against the caller's working directory rather than
the project. Running any audit from another directory produced **zero profiles
with no error** — a measured population of 0 that would have been reported as
though it were real. All four now derive from `config.BASE_DIR`, which is
computed from the module location, and `load_profiles()` raises a
`FileNotFoundError` naming the directory and pointing at `DATA_SOURCES.md`
instead of returning an empty list. Tests assert that the resolved paths are
identical from the repository root and from an unrelated directory, that a
relative path would have differed, and that absent shards raise.

The refactor is behaviour-preserving: the calibration artifacts reproduce
byte-for-byte afterwards, and the frozen linkage and 40-row packet hashes are
unchanged.

**One-join blinding weakness.** The 40-row calibration packet exposed
`source_review_id` and both Itqan profile IDs. Each of the three joins directly
to `itqan_profile_duplication_strict_mechanical_triage.csv`, which carries
`assistant_mechanical_triage`. No label was ever visible in the packet, and the
40 rows were never adjudicated, so no verdict is contaminated — but a reviewer
could have reached the machine's opinion in one lookup, which is a weakness in
the artifact, not in the results.

Future packets close it. `build_blinded_packet` emits an opaque
`HIR-000001` identifier, redacts every identifier key from the evidence
payloads at any depth, shuffles rows under a recorded seed so position carries
no signal, and writes the mapping to a separate hidden file that is never given
to the reviewer. A leakage report is computed on every build and the generator
refuses to write a packet that would expose a join key or an automatic label.
One residual vector is recorded rather than hidden: teacher and student profile
ID lists remain visible because they are evidence a specialist needs, and
recovering the pair from them would require corpus-wide matching rather than a
lookup.

### DECISION

The evidence needed to identify a historical narrator is not present in this
corpus: there is no identity-bearing field, no independent corroboration in any
of the 40 pairs, and no positive anchor to validate against. Two rules are worth
carrying forward (R-04 as a data-quality flag, R-05 with more evidence); three
are rejected outright.

**ENTITY-RESOLUTION GATE CLOSED.** No `HistoricalNarrator` instance, person map,
merged profile, final MIS mapping, grade aggregation or graph was created. The
next permitted step is adjudication under the validation protocol — the gate
opens on adjudicated identity evidence, never on rule coverage.

---

## 17. Deterministic MIS Sanad Graph — Chain Layer

### QUESTION

Can the sanad chain layer be built, verified and queried using MIS narrator
identities alone, while Itqan historical-person identity stays unresolved? The
readiness assessment argued yes from source measurements; this builds it and
checks the claim against a rebuilt database.

### SOURCE SEMANTICS

Keys were measured before the schema was written, not assumed.

`HadithNo` alone is unique across all 7,748 MIS hadiths, and so is
`(BookNo, HadithNo)`; `ChapterNo` and `UnitNo` are functionally determined by
that pair (0 hadiths carry more than one chapter/unit). The composite
`(book_no, hadith_no)` is used as the primary key rather than the bare hadith
number, because it is how every edge addresses a hadith and it keeps the source
identity intact.

An isnad is `(BookNo, HadithNo, SanadNo)` → 14,155 chains. Adding chapter and
unit to the key changes nothing, and no edge disagrees with its hadith's
chapter/unit (0 of 63,642). A transmission step is that key plus its position,
unique across all 63,642 rows; the full `intractionLabel` is likewise 63,642
distinct and is stored verbatim as provenance.

`SanadCount` parses as an integer in all 7,748 rows.

### SCHEMA

Four tables, no decorative nodes:

- `mis_narrator` — `narrator_id` PK, complete Arabic name, mapped short name,
  English mapped name, gender, generation.
- `mis_hadith` — `(book_no, hadith_no)` PK, chapter/unit, titles, declared
  sanad count.
- `isnad` — `(book_no, hadith_no, sanad_no)` PK, step and narrator counts,
  FK to its hadith.
- `transmission` — `(book_no, hadith_no, sanad_no, position)` PK,
  `from_narrator_id` → `to_narrator_id`, unique `source_label`, FKs to the
  isnad and to both narrators.

Direction is stored as MIS records it: `from` is the narrator transmitted from,
`to` the one who received. No `ItqanProfile`, `SourceRecord`,
`HistoricalNarrator`, candidate link or grading table exists, and the build
raises if any appears.

### BUILD

`python -m src.build_sanad_graph` reads the frozen workbooks and writes a
git-ignored `data/processed/sanad_graph.sqlite` plus a manifest. Paths derive
from the project root, so the build does not depend on the working directory.

Constraints are enforced by the database rather than by tests alone: primary
keys, composite foreign keys, a unique source label, and `CHECK` constraints on
position and on `narrator_count = step_count + 1`. `PRAGMA foreign_keys` is on,
and `PRAGMA foreign_key_check` runs after load.

### POPULATION COUNTS

| table | rows | source |
|---|---:|---:|
| `mis_narrator` | **2,092** | 2,092 |
| `mis_hadith` | **7,748** | 7,748 |
| `isnad` | **14,155** | 14,155 |
| `transmission` | **63,642** | 63,642 |

### CHAIN FIDELITY

Every chain was rebuilt from SQLite and compared step by step against the
workbook: **14,155 exact, 0 mismatched, 0 missing, 0 extra.**

Structural checks are all clean: 0 dangling `from` endpoints, 0 dangling `to`
endpoints, 0 isnads without a hadith, 0 broken chain transitions, and 0
narrators unreferenced by any edge.

### EDGE FIDELITY

63,642 stored transmissions against 63,642 source edges, with 63,642 distinct
`source_label` values — no duplication and no loss.

### MULTI-ISNAD FIDELITY

Declared `SanadCount` was compared with the number of stored isnads for all
7,748 hadiths: **0 mismatches.** Chains from one hadith are never merged; each
is addressable by its sanad number, and the query API returns them as separate
records.

### DETERMINISM

Two builds from identical inputs produce the **same canonical hash** —
`496ccf1da21d2e849a94fb2d2e0d4ae66e3bfa549f4ce555f5cf2f4d490bfbce` — computed
from the schema plus every table's rows in primary-key order. The two files
also happened to be byte-identical and the same size, but that is not claimed
as a guarantee: SQLite's format carries non-semantic variation, so logical
content is what is hashed and what the manifest records.

### DIRECTION — MEASURED, NOT ENFORCED

MIS records `source → target` as the direction of transmission, and the
generation labels agree overwhelmingly: 41,687 steps run earlier generation to
later, 21,692 within one generation, 220 involve an unranked `NotMapped`
narrator — and **43 run later to earlier**.

Those 43 are preserved exactly as recorded. An elder narrating from a junior is
a recognised occurrence in transmission, so a constraint forcing generation
order would have corrupted real source records to satisfy a rule the source
never claimed. The count is reported in the manifest instead.

### QUERY API

`src/sanad_graph.py` — deterministic reads, no model, no ranking, no inference:
`get_narrator`, `get_mis_hadith`, `get_isnads_for_mis_hadith`,
`get_ordered_chain`, `get_hadiths_for_narrator`, `get_predecessors_in_chain`,
`get_successors_in_chain`.

Every result carries `recorded_in: "MIS"`, narrator results carry the MIS ID
with both name forms and the generation, and chain results carry positions.
Predecessor and successor queries are scoped to one named isnad and say so in
the payload: a single occurrence is not a general claim about who taught whom.

Absence is typed rather than empty. An unknown narrator, hadith or isnad raises
`UnknownNarratorError`, `UnknownHadithError` or `UnknownIsnadError`; a known
narrator with no recorded transmission returns an empty occurrence list. A
caller can always distinguish a bad identifier from a valid record with nothing
recorded.

### PERFORMANCE

| step | measured |
|---|---|
| workbook read | 7.29 s |
| database build + constraint load | 1.18 s |
| full rebuild | **8.47 s** |
| all-chain validation (14,155) | 0.43 s |
| canonical hash | 0.78 s |
| database size | 11.8 MB |

Query medians: `get_narrator` 0.069 ms · `get_isnads_for_mis_hadith` 0.141 ms ·
`get_successors_in_chain` 0.271 ms · `get_ordered_chain` 0.577 ms · the busiest
narrator's 1,996 occurrences 9.4 ms. Nothing was optimised, because nothing is
slow.

### SAFE CAPABILITIES

Answerable now, as recorded in MIS: the ordered isnads of a hadith; the
narrators in a chain with their positions; every hadith and chain a narrator
appears in; who precedes or follows a narrator within a named chain; how many
chain variants a hadith has; a narrator's MIS-recorded generation and name
forms.

### BLOCKED CAPABILITIES

Unchanged by this milestone: all classical gradings for a narrator; a narrator's
biography; whether a MIS narrator is the same person as an Itqan profile;
whether two differently-named profiles are one person; any chain-wide
reliability judgement. These need the identity layer, which does not exist.

### LIMITATIONS

MIS narrator IDs are stable and non-colliding inside this frozen snapshot; they
are not canonical historical-person identifiers, and 14 short/mapped names are
still shared by more than one ID. 80 narrators carry `NotMapped` as their
generation. Coverage is MIS's own: 7,748 MIS hadiths, of which 7,015 have an
accepted link to the local corpus — the local hadiths are deliberately not
attached in this milestone, so the chain graph stands or falls on its own. The
graph records transmission as MIS asserts it and does not verify those
assertions against the classical literature.

### DECISION

The chain layer is built, verified and reproducible on MIS identities alone,
which confirms the decoupling the readiness assessment proposed: chain structure
does not depend on historical-person identity.

**ENTITY-RESOLUTION GATE CLOSED.** No Itqan profile, source record, grading,
candidate identity link or `HistoricalNarrator` exists in the graph, and the
build fails if one appears. The frozen linkage is unchanged and remains
readable at 7,015 rows.

---

## 18. Local Hadith ↔ MIS Graph Attachment

### QUESTION

Can a hadith returned by the matn retrieval pipeline be connected, deterministically
and without guessing, to the isnads recorded for it in MIS? The chain layer was
built to stand alone; this attaches the local corpus to it through the frozen
linkage and nothing else.

### FROZEN LINKAGE

Consumed, never recomputed. `mis_linkage_accepted_v1.jsonl`,
`9c3a48e7…a572c77`, 7,015 rows, every one `accepted: true` and
`candidate_status: unique`. The builder refuses to load a file containing a
non-accepted row.

Its endpoints were measured rather than assumed: the local side is
`our_idInBook` (7,015 unique, 0 null) and the MIS side is `mis_HadithNo`
(7,015 unique, 0 null). There is no `mis_BookNo` field, and none is needed —
`book_no` is `'2'` for all 7,748 MIS hadiths, so the graph key
`(book_no, hadith_no)` is reached with the book held constant and recorded
explicitly rather than inferred per row.

Resolution against the graph before any schema change: 0 duplicate local
sources, 0 duplicate MIS targets, 0 local sources absent from the corpus, 0 MIS
targets absent from `mis_hadith`. Strict 1:1 confirmed.

### SCHEMA EXTENSION

Two tables, and deliberately not one. `local_hadith` is keyed by the corpus
`id` with `id_in_book` unique beside it; `hadith_mis_link` carries the local id,
the MIS composite key, and the linkage's own provenance — version, artifact
SHA-256, candidate status and both similarity scores.

A local hadith and a MIS hadith are different records from different corpora.
The accepted mapping happens to be 1:1 today, which is a fact about this
artifact, not a licence to store them in one row: the linkage is revisable and
the two identities are not.

The relation is named `LINKS_TO_MIS_RECORD` with status `ACCEPTED_LINK_V1`. It
is not called `SAME_HISTORICAL_HADITH`, because the frozen artifact records a
narrow-normalised textual match, and no document in this project adjudicates
the stronger claim.

Local Arabic text is **not** stored. It is 7.2 MB the retrieval layer already
owns, and the join needs identity, not content — the database grew 11.8 → 13.8 MB
as it is.

### POPULATION

| table | rows |
|---|---:|
| `mis_narrator` | 2,092 |
| `mis_hadith` | 7,748 |
| `isnad` | 14,155 |
| `transmission` | 63,642 |
| `local_hadith` | **7,459** |
| `hadith_mis_link` | **7,015** |

Every local hadith is present, linked or not. Every MIS hadith remains, linked
or not. Neither side was trimmed to make the join look complete.

### LINKAGE FIDELITY

Every frozen mapping compared against the database:

| check | result |
|---|---:|
| accepted source links | 7,015 |
| stored links | 7,015 |
| exact matches | **7,015** |
| missing | 0 |
| extra | 0 |
| duplicate local endpoints | 0 |
| duplicate MIS endpoints | 0 |
| dangling local endpoints | 0 |
| dangling MIS endpoints | 0 |

Enforced in the schema rather than only in tests: `local_id` is the primary key
and `id_in_book` is unique, so one accepted link per local hadith;
`UNIQUE (mis_book_no, mis_hadith_no)` gives one per MIS hadith; three foreign
keys reject a dangling endpoint; and a `CHECK` rejects any status other than
`ACCEPTED_LINK_V1`. A duplicate mapping fails loudly.

### COVERAGE

| side | linked | unlinked | linked % |
|---|---:|---:|---:|
| local corpus (7,459) | 7,015 | **444** | 94.05% |
| MIS (7,748) | 7,015 | **733** | 90.54% |

This is linkage coverage, not identity accuracy, and the artifact says so in
its own field name. The 444 local and 733 MIS hadiths outside the accepted set
are first-class records that report their own missing layer.

### RETRIEVAL IDENTIFIER JOIN

Retrieval was not changed — no embedding, index, BM25, RRF or reranker was
touched. What was needed was proof that its identifier joins.

`src/ingest.py` sets `hadith_number` from the corpus `id`, and `retrieve.py`
surfaces it as `hadith_id`. That is the corpus `id` (range 7,278–14,736), not
`idInBook` (1–7,459) — both unique, and the linkage keys on the latter, so
`local_hadith` stores both and the join runs `id → id_in_book → link`.

Measured over the whole chunk store: 7,570 chunks carry 7,459 distinct
identifiers, **0 of which fail to resolve** to a `local_hadith`; 7,015 reach an
accepted link and 444 do not, exactly matching the unlinked population.

Confirmed end to end on real retrieval output, with no LLM call: querying the
dense matn retriever and traversing each returned `hadith_id` produced
`local hadith → ACCEPTED_LINK_V1 → MIS 2/2327 → 1 isnad → 5 narrators` and
similar for every result inspected.

### QUERY API

`get_local_hadith`, `get_mis_record_for_local_hadith`,
`get_isnads_for_local_hadith`, `get_ordered_chains_for_local_hadith`,
`get_local_hadith_for_mis_record`, `linkage_coverage`. Deterministic reads, no
model, no ranking.

Every traversal result keeps the three layers visibly separate — `local_hadith`,
`linkage` (status, relation, version, artifact SHA-256), `mis_hadith`, then
`isnads` and `chains`. The linkage is never collapsed into the answer.

### ABSTENTION

Four states, distinguishable rather than all rendered as an empty list:

- `INVALID_LOCAL_HADITH_ID` → `UnknownLocalHadithError`;
- `VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK` → `NoAcceptedMisLinkError`,
  carrying the local id, for all 444 unlinked hadiths;
- `VALID_LINKED_HADITH_WITH_NO_RECORDED_ISNAD` → returned as a status with an
  empty `isnads` list;
- `INVALID_MIS_RECORD` → `UnknownHadithError`.

Reverse lookup adds `VALID_MIS_RECORD_BUT_NO_ACCEPTED_LOCAL_LINK` for the 733.
A caller can always tell which layer is missing.

### DETERMINISM

Two builds from identical inputs: identical row counts, identical accepted-link
population, identical file size, and identical hashes.

Adding tables would have changed a whole-database hash, so the canonical hash is
now computed per layer, with `sqlite_master` filtered to the layer's own tables.
The chain hash is therefore **unchanged**:

```
MIS_CHAIN_HASH   496ccf1da21d2e849a94fb2d2e0d4ae66e3bfa549f4ce555f5cf2f4d490bfbce
FULL_GRAPH_HASH  c8818da00bf27f74750105ed6bf2d57e674c26e3dfe63b9ec8774c6a4d6e481c
```

`canonical_graph_sha256` in the manifest still holds the MIS-chain value, so the
identity earlier milestones pinned did not silently become a different number.
A test asserts the chain hash survives deleting the entire local layer, and that
the full hash does not.

### PERFORMANCE

Full rebuild **9.0 s** (7.7 s reading workbooks, corpus and linkage; 1.3 s
building) to a **13.8 MB** database. Query medians over 200 runs:
`get_local_hadith` 0.148 ms · `get_local_hadith_for_mis_record` 0.184 ms ·
`get_mis_record_for_local_hadith` 0.191 ms · `get_isnads_for_local_hadith`
0.313 ms · `get_ordered_chains_for_local_hadith` 0.806 ms. Nothing optimised.

### SAFE CAPABILITIES

A retrieved hadith can now be connected to its recorded isnads: the ordered
chains of a local hadith, its MIS record, the narrators and their positions, the
chain-variant count, and the reverse direction from a MIS record to its local
hadith — each answered *as recorded in MIS, via the frozen accepted linkage*,
with the linkage visible in the result.

### STILL BLOCKED

Everything that needs historical-person identity: narrator gradings, narrator
biography, whether a MIS narrator is a given Itqan profile, and any reliability
judgement about a chain. No Itqan profile, source record, grading, candidate
identity link or `HistoricalNarrator` exists in the database — verified by table
and column inspection, and the build fails if one appears.

### LIMITATIONS

Coverage is partial by construction: 444 local hadiths have no accepted MIS
record and 733 MIS records have no accepted local hadith, so a retrieval answer
may legitimately have no chain to show. The link asserts a frozen textual match,
not that two records are the same historical hadith. `book_no` is held constant
at `'2'` because this corpus is one book; a multi-book MIS snapshot would need
the book carried in the linkage artifact itself. The graph stores no local text,
so any presentation of the matn still comes from the retrieval layer.

### DECISION

The retrieval pipeline and the sanad graph are now joined by a deterministic,
provenance-carrying path, and the chain layer kept its identity while gaining
one. **ENTITY-RESOLUTION GATE REMAINS CLOSED** — attaching the local corpus
required no identity claim and made none.

---

## 19. Deterministic Retrieval → Sanad Context Surface

### WHAT THIS IS, AND IS NOT

A read-only composition API over reads that already existed. It is **not** an
agent, **not** routing, **not** query classification, and **not** GraphRAG
orchestration. It adds no capability: no search, no scoring, no ranking, no
inference, no identity reasoning, and no model or network call of any kind.

It exists so a caller does not have to know the table joins — not so it can stop
knowing why an answer is missing.

### QUESTION

Can a caller hand over one hadith identifier and receive its recorded sanad,
with every provenance layer intact and the reason for any missing layer named?

### INPUT CONTRACT

Two explicit entry points, both deterministic; no free-form text is accepted and
no intent is inferred.

- `context_for_local_hadith(connection, local_id)` — the canonical form, taking
  the local corpus `id`.
- `context_for_retrieval_result(connection, result)` — an adapter taking **one**
  retrieval result. It reads `hadith_id` (what `retrieve.py` exposes) or
  `hadith_number` (the same value in chunk metadata), directly or under
  `metadata`. Any other shape raises `MissingRetrievalIdentifierError` rather
  than guessing.

The adapter enriches the one result it is given. It does not re-run retrieval,
alter ranking, choose between results, or decide whether the lookup was
worthwhile — verified by a test that passes two results through and checks both
survive in order, including the unlinked one.

### OUTPUT CONTRACT

One structure carrying `status`, `local_hadith`, `linkage`, `mis_hadith`,
`isnads` (each with `sanad_no` and ordered `narrators`), `isnad_count`,
`declared_sanad_count`, `requested_local_id`, `detail`, and `basis`.

Narrator records are exactly the ones `sanad_graph` already returns — MIS
narrator id, both Arabic name forms, generation and chain position — rather than
restated under second names, so there is one representation of a narrator in the
codebase and not two.

Every result carries its `basis` verbatim: *as recorded in MIS for the record
joined by the accepted local↔MIS linkage; MIS narrator identities, not
adjudicated historical persons.* The linkage is never hidden: `link_status`,
`link_relation`, `linkage_version` and the artifact SHA-256 travel with the
answer, and a test asserts the reported SHA is the frozen `9c3a48e7…`.

### STATUS / ABSTENTION CONTRACT

Four outcomes, each named, none collapsed into `[]`, `None` or `NOT_FOUND`:

| status | meaning | what survives |
|---|---|---|
| `LINKED_WITH_RECORDED_ISNAD` | full traversal | everything |
| `LINKED_BUT_NO_RECORDED_ISNAD` | linked, MIS records no chain | local + linkage + MIS record |
| `VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK` | real hadith, no accepted link (the 444) | local record kept |
| `INVALID_LOCAL_HADITH_ID` | no such hadith | the requested id, for the caller's error message |

The surface returns these rather than raising, so a caller branching on `status`
does not also have to catch two exception types. `sanad_graph` still raises, so
the precise API underneath is unchanged. A test asserts all four are distinct.

### PROVENANCE AND PERFORMANCE

Verified on live retrieval output with no LLM call: the dense matn retriever's
top results for two golden questions each resolved through
`hadith_id → local hadith → ACCEPTED_LINK_V1 → MIS record → ordered chain`, with
rank and score passed through untouched.

Adapter latency: **0.816 ms** median over 200 runs, on top of a
`context_for_local_hadith` that is itself sub-millisecond. Nothing cached,
nothing optimised.

### IDENTITY UNCHANGED

`MIS_CHAIN_HASH` `496ccf1d…`, `FULL_GRAPH_HASH` `c8818da0…` and the frozen
linkage `9c3a48e7…` are all unchanged — this milestone touched no data, only
composition. Tests assert each.

Static checks keep the boundary honest: the module's imports are exactly
`{__future__, sys, pathlib, sanad_graph}`; its source mentions no model or
network library; and no function or class it defines has a routing, planning,
classification or agent name.

### DECISION

The deterministic foundation is complete. **ENTITY-RESOLUTION GATE REMAINS
CLOSED** — no Itqan profile, grading, candidate identity edge or
`HistoricalNarrator` is reachable from this surface, and a test asserts none of
those words appears in its output.

---

## 20. Pre-Agentic Integrity Audit Repair

An independent pre-handoff audit raised eight suspected inconsistencies. Each
was checked against repository truth before anything was edited. Six were
confirmed, one was reconciled as a units problem with both numbers correct, and
one claim turned out to be supported but undocumented.

**No measured result changed and no runtime behaviour changed.** Where a number
moves below, it is because a *documented claim* was wrong, not because an
experiment was re-run differently. All frozen identities were re-verified
afterwards and are unchanged.

### A — scope header contradicted the later sections

**Before:** the header declared that the knowledge graph, isnad tracing, agents
and MCP were "not built, and there are no numbers for them here", while §17–19
document a built sanad graph, a local↔MIS bridge and a context surface with
measured numbers. The single measurement date also read as dating the whole
document.

**After:** the header separates §1–9 (the retrieval and answer path, covered by
the dated snapshot below it) from §10–19 (each carrying its own measurement),
and states the true boundary: RAG path, sanad graph, local↔MIS bridge and
context surface built; historical narrator identity, Itqan grading integration
and any router/LangGraph/agent not built.

### B — 1,524 versus 1,569: units, not a contradiction

**Root cause:** the audit emits **grouping records**, not profile sets. One set
of profile IDs appears once per grouping key, so a set with both a canonical-name
key and an exact-representation key is counted twice.

**Measured:** 19,757 grouping records over 19,410 unique profile-ID sets. In the
distinct-person class, 1,569 records — 468 `NARROW_CANONICAL_NAME` plus 1,101
`NARROW_EXACT_REPRESENTATION` — collapse to 1,524 unique sets. The same holds
elsewhere: 570 duplicate-class records → 445 sets; 17,618 unresolved records →
17,450 sets.

**After:** both numbers are retained and labelled by unit, and §16's rule table
now reports triggered records and triggered unique sets side by side. Neither is
precision: no adjudicated historical-person labels exist.

### C — check_docs compared a set of numbers

**Root cause:** the checker extracted percentages and MRR values into a set and
asserted every README number appeared *somewhere* in EXPERIMENTS. A correct
number attached to the wrong metric passed; so did swapping two percentages
between metrics, or renaming a metric while leaving a valid number; denominators
were never checked at all.

**After:** a single `canonical-results` block inside EXPERIMENTS — not a second
file, so there is still one source of truth — records each README row as
`(table, row_id, label, metadata, metric=value@denominator)`. The checker now
validates 30 README cells against it by `(table, row, metric)`, confirms each
canonical value appears in the EXPERIMENTS **section it declares**, and requires
every rate to carry a denominator. Dataset-hash checking is unchanged. Tests
assert it fails on a swapped value, a renamed metric, a wrong denominator and a
misattributed section.

### D — the reranker-depth claim was wrong

**Before:** "`hit@10` = `hit@20` = `hit@50` = 89% — a deeper candidate list buys
nothing but latency", in both §6 and the README.

**Evidence:** no depth-sweep artifact existed and no code sweeps depth, so the
claim was verified directly, retrieval-side and free — frozen datasets, current
dense/BM25/RRF/reranker code, no LLM and no paid API.

Hybrid ceiling on golden (n=27): `hit@10` **23/27 = 85.19%**, `hit@20` = `hit@50`
**24/27 = 88.89%**. The three are *not* equal — depth 10 differs from 20 and 50
by exactly one question, which is the same one-question difference §7 already
records as noise.

Varying only the candidate depth under the production reranker:

| top_k_in | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| **10** (in use) | 15/27 | 20/27 | **22/27** | 0.665 |
| 20 | 15/27 | 20/27 | 21/27 | 0.671 |
| 50 | 15/27 | 20/27 | 20/27 | 0.658 |

`hit@1` is identical at all three depths and `hit@5` *falls* as the pool deepens.

**After:** the claim is corrected in both documents. Depth 10 is kept and
justified by measured top-5 precision and latency rather than by equal ceilings.
`DEFAULT_TOP_K_IN = 10` was already the configured value; no code changed.
Depth 10 reproduces the published `hybrid + mmarco` row exactly
(56%/74%/81%/85%, MRR 0.665), which cross-checks the measurement against §6.

### E — answer-quality denominators were ambiguous

**Root cause:** the table sat under a "30 questions" heading while its metrics
use three different denominators, read from `answer_eval.report()`:

| metric | `among` | denominator |
|---|---|---|
| invalid citation attempts | — | all 30 |
| cited the wrong hadith from context | — | all 30 |
| correct citation | `answerable` | **27** |
| false refusal | `gold_in_context` | 20 hybrid / 22 reranked |
| correct refusal | `refusal_test` | 3 |

So "81% correct citation" is 22/27, not 81% of 30.

**After:** the README states the denominators explicitly and the canonical block
carries `@denominator` on every rate, which the checker enforces.

**Verification boundary.** `answer_eval.py` prints and stores nothing, so no
per-question artifact exists. The denominators above are established from code;
the numerators implied by the published rounded percentages are not
independently re-derivable without calling the generator, which this repair does
not do. No answer-quality number was changed.

### F — answer_eval described the whole evaluation as free

**Before:** "all metrics here are computed programmatically — no LLM judge — so
they are free and repeatable."

**After:** metric *computation* is programmatic, deterministic and free; running
the evaluation calls the answer generator (Gemini via Vertex) for every question
in every configuration and consumes quota and cost. Behaviour unchanged.

### G — the unretrievable questions: supported, now documented

The README claimed three golden questions are unretrievable by any method at any
depth. Measured at depth 50, per retriever:

| retriever | misses | question indices |
|---|---:|---|
| Dense: matn only | 6/27 | 4, 5, 12, 13, 19, 24 |
| BM25: matn only | 4/27 | 4, 12, 13, 14 |
| Hybrid | 3/27 | 4, 12, 13 |

**Missed by every method at depth 50 — exactly three**, all with verified ground
truth:

| # | question | expected |
|---|---|---|
| 4 | هل يجوز صيام يوم الشك؟ | 9679 |
| 12 | ما شرط كمال الإيمان في التعامل مع الآخرين؟ | 7354, 7355 |
| 13 | ما حكم الغش في البيع؟ | 7466, 7467 |

The claim holds for every depth measured (≤50); "any depth" is unbounded and was
narrowed accordingly. Query expansion remains an **unvalidated hypothesis** and
is not implemented — the README no longer presents it as the next step, since
the next work is the agentic layer.

### H — refusal did not do what the README implied

**Before:** "roughly one question in five is answered from an incomplete context
— the system's refusal behaviour is what keeps that from becoming a fabricated
answer."

**Root cause:** it conflated two failure modes. Citation enforcement prevents a
citation to a hadith **outside** the supplied evidence (invalid citation
attempts: 0%). It does not prevent a confident answer citing the **wrong hadith
from within** the retrieved context, which is measured at 10% with reranking and
13% without.

**After:** the README states both modes separately and no longer implies refusal
makes a wrong in-context citation impossible.

### FROZEN IDENTITIES — RE-VERIFIED UNCHANGED

`golden.jsonl` `a7ec05f48ec0491a` · `synthetic_eval.jsonl` `4bec52d5a56a8fc8` ·
`muslim.json` `63a99e46155dc6e9` · Hadith↔MIS linkage
`9c3a48e7…a572c77` · `MIS_CHAIN_HASH` `496ccf1d…0bfbce` · `FULL_GRAPH_HASH`
`c8818da0…6e481c`.

No corpus, golden label, synthetic row, embedding, linkage, graph, tier or audit
artifact was touched.

---

## 21. إغلاق ثغرة التحقق من الاستشهاد وإعادة القياس

**تاريخ القياس:** 2026-11-12

### ما الذي تغيّر في `src/answer.py`؟

الفاحص القديم في `answer_with_details()` كان يحسب فقط `bool(cited_ids(raw) - context_ids)` باستخدام التعبير النمطي الضيق `حديث\s*رقم\s*[:\s]*(\d+)`. هذا ترك ثلاث ثغرات تمرّ دون إعادة توليد:

1. **إجابة بلا أي استشهاد (`MISSING_CITATION`):** عندما لا يكتب الموديل أي رقم حديث، تكون مجموعة `cited_ids(raw)` فارغة، فيكون الفرق مع `context_ids` فارغًا وتمرّ الإجابة بلا مصدر.
2. **إشارات حرة لرقم حديث خارج السياق (`OUT_OF_CONTEXT_CITATION`):** مثل `"حديث 999"` أو `"مسلم 999"` أو `"مسلم، رقم 999"` (بالأرقام العربية `0-9` أو الهندية `٠-٩`)، إذ لم يكن التعبير الضيق يلتقطها.
3. **رفض مختلط (`MIXED_REFUSAL`):** كتابة جملة الرفض مع نص إضافي أو علامات ترقيم زائدة أو أرقام، بدل الاكتفاء بجملة `REFUSAL` وحدها حرفيًا.

أُضيفت الدالة الصافية `validate_answer(answer, context_ids)` التي تُرجع إحدى الحالات الخمس (`VALID_ANSWER`, `VALID_REFUSAL`, `MISSING_CITATION`, `OUT_OF_CONTEXT_CITATION`, `MIXED_REFUSAL`)، وعند أي حالة غير صالحة يُعاد التوليد **مرة واحدة فقط** برسالة تصحيح مخصصة لنوع الخطأ (`CORRECTIONS[status]`)؛ فإن فشلت المحاولة الثانية يُرجع النظام `REFUSAL`.

**ثبات البرومبت وقابلية المقارنة:** لم يتغير `build_system_prompt()` إطلاقًا، لذا فإن المخرَج الخام الأول (`raw`) لكل سؤال لا يتأثر بتعديل الفاحص. كما أُبقي حساب `invalid_citation_attempt` مطابقًا للتعريف القديم (استشهاد بالصيغة الرسمية خارج السياق) ليبقى قابلًا للمقارنة المباشرة، وأُضيفت مقاييس خام منفصلة: `missing_citation_attempt` و`loose_out_of_context_attempt` و`mixed_refusal_attempt`.

### نتائج القياس (30 سؤالًا: 27 قابلة للإجابة + 3 رفض، `k=5`، `gemini-2.5-pro`)

أُجري التحقق المسبق `uv run python -m src.validate_golden` (7,459 حديثًا، 33 مدخلًا، 0 أخطاء)، ثم شُغّل `uv run python -m src.answer_eval` على إعدادَي `Hybrid: dense + BM25` و`Hybrid + mmarco-mMiniLMv2-L12-H384-v1` دون CRAG. في نفس التشغيلة طُبّق الفاحص القديم والفاحص الجديد على نفس المخرجات الخام (`raw`):

| المقياس | المقام | Hybrid (لقطة §9 السابقة) | Hybrid (هذه التشغيلة — فاحص قديم) | Hybrid (هذه التشغيلة — فاحص جديد) | **Hybrid + rerank** (لقطة §9 السابقة) | **Hybrid + rerank** (هذه التشغيلة — فاحص قديم) | **Hybrid + rerank** (هذه التشغيلة — فاحص جديد) |
|---|---|---|---|---|---|---|---|
| Correct citation (`correct_citation`) | 27 | 70% (19/27) | 63% (17/27) | 63% (17/27) | **81%** (22/27) | **81%** (22/27) | **81%** (22/27) |
| Invalid citation attempts (measured before filtering) | 30 | 0% (0/30) | 0% (0/30) | 0% (0/30) | **0%** (0/30) | **0%** (0/30) | **0%** (0/30) |
| Missing citation attempts (raw output) | 30 | غير مقيس | — | 0% (0/30) | غير مقيس | — | **0%** (0/30) |
| Loose out-of-context attempts (raw output) | 30 | غير مقيس | — | 0% (0/30) | غير مقيس | — | **0%** (0/30) |
| Mixed refusal attempts (raw output) | 30 | غير مقيس | — | 0% (0/30) | غير مقيس | — | **3%** (1/30) |
| Cited a non-gold hadith from the context (`wrong_citation`) | 30 | 13% (4/30) | 23% (7/30) | 23% (7/30) | **10%** (3/30) | **10%** (3/30) | **10%** (3/30) |
| False refusals (`gold_in_context`) | 20 / 22 | 0% (0/20) | 0% (0/20) | 0% (0/20) | **0%** (0/22) | **0%** (0/22) | **0%** (0/22) |
| Correct refusals (`refusal_test`) | 3 | 3/3 (100%) | 3/3 (100%) | 3/3 (100%) | **3/3** (100%) | **3/3** (100%) | **3/3** (100%) |
| Cited a source while refusing | 6 / 5 | 0% | 0% (0/6) | 0% (0/6) | **0%** | **0%** (0/5) | **0%** (0/5) |
| حالات الثغرة (مرّت قديمًا وفشلت جديدًا على `raw`) | 30 | — | — | **0/30** | — | — | **1/30** |
| نداءات Gemini المستهلكة | — | 30 | — | 30 | 30 | — | 31 |

### تفسير النتائج وحالات الثغرة

1. **مقارنة الفاحص القديم بالجديد على نفس المخرجات الخام (مقارنة مضبوطة 100%):**
   - في إعداد **`Hybrid: dense + BM25`**: لم يفشل أي مخرَج خام من الـ 30 في الفاحص القديم ولا في الفاحص الجديد (`0/30` حالات ثغرة، `0/30` إعادة توليد). بالتالي فإن الفاحص القديم والفاحص الجديد يعطيان **نفس الأرقام بالضبط** على هذه التشغيلة (`63%` استشهاد صحيح = 17/27، و`23%` استشهاد بحديث غير مرجعي من السياق = 7/30).
   - سبب الفرق في إعداد `Hybrid` وحده بين لقطة §9 السابقة (`70%` / `13%`) وهذه التشغيلة (`63%` / `23%`) هو **تباين عبر التشغيلات (run-to-run variance)** في خدمة `gemini-2.5-pro` عبر Vertex AI بين تاريخَي القياس على سؤالين إلى ثلاثة أسئلة، وليس بسبب تعديل الفاحص (لأن الفاحص لم يتدخل في أي سؤال من أسئلة `Hybrid` الثلاثين).
2. **الحالة التي أمسكها الفاحص الجديد في `Hybrid + mmarco-mMiniLMv2-L12-H384-v1` (`1/30`):**
   - **السؤال `#28`:** `ما هو فضل قراءة سورة الكهف يوم الجمعة؟` (سؤال رفض).
   - **المخرَج الخام (`raw`):** `"المصادر المتاحة لا تجيب عن هذا السؤال."` (أضاف الموديل نقطة في نهاية جملة الرفض).
   - **التصنيف:** مرّ في الفاحص القديم لأن `cited_ids(raw)` فارغة، بينما صنّفه `validate_answer` كـ `MIXED_REFUSAL` لعدم مطابقته الحرفية لجملة `REFUSAL`. بعد إعادة توليد واحدة برسالة `CORRECTION_MIXED_REFUSAL`، أخرج الموديل النص المطابق حرفيًا: `"المصادر المتاحة لا تجيب عن هذا السؤال"`.
   - **الأثر على المقاييس النهائية في `Hybrid + rerank`:** بقيت كل المقاييس النهائية مطابقة للقطة §9 (`81%` استشهاد صحيح = 22/27، `10%` استشهاد بحديث غير مرجعي من السياق = 3/30، `0%` محاولات استشهاد باطل، `0%` محاولات إجابة بلا استشهاد، `0%` رفض كاذب = 0/22، `3/3` رفض صحيح).

---

## 22. التجربة E0 — توسيع المرجع بالمتون المتطابقة بعد التطبيع (Measurement Fix)

**تاريخ القياس:** 2026-11-13

### الفرضية والقاعدة الحتمية

يروي صحيح مسلم أحيانًا المتن الواحد بأسانيد متعددة وأرقام حديث مختلفة. إذا طابق متن حديثٍ آخر في الفهرس (بعد نفس التطبيع المستخدم في الفهرس: `strip_diacritics(split_isnad_matn(text))` للفهرس الدلالي و`tokenize(split_isnad_matn(text))` لفهرس BM25) متنَ حديثٍ مرجعي مدرج في `hadith_ids` تطابقًا تامًا، وجب احتسابه ضمن المرجع (`src/experiment_e0_gold_expansion.py`).

### النتيجة على مجموعتَي التقييم (0 نداءات API)

فُحصت جميع الـ 7,110 وثيقة القابلة للفهرسة (وجميع الـ 7,570 جزءًا شاملًا الإحالات)، ووُلّدت نسختان مشتقتان دون لمس الملفات الأصلية:

| المقياس / الملف | النتيجة |
|---|---|
| مجموعات المتون المتطابقة (`> 1 hadith_id`) بتطبيع الفهرس الدلالي | **33** مجموعة (53 شاملًا الإحالات) |
| مجموعات المتون المتطابقة (`> 1 hadith_id`) بتطبيع BM25 | **36** مجموعة (56 شاملًا الإحالات) |
| أسئلة تغيّرت في `golden.jsonl` (27 سؤالًا) | **0 / 27** (`data/processed/golden_expanded.jsonl`، البصمة `a7ec05f48ec0491a`) |
| أسئلة تغيّرت في `synthetic_eval.jsonl` (224 سؤالًا) | **0 / 224** (`data/processed/synthetic_eval_expanded.jsonl`، البصمة `4bec52d5a56a8fc8`) |

**لماذا لم يتغير أي سؤال (`0` تغيير)؟**
1. في `synthetic_eval.jsonl`: سكربت التوليد `src/build_eval_set.py` (`candidate_hadiths`) استبعد أصلًا عند البناء كل حديث يتكرر توقيع أول 8 كلمات من متنه المطبَّع (`signatures[matn_signature(matn)] > 1`)، فلا يوجد لأي سؤال من الـ 224 شقيق بمتن مطبَّع مطابق في الفهرس.
2. في `golden.jsonl`: الأسئلة ذات المتون المكررة أُضيفت أشقاؤها يدويًا في مراجعة المرجع السابقة، وما بقي من أحاديث قريبة يختلف في ديباجة الرواية أول المتن («قال رسول الله ﷺ» مقابل «عن النبي ﷺ») أو في بعض الألفاظ، فلا ينطبق عليه شرط التطابق الحرفي بعد التطبيع.

### خط الأساس الكامل مع `recall@50` (قبل أي تجربة استرجاع جديدة)

بما أن `0` أسئلة تغيّرت، فإن أرقام خط الأساس للاسترجاع وجودة الإجابة (المحسوبة في §21 دون أي نداء API جديد) تبقى مطابقة تمامًا، ويُثبّت هنا `recall@50` (`hit@50`) و`setR@50` معيارًا للاختيار في التجارب E1–E4:

**`synthetic_eval.jsonl` (المصدر: `dev`، `n = 224` — كل سؤال له حديث مرجعي واحد فـ `hit@50 == setR@50 == recall@50`؛ المعاملات المعايَرة مثل أوزان RRF وعمق المرشحين تُختار على `dev`):**

| الإعداد (المصدر: `dev`, `n = 224`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | **MRR@10** |
|---|---|---|---|---|---|---|
| Dense: matn only (`multilingual-e5-base`) | 14.3% | 20.1% | 25.9% | 31.7% | **43.8%** (98/224) | **0.189** |
| BM25: matn only | 17.9% | 25.0% | 28.6% | 36.6% | **50.9%** (114/224) | **0.228** |
| **Hybrid: dense + BM25 (RRF, c=50)** | 17.9% | 30.4% | 36.6% | 44.2% | **58.0%** (130/224) | **0.256** |
| **Hybrid + mmarco (top 10)** | **27.2%** | **37.1%** | **40.6%** | **44.2%** | 44.2% (سقف الـ 10؛ 58.0% قبل القص) | **0.330** |

**`golden.jsonl` (المصدر: `golden`، `n = 27` — للتأكيد المستقل فقط دون ضبط معاملات):**

| الإعداد (المصدر: `golden`, `n = 27`) | hit@1 | hit@3 | hit@5 | hit@10 | **hit@50 (recall@50)** | setR@50 | **MRR@10** |
|---|---|---|---|---|---|---|---|
| Dense: matn only (`multilingual-e5-base`) | 40.7% | 55.6% | 59.3% | 63.0% | **77.8%** (21/27) | 69.3% | **0.493** |
| BM25: matn only | 33.3% | 59.3% | 63.0% | 66.7% | **85.2%** (23/27) | 75.1% | **0.464** |
| **Hybrid: dense + BM25 (RRF, c=50)** | 44.4% | 66.7% | 74.1% | 85.2% | **88.9%** (24/27) | 81.3% | **0.565** |
| **Hybrid + mmarco (top 10)** | **55.6%** | **74.1%** | **81.5%** | **85.2%** | 85.2% (سقف الـ 10؛ 88.9% قبل القص) | 75.6% | **0.665** |

---

## 23. التجربة E1 — مقارنة نماذج التضمين الكثيف والهجين (Dense & Dense+Sparse)

**تاريخ القياس:** 2026-11-13
**السكربت:** `src/experiment_e1_dense_models.py` و`src/embed_vertex_e1.py`

### الإعداد والنماذج المفحوصة

قورنت النماذج التالية على نفس الـ 7,110 وثيقة (صيغة `matn` منزوعة التشكيل، المتغير الوحيد المتغير هو نموذج التضمين):
1. **`intfloat/multilingual-e5-base`** (الحالي، `dim = 768`).
2. **`BAAI/bge-m3`** (`dim = 1024`): فُحص في ثلاث صور من نفس التمريرة الأمامية (`sparse_linear.pt` + `[CLS]`):
   - كثيف فقط (`bge-m3 dense`).
   - أوزان معجمية متعلَّمة فقط (`bge-m3 sparse lexical`).
   - كثيف + متناثر (`bge-m3 dense + sparse`) بطريقتين: الدمج الخطي الأصلي لـ BGE-M3 (`score = dense + 0.3 * sparse`) ودمج المراتب `RRF (c=50)`.
3. **`Qwen/Qwen3-Embedding-0.6B`** (`dim = 1024`، `last_token_pool` مع تعليمة الاستعلام القياسية من `config_sentence_transformers.json`).
4. **`gemini-embedding-001` عبر Vertex AI**: النموذج الحالي المتاح على Vertex AI (تمت تجربة `text-multilingual-embedding-002` أيضًا فأرجع `429 RESOURCE_EXHAUSTED` لتقييد حصة عائلة `textembedding-gecko` القديمة إلى الصفر، بينما يعمل `gemini-embedding-001` بكامل الحصة؛ استُهلكت 36 دفعة للوثائق + دفعتان للاستعلامات = **38 نداء `embed_content`**). وبفضل تدريب Matryoshka في `gemini-embedding-001`، قيست الأبعاد الثلاثة القياسية: `768`، `1536`، و`3072` (مع تطبيع L2 لكل بُعد).
5. **نماذج 4B / 8B:** تخطّاها البروتوكول لأن الجهاز لا يحتوي على GPU (`torch.cuda.is_available() == False`، المعالج `Intel Core i7-1065G7` رباعي النواة).

### النتائج على `synthetic_eval_expanded.jsonl` (المصدر: `dev`، `n = 224` — أوزان RRF مختارة على `dev`)

| الإعداد (المصدر: `dev`, `n = 224`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|
| `Dense: multilingual-e5-base (768)` *(خط الأساس)* | 14.3% | 20.1% | 25.9% | 31.7% | **43.8%** (98/224) | **0.189** | 0.195 |
| `BM25: matn only` | 17.9% | 25.0% | 28.6% | 36.6% | **50.9%** (114/224) | **0.228** | 0.235 |
| `Sparse: BAAI/bge-m3 lexical` | 23.2% | 30.8% | 33.9% | 41.1% | **58.0%** (130/224) | **0.282** | 0.290 |
| `Dense: Qwen3-Embedding-0.6B (1024)` | 21.9% | 37.9% | 43.8% | 50.4% | **67.9%** (152/224) | **0.310** | 0.318 |
| `Dense: BAAI/bge-m3 dense (1024)` | 21.4% | 37.1% | 45.1% | 51.3% | **72.3%** (162/224) | **0.308** | 0.318 |
| `BGE-M3: dense + sparse (linear 1:0.3)` | 24.1% | 39.7% | 44.6% | 55.4% | **75.9%** (170/224) | **0.338** | 0.348 |
| `BGE-M3: dense + sparse (RRF c=50)` | 25.4% | 39.3% | 41.1% | 50.0% | **76.3%** (171/224) | **0.332** | 0.345 |
| **`Dense: gemini-embedding-001 (768)`** | 42.9% | **63.4%** | **71.9%** | 80.8% | **92.9%** (208/224) | **0.555** | 0.561 |
| **`Dense: gemini-embedding-001 (1536)`** | **44.2%** | 62.5% | **71.9%** | **81.2%** | **94.2%** (211/224) | **0.560** | **0.566** |
| **`Dense: gemini-embedding-001 (3072)`** | 43.3% | 62.5% | **71.9%** | 80.8% | **93.8%** (210/224) | **0.556** | 0.563 |
| `Hybrid (1:1, c=50): e5-base + BM25` *(خط الأساس الهجين)* | 17.9% | 30.4% | 36.6% | 44.2% | **58.0%** (130/224) | **0.256** | 0.263 |
| `Hybrid (1:1, c=50): Qwen3-0.6B + BM25` | 22.3% | 34.4% | 40.6% | 50.9% | **70.5%** (158/224) | **0.306** | 0.316 |
| `Hybrid (1:1, c=50): bge-m3 dense + BM25` | 22.8% | 36.2% | 43.3% | 51.8% | **72.3%** (162/224) | **0.315** | 0.326 |
| `Hybrid (1:1, c=50): bge-m3 (d+s) + BM25` | 24.6% | 35.3% | 44.2% | 52.2% | **74.1%** (166/224) | **0.326** | 0.337 |
| `Hybrid (1:1, c=50): gemini-001 (768) + BM25` | 29.5% | 46.0% | 58.9% | 71.0% | **90.2%** (202/224) | **0.415** | 0.426 |
| `Hybrid (1:1, c=50): gemini-001 (1536) + BM25` | 28.6% | 46.9% | 57.6% | 71.4% | **90.2%** (202/224) | **0.412** | 0.422 |
| `Hybrid (1:1, c=50): gemini-001 (3072) + BM25` | 29.0% | 46.9% | 57.6% | 71.0% | **90.6%** (203/224) | **0.414** | 0.425 |
| `Hybrid (3:1, c=50): gemini-001 (768) + BM25` | 34.8% | 56.7% | 65.2% | 79.0% | **92.9%** (208/224) | **0.484** | 0.491 |
| `Hybrid (3:1, c=50): gemini-001 (1536) + BM25` | 35.3% | 55.4% | 65.6% | 78.6% | **94.2%** (211/224) | **0.483** | 0.492 |
| `Hybrid (3:1, c=50): gemini-001 (3072) + BM25` | 35.3% | 54.9% | 66.1% | 78.1% | **93.8%** (210/224) | **0.485** | 0.493 |

### النتائج على `golden_expanded.jsonl` (المصدر: `golden`، `n = 27` — للتأكيد المستقل فقط)

| الإعداد (المصدر: `golden`, `n = 27`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50 (hit@50)** | setR@50 | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|---|
| `Dense: multilingual-e5-base (768)` *(خط الأساس)* | 40.7% | 55.6% | 59.3% | 63.0% | **77.8%** (21/27) | 69.3% | **0.493** | 0.500 |
| `BM25: matn only` | 33.3% | 59.3% | 63.0% | 66.7% | **85.2%** (23/27) | 75.1% | **0.464** | 0.474 |
| `Sparse: BAAI/bge-m3 lexical` | 44.4% | 70.4% | 74.1% | 77.8% | **85.2%** (23/27) | 77.6% | **0.569** | 0.572 |
| `Dense: Qwen3-Embedding-0.6B (1024)` | 44.4% | 66.7% | 77.8% | 81.5% | **92.6%** (25/27) | 88.3% | **0.581** | 0.586 |
| `Dense: BAAI/bge-m3 dense (1024)` | 66.7% | 85.2% | 88.9% | 88.9% | **88.9%** (24/27) | 83.7% | **0.769** | 0.769 |
| `BGE-M3: dense + sparse (linear 1:0.3)` | 63.0% | **88.9%** | 88.9% | 88.9% | **88.9%** (24/27) | 84.3% | **0.753** | 0.753 |
| `BGE-M3: dense + sparse (RRF c=50)` | 63.0% | 81.5% | 88.9% | 88.9% | **88.9%** (24/27) | 85.0% | **0.725** | 0.725 |
| **`Dense: gemini-embedding-001 (768)`** | **70.4%** | 85.2% | **88.9%** | **92.6%** | **96.3%** (26/27) | **93.9%** | **0.793** | **0.794** |
| **`Dense: gemini-embedding-001 (1536)`** | **70.4%** | 85.2% | **88.9%** | **92.6%** | **92.6%** (25/27) | 90.2% | **0.790** | 0.790 |
| **`Dense: gemini-embedding-001 (3072)`** | **70.4%** | 85.2% | **88.9%** | **92.6%** | **92.6%** (25/27) | 90.2% | **0.790** | 0.790 |
| `Hybrid (1:1, c=50): e5-base + BM25` *(خط الأساس الهجين)* | 44.4% | 66.7% | 74.1% | 85.2% | **88.9%** (24/27) | 81.3% | **0.565** | 0.569 |
| `Hybrid (1:1, c=50): Qwen3-0.6B + BM25` | 48.1% | 63.0% | 81.5% | 85.2% | **88.9%** (24/27) | 84.3% | **0.602** | 0.604 |
| `Hybrid (1:1, c=50): bge-m3 dense + BM25` | 63.0% | 74.1% | 81.5% | 88.9% | **88.9%** (24/27) | 83.7% | **0.706** | 0.706 |
| `Hybrid (1:1, c=50): bge-m3 (d+s) + BM25` | 63.0% | 81.5% | 81.5% | 85.2% | **88.9%** (24/27) | 82.5% | **0.715** | 0.717 |
| `Hybrid (1:1, c=50): gemini-001 (768) + BM25` | 59.3% | 77.8% | 81.5% | 85.2% | **92.6%** (25/27) | 90.2% | **0.691** | 0.695 |
| `Hybrid (1:1, c=50): gemini-001 (1536) + BM25` | 59.3% | 77.8% | 81.5% | 85.2% | **92.6%** (25/27) | 90.2% | **0.691** | 0.695 |
| `Hybrid (1:1, c=50): gemini-001 (3072) + BM25` | 59.3% | 77.8% | 81.5% | 85.2% | **92.6%** (25/27) | 90.2% | **0.690** | 0.695 |
| `Hybrid (3:1, c=50): gemini-001 (768) + BM25` | 66.7% | 85.2% | 85.2% | 88.9% | **96.3%** (26/27) | **93.9%** | **0.758** | 0.762 |
| `Hybrid (3:1, c=50): gemini-001 (1536) + BM25` | 66.7% | 85.2% | 85.2% | 88.9% | **92.6%** (25/27) | 90.2% | **0.758** | 0.761 |
| `Hybrid (3:1, c=50): gemini-001 (3072) + BM25` | 66.7% | 85.2% | 85.2% | 88.9% | **92.6%** (25/27) | 90.2% | **0.758** | 0.761 |

### التحليل والقرار (E1)

1. **الترتيب حسب معيار الاختيار (`recall@50` و`MRR`):**
   - يتفوق **`gemini-embedding-001`** بفارق كبير جدًا على جميع النماذج الأخرى على المجموعتين:
     - مقارنةً بخط الأساس الكثيف (`multilingual-e5-base`): يرتفع `recall@50` على `synthetic_eval` من **43.8%** (98/224) إلى **94.2%** (211/224 عند 1536d) و**93.8%** (210/224 عند 3072d) و**92.9%** (208/224 عند 768d)، ويرتفع `MRR@10` من **0.189** إلى **0.560 / 0.556 / 0.555** (أكثر من 2.9×). وعلى `golden` يرتفع `recall@50` من **77.8%** (21/27) إلى **96.3%** (26/27 عند 768d؛ و92.6% = 25/27 عند 1536d/3072d) و`MRR@10` من **0.493** إلى **0.793**.
     - مقارنةً بـ `BAAI/bge-m3 (dense+sparse)` (`recall@50 = 76.3%` على dev و`88.9%` على golden) و`Qwen3-Embedding-0.6B` (`recall@50 = 67.9%` على dev و`92.6%` على golden): يتقدم `gemini-embedding-001` بنحو **+17 إلى +26 نقطة مئوية** في `recall@50` وأكثر من **+0.22** في `MRR@10` على مجموعة التطوير.
2. **أثر الدمج مع BM25 (`1:1` مقابل الكثيف المنفرد و`3:1`):**
   - كان `BM25` يرفع `multilingual-e5-base` لأن الكثيف القديم ضعيف (`43.8%` مقابل `50.9%` لـ BM25). أما مع `gemini-embedding-001` (`recall@50 = 93.8%–94.2%`، `MRR@10 = 0.556–0.560`)، فإن الدمج بوزن متساوٍ (`1:1`) مع BM25 (`50.9%`) يدفع وثائق BM25 اللفظية غير الدقيقة إلى أعلى القائمة فيخفض `recall@50` إلى `90.6%` و`MRR@10` إلى `0.414`.
   - الكثيف المنفرد `gemini-embedding-001` (وعند الحاجة للهجين: ترجيح الكثيف `3:1` أو `4:1`) يحسم المشكلة؛ وفي الصيغة القياسية الهجينة للخطوات التالية سنفحص في **E2** أثر إضافة حقل توسيع الوثائق (`doc_expansions`) بالـ RRF فوق أفضل مسترجع من E1.
3. **القرار:** اعتماد **`gemini-embedding-001`** فائزًا في التجربة E1 (مع الاحتفاظ بمتجهات `768` و`1536` و`3072` لاختبار دمج RRF في E2 وإعادة الترتيب في E3).

---

## 24. التجربة E2 — توسيع الوثائق بالأسئلة والكلمات المفتاحية المعاصرة (Document Expansion)

**تاريخ القياس:** 2026-11-13
**السكربت:** `src/experiment_e2_doc_expansion.py`
**ملف التوسيع الناتج:** `data/processed/doc_expansions.jsonl` (البصمة `80dfdc2b52ad1380`، `7,110` سجلًا مطابقًا لترتيب الفهرس).

### النموذج والمطالبة والتكلفة (مختلفان عن `build_eval_set.py`)

التزمًا ببروتوكول عدم مشاركة نموذج أو مطالبة `src/build_eval_set.py` (الذي استخدم `gemini-2.5-pro` ومطالبة توليد سؤال وحيد مع حظر كلمات المتن):
- **النموذج:** `gemini-2.5-flash` عبر Vertex AI (`temperature = 0`، `thinking_budget = 0`، `response_mime_type = "application/json"`).
- **المطالبة (`DOC_EXPANSION_PROMPT`):**
  ```text
  أنت مفهرس موضوعي وفقهي لأحاديث صحيح مسلم.
  لكل نص مرقّم أدناه (يتضمن عنوان الباب ومتن الحديث)، اكتب من 3 إلى 5 عبارات بحثية وأسئلة قصيرة وكلمات مفتاحية فقهية وموضوعية باللغة العربية الفصحى المعاصرة (MSA) تصف موضوع الحديث وحكمه ومعناه ومرادفاته المعاصرة للألفاظ التراثية.
  شروط الفهرسة:
  1. استخدم المصطلحات الفصحى المعاصرة التي يبحث بها القارئ اليوم إلى جانب المفهوم الشرعي الدقيق.
  2. اجعل كل عبارة موجزة ومكتفية بذاتها (سؤال قصير أو عنوان موضوعي أو مصطلح فقهي).
  3. لا تذكر رقم الحديث ولا أسماء الرواة في السند.
  ```
- **النداءات والتكلفة:**
  - نداءات `gemini-2.5-flash`: **1,328 نداءً** (دفعات من 25 وثيقة مع تجزئة تلقائية عند الحاجة).
  - عدد التوكنات: `832,704` توكن إدخال + `548,950` توكن إخراج = **`1,381,654` توكن**.
  - التكلفة الفعلية المقدرة (بسعر Vertex AI لـ `gemini-2.5-flash`: `$0.30 / 1M` إدخال و`$2.50 / 1M` إخراج): **`$1.6222`** (نحو `$1.62`).
  - بالإضافة إلى **36 نداء `embed_content`** (`gemini-embedding-001`) لتضمين حقل التوسيع كفهرس كثيف مستقل (`vectors_expansion_gemini001_3072.npy`).

### النتائج على `synthetic_eval_expanded.jsonl` (المصدر: `dev`، `n = 224` — أوزان RRF مختارة على `dev`)

فُهرس حقل التوسيع (`expansion_text`) كحقل مستقل في كلٍّ من BM25 (`BM25_exp`) والتضمين الكثيف (`Dense_exp`)، ودُمج بالـ RRF (`c=50`) مع `Dense_matn` و`BM25_matn`:

| الإعداد (المصدر: `dev`, `n = 224`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|
| `BM25: matn only (baseline)` | 17.9% | 25.0% | 28.6% | 36.6% | **50.9%** (114/224) | **0.228** | 0.235 |
| `BM25: doc_expansion field only` | 16.5% | 25.9% | 29.5% | 34.4% | **50.4%** (113/224) | **0.223** | 0.231 |
| `BM25: matn + doc_expansion (RRF 1:1)` | 17.9% | 29.0% | 35.3% | 45.5% | **67.0%** (150/224) | **0.252** | 0.263 |
| `Dense: doc_expansion gemini-001 (1536) only` | 30.8% | 46.9% | 54.0% | 65.2% | **81.2%** (182/224) | **0.408** | 0.417 |
| `Dense: doc_expansion gemini-001 (3072) only` | 30.4% | 46.9% | 54.9% | 65.2% | **81.7%** (183/224) | **0.407** | 0.416 |
| `Legacy Hybrid: e5-base + BM25_matn (1:1)` | 17.9% | 30.4% | 36.6% | 44.2% | **58.0%** (130/224) | **0.256** | 0.263 |
| `Legacy Hybrid + BM25_exp (1:1:1)` | 19.6% | 30.4% | 39.3% | 50.9% | **71.4%** (160/224) | **0.275** | 0.285 |
| `E1: Dense gemini-001 (1536)` *(فائز E1)* | **44.2%** | 62.5% | **71.9%** | 81.2% | **94.2%** (211/224) | **0.560** | **0.566** |
| `E1: Dense gemini-001 (3072)` *(فائز E1)* | 43.3% | 62.5% | **71.9%** | 80.8% | **93.8%** (210/224) | **0.556** | 0.563 |
| `E2 (1536): Dense_matn + BM25_exp (3:1)` | 29.5% | 52.2% | 61.6% | 81.2% | **94.2%** (211/224) | **0.440** | 0.446 |
| `E2 (1536): Dense_matn + Dense_exp (1:1)` | 35.7% | 57.6% | 63.8% | 75.4% | **95.5%** (214/224) | **0.478** | 0.489 |
| `E2 (3072): Dense_matn + Dense_exp (1:1)` | 36.6% | 58.0% | 64.3% | 75.4% | **95.1%** (213/224) | **0.484** | 0.495 |
| `E2 (1536): Dense_matn + BM25_matn + BM25_exp (3:1:1)` | 32.1% | 54.5% | 65.6% | 77.7% | **94.6%** (212/224) | **0.461** | 0.471 |
| **`E2 (1536): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`** | 31.2% | 51.8% | 61.2% | 79.5% | **96.0%** (215/224) | **0.447** | 0.456 |
| **`E2 (1536): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)`** | 33.9% | 54.5% | 63.4% | 79.9% | **95.5%** (214/224) | **0.471** | 0.480 |
| **`E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`** | 30.4% | 50.9% | 61.2% | 79.9% | **96.4%** (216/224) | **0.442** | 0.450 |
| **`E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)`** | 33.0% | 54.9% | 62.9% | 80.4% | **95.1%** (213/224) | **0.467** | 0.475 |
| `E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (8:2:1:1)` | 36.6% | 56.7% | 67.4% | **81.7%** | **93.8%** (210/224) | **0.511** | 0.519 |

### النتائج على `golden_expanded.jsonl` (المصدر: `golden`، `n = 27` — للتأكيد المستقل فقط)

| الإعداد (المصدر: `golden`, `n = 27`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50 (hit@50)** | setR@50 | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|---|
| `BM25: matn only (baseline)` | 33.3% | 59.3% | 63.0% | 66.7% | **85.2%** (23/27) | 75.1% | **0.464** | 0.474 |
| `BM25: doc_expansion field only` | 33.3% | 66.7% | 77.8% | 81.5% | **92.6%** (25/27) | 81.9% | **0.507** | 0.511 |
| `BM25: matn + doc_expansion (RRF 1:1)` | 40.7% | 59.3% | 74.1% | 85.2% | **96.3%** (26/27) | 87.7% | **0.548** | 0.557 |
| `Dense: doc_expansion gemini-001 (1536) only` | 51.9% | 88.9% | **92.6%** | **96.3%** | **100.0%** (27/27) | 95.1% | **0.686** | 0.689 |
| `Legacy Hybrid: e5-base + BM25_matn (1:1)` | 44.4% | 66.7% | 74.1% | 85.2% | **88.9%** (24/27) | 81.3% | **0.565** | 0.569 |
| `Legacy Hybrid + BM25_exp (1:1:1)` | 37.0% | 77.8% | 85.2% | 92.6% | **100.0%** (27/27) | 93.2% | **0.572** | 0.574 |
| `E1: Dense gemini-001 (768)` | 70.4% | 85.2% | 88.9% | 92.6% | **96.3%** (26/27) | 93.9% | **0.793** | 0.794 |
| `E1: Dense gemini-001 (1536)` | 70.4% | 85.2% | 88.9% | 92.6% | **92.6%** (25/27) | 90.2% | **0.790** | 0.790 |
| `E1: Dense gemini-001 (3072)` | 70.4% | 85.2% | 88.9% | 92.6% | **92.6%** (25/27) | 90.2% | **0.790** | 0.790 |
| **`E2 (1536): Dense_matn + Dense_exp (1:1)`** | 70.4% | **88.9%** | 88.9% | 92.6% | **100.0%** (27/27) | **98.1%** | **0.795** | **0.799** |
| **`E2 (3072): Dense_matn + Dense_exp (1:1)`** | 70.4% | **88.9%** | 88.9% | 92.6% | **100.0%** (27/27) | **98.1%** | **0.795** | **0.800** |
| **`E2 (1536): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`** | 70.4% | **88.9%** | 88.9% | 92.6% | **100.0%** (27/27) | **98.1%** | **0.794** | 0.796 |
| **`E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`** | 70.4% | **88.9%** | 88.9% | 88.9% | **100.0%** (27/27) | **98.1%** | **0.790** | 0.796 |
| **`E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)`** | 70.4% | **88.9%** | 88.9% | 92.6% | **100.0%** (27/27) | **98.1%** | **0.794** | 0.796 |
| `E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (4:1.5:0.5:0.5)` | **74.1%** | **88.9%** | 88.9% | 92.6% | **92.6%** (25/27) | 90.2% | **0.822** | **0.822** |

### التحليل والقرار (E2)

1. **الأثر المستقل لحقل التوسيع (`doc_expansion`):**
   - يرفع حقل التوسيع وحده `recall@50` في BM25 من **50.9%** إلى **67.0%** (+16.1 نقطة مئوية) على `synthetic_eval`، ومن **85.2%** إلى **96.3%** على `golden`.
   - مع المسترجع الهجين القديم (`e5-base + BM25`)، يقفز `recall@50` عند إضافة `BM25_exp` من **58.0%** إلى **71.4%** على `synthetic_eval` ومن **88.9%** إلى **100.0%** (27/27) على `golden`.
2. **الأثر عند الدمج بالـ RRF فوق فائز E1 (`gemini-embedding-001`):**
   - يرفع دمج رباعي الحقول **`E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`** (وكذلك نظيره عند `1536d` وثنائي الحقول `Dense_matn + Dense_exp (1:1)`) سقف الاستدعاء `recall@50` على `synthetic_eval` من **93.8%–94.2%** (210–211/224) إلى **96.4%** (**216/224**)، ويرفع `recall@50` على `golden` من **92.6%** (25/27) إلى **100.0%** (**27/27**، مع `setR@50 = 98.1%` و`MRR@10 = 0.794–0.795`).
   - المقابلة الهندسية في RRF: خفض وزن `Dense_matn` النسبي إلى `2:1:1:1` يسمح لوثائق `Dense_exp` و`BM25_exp` في المراكز `1..10` بدخول قائمة الـ 50 مرشحًا (لأن $\frac{1+1}{61} > \frac{2}{110}$)، فيرتفع `recall@50` إلى `96.4%` و`100%`، لكنه يخفض `MRR@10` قبل إعادة الترتيب على `synthetic_eval` من `0.556` إلى `0.442–0.484`؛ وهو ما تعالجه مرحلة **E3 (إعادة الترتيب بالـ Cross-Encoder على عمق 30 و50)** التي تعيد ترتيب قائمة المرشحين الموسَّعة.
3. **القرار:** الاحتفاظ بتوسيع الوثائق **E2** (`Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)` لرفع `recall@50` إلى **96.4%** على dev و**100.0%** على golden، مع مقارنة كلٍّ من مرشحي E2 الهجين ومرشحي E1 الكثيف تحت معيدات الترتيب في **E3**).

---

## 25. التجربة E3 — مقارنة معيدات الترتيب (Cross-Encoder Rerankers) وعمق المرشحين (10 / 30 / 50)

**تاريخ القياس:** 2026-11-14
**السكربت:** `src/experiment_e3_rerankers.py`
**النتائج المحفوظة:** `data/processed/e3_results.json` وملفات النقاط `data/processed/e3_scores_{mmarco,bge,qwen3}.pkl` (`12,550` زوج «سؤال، متن» لكل معيد ترتيب عبر `251` سؤالًا × `50` مرشحًا).

### الإعداد والنماذج المفحوصة

قُورنت ثلاثة معيدات ترتيب (Cross-Encoders) عند أعماق إدخال `top_k_in ∈ {10, 30, 50}` فوق مرشحي مسترجع **E2** (`Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`، حيث الأوزان `2:1:1:1` وعمق المرشحين مختارة على مجموعة التطوير `dev`):
1. `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (`mmarco`، النموذج الافتراضي السابق عند `top 10`).
2. `BAAI/bge-reranker-v2-m3` (`bge`، متعدد اللغات مبني على `XLM-RoBERTa-large`، `568M` معامل).
3. `Qwen/Qwen3-Reranker-0.6B` (`qwen3`، بصيغته الرسمية `AutoModelForCausalLM` وحساب فرق اللوغاريتم `logits["yes"] - logits["no"]` مع تخزين مؤقت لبادئة السؤال عبر `past_key_values.crop`).

### النتائج على مجموعة التطوير `synthetic_eval_expanded.jsonl` (المصدر: `dev`، `n = 224`)

*(جميع الأرقام في الجدول أدناه مقيسة على مجموعة التطوير `dev: synthetic_eval_expanded.jsonl`، `n = 224`؛ استُخدمت هذه المجموعة وحدها للمفاضلة بين معيدات الترتيب واختيار العمق `top_k_in`):*

| الإعداد (المصدر: `dev`, `n = 224`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | **MRR@10** | MRR@50 | زمن CPU / سؤال (ث) | اقتطاع `> 512` |
|---|---|---|---|---|---|---|---|---|---|
| `Legacy Default: e5-base + BM25 + mmarco (top 10)` *(خط الأساس القديم)* | 27.2% (61/224) | 37.1% | 40.6% (91/224) | 44.2% (99/224) | 58.0% (130/224) | **0.330** | 0.335 | 1.52 | 0 / 12,550 |
| `E2 Base (2:1:1:1, no rerank)` | 30.4% (68/224) | 50.9% | 61.2% (137/224) | 79.9% (179/224) | **96.4%** (216/224) | **0.442** | 0.450 | — | — |
| `E1 Dense gemini-001 (3072, no rerank)` | **43.3%** (97/224) | **62.5%** | **71.9%** (161/224) | **80.8%** (181/224) | 93.8% (210/224) | **0.556** | **0.563** | — | — |
| `E2 + mmarco-mMiniLMv2 (top 10)` | 33.5% (75/224) | 54.9% | 65.6% (147/224) | 79.9% (179/224) | **96.4%** (216/224) | **0.474** | 0.482 | **1.52** | 0 / 12,550 |
| `E2 + mmarco-mMiniLMv2 (top 30)` | 30.8% (69/224) | 47.8% | 58.0% (130/224) | 73.2% (164/224) | **96.4%** (216/224) | **0.429** | 0.440 | 4.24 | 0 / 12,550 |
| `E2 + mmarco-mMiniLMv2 (top 50)` | 30.4% (68/224) | 46.9% | 54.5% (122/224) | 67.9% (152/224) | **96.4%** (216/224) | **0.412** | 0.426 | 4.71 | 0 / 12,550 |
| `E2 + bge-reranker-v2-m3 (top 10)` | 31.2% (70/224) | 55.8% | 65.2% (146/224) | 79.9% (179/224) | **96.4%** (216/224) | **0.467** | 0.475 | 6.69–6.95 | 0 / 12,550 |
| `E2 + bge-reranker-v2-m3 (top 30)` | 30.4% (68/224) | 57.1% | 66.5% (149/224) | 75.4% (169/224) | **96.4%** (216/224) | **0.453** | 0.464 | 21.66–22.18 | 0 / 12,550 |
| `E2 + bge-reranker-v2-m3 (top 50)` | 30.8% (69/224) | 54.0% | 66.1% (148/224) | 73.2% (164/224) | **96.4%** (216/224) | **0.447** | 0.459 | 30.89–47.89 | 0 / 12,550 |
| **`E2 + Qwen3-Reranker-0.6B (top 10)`** | **38.8%** (87/224) | **57.1%** | **69.6%** (156/224) | **79.9%** (179/224) | **96.4%** (216/224) | **0.510** | **0.519** | 10.67–19.65 | 37 / 12,550 |
| `E2 + Qwen3-Reranker-0.6B (top 30)` | 38.4% (86/224) | 54.9% | 62.9% (141/224) | 74.1% (166/224) | **96.4%** (216/224) | **0.491** | 0.503 | 31.11–44.70 | 37 / 12,550 |
| `E2 + Qwen3-Reranker-0.6B (top 50)` | 38.0% (85/224) | 54.0% | 62.9% (141/224) | 71.4% (160/224) | **96.4%** (216/224) | **0.484** | 0.495 | 51.07–68.74 | 37 / 12,550 |

### النتائج على المجموعة اليدوية `golden_expanded.jsonl` (المصدر: `golden`، `n = 27`)

*(جميع الأرقام في الجدول أدناه مقيسة على المجموعة اليدوية `golden: golden_expanded.jsonl`، `n = 27` للتأكيد المستقل فقط، دون استخدامها في ضبط العمق أو الأوزان):*

| الإعداد (المصدر: `golden`, `n = 27`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | setR@50 | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|---|
| `E2 Base (2:1:1:1, no rerank)` | **70.4%** (19/27) | **88.9%** | **88.9%** (24/27) | 88.9% (24/27) | **100.0%** (27/27) | **98.1%** | **0.790** | **0.796** |
| `E1 Dense gemini-001 (3072, no rerank)` | **70.4%** (19/27) | 85.2% | **88.9%** (24/27) | **92.6%** (25/27) | 92.6% (25/27) | 90.2% | **0.790** | 0.790 |
| `E2 + mmarco-mMiniLMv2 (top 10)` | 59.3% (16/27) | 74.1% | 85.2% (23/27) | 88.9% (24/27) | **100.0%** (27/27) | **98.1%** | **0.691** | 0.696 |
| `E2 + mmarco-mMiniLMv2 (top 30)` | 55.6% (15/27) | 70.4% | 77.8% (21/27) | 88.9% (24/27) | **100.0%** (27/27) | **98.1%** | **0.661** | 0.667 |
| `E2 + mmarco-mMiniLMv2 (top 50)` | 55.6% (15/27) | 70.4% | 74.1% (20/27) | 85.2% (23/27) | **100.0%** (27/27) | **98.1%** | **0.652** | 0.660 |
| `E2 + bge-reranker-v2-m3 (top 10)` | **70.4%** (19/27) | 77.8% | 85.2% (23/27) | 88.9% (24/27) | **100.0%** (27/27) | **98.1%** | **0.764** | 0.769 |
| `E2 + bge-reranker-v2-m3 (top 30)` | 63.0% (17/27) | 81.5% | 85.2% (23/27) | **92.6%** (25/27) | **100.0%** (27/27) | **98.1%** | **0.741** | 0.744 |
| `E2 + bge-reranker-v2-m3 (top 50)` | 63.0% (17/27) | 81.5% | 85.2% (23/27) | 88.9% (24/27) | **100.0%** (27/27) | **98.1%** | **0.738** | 0.745 |
| `E2 + Qwen3-Reranker-0.6B (top 10)` | **70.4%** (19/27) | 85.2% | 85.2% (23/27) | 88.9% (24/27) | **100.0%** (27/27) | **98.1%** | **0.778** | 0.783 |
| `E2 + Qwen3-Reranker-0.6B (top 30)` | **70.4%** (19/27) | 81.5% | **88.9%** (24/27) | **92.6%** (25/27) | **100.0%** (27/27) | **98.1%** | **0.777** | 0.779 |
| `E2 + Qwen3-Reranker-0.6B (top 50)` | **70.4%** (19/27) | 81.5% | **88.9%** (24/27) | **92.6%** (25/27) | **100.0%** (27/27) | **98.1%** | **0.772** | 0.774 |

### اختبارات McNemar المزدوجة على `dev` (`n = 224`)

حُسبت قيمة `p` الدقيقة ثنائية الطرف (Exact two-sided binomial McNemar) على `dev` (`n = 224`) أمام كلٍّ من:
- **(أ) الإعداد الافتراضي القديم للنظام (`Legacy Default: Hybrid e5-base + BM25 + mmarco top 10`):**
- **(ب) معيد الترتيب الافتراضي عند العمق الافتراضي فوق E2 (`E2 + mmarco-mMiniLMv2 top 10`):**
- **(ج) مسترجع E2 الأساسي دون إعادة ترتيب (`E2 Base 2:1:1:1, no rerank`):**

| المقارنة على `dev` (`n = 224`) | `hit@1` (`A_only vs B_only`, `p`) | `hit@5` (`A_only vs B_only`, `p`) | `hit@10` (`A_only vs B_only`, `p`) |
|---|---|---|---|
| **أمام خط الأساس الافتراضي القديم (`Legacy Default: e5+BM25+mmarco@10`):** | | | |
| `E2 + mmarco-mMiniLMv2 (top 10)` vs `Legacy Default` | `23 vs 9` (**p = 0.0201**) | `62 vs 6` (**p < 0.0001**) | `85 vs 5` (**p < 0.0001**) |
| `E2 + mmarco-mMiniLMv2 (top 30)` vs `Legacy Default` | `16 vs 8` (`p = 0.1516`) | `45 vs 6` (**p < 0.0001**) | `73 vs 8` (**p < 0.0001**) |
| `E2 + mmarco-mMiniLMv2 (top 50)` vs `Legacy Default` | `16 vs 9` (`p = 0.2295`) | `41 vs 10` (**p < 0.0001**) | `65 vs 12` (**p < 0.0001**) |
| `E2 + bge-reranker-v2-m3 (top 10)` vs `Legacy Default` | `25 vs 16` (`p = 0.2110`) | `64 vs 9` (**p < 0.0001**) | `85 vs 5` (**p < 0.0001**) |
| `E2 + bge-reranker-v2-m3 (top 30)` vs `Legacy Default` | `23 vs 16` (`p = 0.3368`) | `64 vs 6` (**p < 0.0001**) | `74 vs 4` (**p < 0.0001**) |
| `E2 + bge-reranker-v2-m3 (top 50)` vs `Legacy Default` | `24 vs 16` (`p = 0.2682`) | `63 vs 6` (**p < 0.0001**) | `70 vs 5` (**p < 0.0001**) |
| `E2 + Qwen3-Reranker-0.6B (top 10)` vs `Legacy Default` | `42 vs 16` (**p = 0.0009**) | `72 vs 7` (**p < 0.0001**) | `85 vs 5` (**p < 0.0001**) |
| `E2 + Qwen3-Reranker-0.6B (top 30)` vs `Legacy Default` | `39 vs 14` (**p = 0.0008**) | `58 vs 8` (**p < 0.0001**) | `73 vs 6` (**p < 0.0001**) |
| `E2 + Qwen3-Reranker-0.6B (top 50)` vs `Legacy Default` | `39 vs 15` (**p = 0.0015**) | `58 vs 8` (**p < 0.0001**) | `68 vs 7` (**p < 0.0001**) |
| **أمام `E2 + mmarco-mMiniLMv2 (top 10)` (الافتراضي فوق E2):** | | | |
| `E2 + mmarco-mMiniLMv2 (top 30)` vs `E2 + mmarco (top 10)` | `6 vs 12` (`p = 0.2379`) | `11 vs 28` (**p = 0.0095**, تراجع) | `18 vs 33` (**p = 0.0489**, تراجع) |
| `E2 + mmarco-mMiniLMv2 (top 50)` vs `E2 + mmarco (top 10)` | `7 vs 14` (`p = 0.1892`) | `12 vs 37` (**p = 0.0005**, تراجع) | `18 vs 45` (**p = 0.0009**, تراجع) |
| `E2 + bge-reranker-v2-m3 (top 10)` vs `E2 + mmarco (top 10)` | `16 vs 21` (`p = 0.5114`) | `13 vs 14` (`p = 1.0000`) | `0 vs 0` (`p = 1.0000`) |
| `E2 + bge-reranker-v2-m3 (top 30)` vs `E2 + mmarco (top 10)` | `18 vs 25` (`p = 0.3604`) | `27 vs 25` (`p = 0.8899`) | `19 vs 29` (`p = 0.1934`) |
| `E2 + bge-reranker-v2-m3 (top 50)` vs `E2 + mmarco (top 10)` | `19 vs 25` (`p = 0.4514`) | `28 vs 27` (`p = 1.0000`) | `21 vs 36` (`p = 0.0627`) |
| `E2 + Qwen3-Reranker-0.6B (top 10)` vs `E2 + mmarco (top 10)` | `30 vs 18` (`p = 0.1114`) | `19 vs 10` (`p = 0.1360`) | `0 vs 0` (`p = 1.0000`) |
| `E2 + Qwen3-Reranker-0.6B (top 30)` vs `E2 + mmarco (top 10)` | `32 vs 21` (`p = 0.1690`) | `20 vs 26` (`p = 0.4614`) | `15 vs 28` (`p = 0.0660`) |
| `E2 + Qwen3-Reranker-0.6B (top 50)` vs `E2 + mmarco (top 10)` | `32 vs 22` (`p = 0.2203`) | `21 vs 27` (`p = 0.4709`) | `15 vs 34` (**p = 0.0094**, تراجع) |
| **أمام `E2 Base (2:1:1:1, no rerank)` والمقارنات البينية:** | | | |
| `E2 + mmarco-mMiniLMv2 (top 10)` vs `E2 Base (no rerank)` | `38 vs 31` (`p = 0.4704`) | `28 vs 18` (`p = 0.1839`) | `0 vs 0` (`p = 1.0000`) |
| `E2 + bge-reranker-v2-m3 (top 10)` vs `E2 Base (no rerank)` | `28 vs 26` (`p = 0.8919`) | `28 vs 19` (`p = 0.2430`) | `0 vs 0` (`p = 1.0000`) |
| `E2 + Qwen3-Reranker-0.6B (top 10)` vs `E2 Base (no rerank)` | `40 vs 21` (**p = 0.0204**) | `27 vs 8` (**p = 0.0019**) | `0 vs 0` (`p = 1.0000`) |
| `E2 + Qwen3-Reranker-0.6B (top 10)` vs `E2 + bge (top 10)` | `31 vs 14` (**p = 0.0161**) | `20 vs 10` (`p = 0.0987`) | `0 vs 0` (`p = 1.0000`) |
| `E2 + Qwen3-Reranker-0.6B (top 30)` vs `E2 + Qwen3 (top 10)` | `6 vs 7` (`p = 1.0000`) | `10 vs 25` (**p = 0.0167**, تراجع) | `15 vs 28` (`p = 0.0660`) |
| `E1 Dense gemini-001 (3072, no rerank)` vs `E2 + mmarco (top 10)` | `45 vs 23` (**p = 0.0103**) | `35 vs 21` (`p = 0.0814`) | `15 vs 13` (`p = 0.8506`) |

### التحليل والقرار (E3)

1. **لماذا تراجعت الدقة عند توسيع عمق إعادة الترتيب إلى `top 30` و`top 50`؟**
   - على عكس المتوقع نظريًا، أدّى توسيع عمق المرشحين الداخلين لمعيدات الترتيب من `10` إلى `30` أو `50` إلى **تراجع دالّ إحصائيًا** في `hit@5` و`hit@10` على `dev` لجميع معيدات الترتيب الثلاثة (`hit@10` ينخفض من `79.9%` عند `top 10` إلى `73.2% / 75.4% / 74.1%` عند `top 30` وإلى `67.9% / 73.2% / 71.4%` عند `top 50`).
   - السبب البنيوي في متون الحديث: المرشحون في المراتب `11..50` من فهرس صحيح مسلم غالبًا ما يشتركون في ألفاظ فقهية أو تراكيب نبوية متقاربة مع السؤال دون أن يكونوا الحديث المرجعي؛ وبما أن نماذج Cross-Encoder متعددة اللغات (`mmarco`, `bge-reranker-v2-m3`, `Qwen3-Reranker-0.6B`) مدرَّبة أساسًا على استعلامات الويب المعاصرة (MS MARCO / MIRACL)، فإنها تمنح درجات مرتفعة للمطابقات السطحية في المراكز `11..50` وتطيح بالأحاديث الصحيحة التي رتّبها تضمين `gemini-embedding-001` الكثيف في المراكز `1..10`.
2. **المفاضلة بين معيدات الترتيب الثلاثة عند `top 10` مقابل عدم إعادة الترتيب:**
   - فوق `E2 Base (2:1:1:1)`، لا يحقق `mmarco (top 10)` ولا `bge-reranker-v2-m3 (top 10)` تحسنًا ذا دلالة إحصائية على `dev` (`p = 0.4704` و`p = 0.8919` على `hit@1`)، بينما يخفض كلاهما `MRR@10` على المجموعة اليدوية `golden` من `0.790` إلى `0.691` و`0.764`.
   - وحده `Qwen3-Reranker-0.6B (top 10)` يحقق تحسنًا دالًّا فوق `E2 Base (2:1:1:1)` على `dev` (`hit@1` من `30.4%` إلى `38.8%`، `p = 0.0204`؛ و`hit@5` من `61.2%` إلى `69.6%`، `p = 0.0019`)، لكنه يظل أدنى من **`E1 Dense gemini-001 (3072, no rerank)`** (`hit@1 = 43.3%`, `hit@5 = 71.9%`, `hit@10 = 80.8%`, `MRR@10 = 0.556`) ومن **`E2 (8:2:1:1, no rerank)`** (`hit@10 = 81.7%`, `MRR@10 = 0.511`) مع كلفة زمنية باهظة على المعالج (`10.67–19.65` ثانية/سؤال عند `top 10` و`51–69` ثانية/سؤال عند `top 50`).
3. **القرار:** عدم تفعيل Cross-Encoder عند أعماق `30/50` لأنه يضرّ بالاستدعاء والدقة معًا على المتون التراثية، والاحتفاظ بخيار معيد الترتيب الخفيف (`mmarco` عند `top 10`) للمسار التوافقي فقط، مع اختبار دمج أوزان RRF الموزونة لصالح التضمين الكثيف وHyDE في التجربتين **E4** و**E5**.

---

## 26. التجربة E4 — تضمين الاستعلام بالمتن الافتراضي (HyDE) وبناء مسودة المجموعة المعمّاة (`holdout_draft.jsonl`)

**تاريخ القياس:** 2026-11-13
**السكربتات:** `src/experiment_e4_hyde.py` · `src/build_holdout_draft.py` · `src/validate_holdout_draft.py`
**الملفات الناتجة:** `data/processed/hyde_queries.jsonl` (البصمة `bf31eab3b8e0f63c`)، `data/processed/e4_results.json`، ومسودة الفحص اليدوي `data/raw/holdout_draft.jsonl` (`120` سؤالًا، البصمة `f003a285cb71d732`).

### إعداد HyDE وتكلفته (`gemini-2.5-flash`)

- **المبدأ:** لكل سؤال من أسئلة التقييم الـ `251` (`224` في `dev` + `27` في `golden`)، يولّد النموذج متن حديث نبوي افتراضي موجز باللغة العربية التراثية الفصيحة (`pseudo_matn`) يحاكي معجم صحيح مسلم، ثم يُضمَّن المتن الافتراضي بـ `gemini-embedding-001` (`3072d`) بنمطَي `RETRIEVAL_DOCUMENT` (`HyDE_doc`) و`RETRIEVAL_QUERY` (`HyDE_q`).
- **النموذج والتكلفة:** `gemini-2.5-flash` (`temperature = 0`، `thinking_budget = 0`، `response_mime_type = "application/json"`): **150 نداءً**، `19,594` توكن إدخال + `6,285` توكن إخراج = `25,879` توكن، بتكلفة **`$0.0216`** (بالإضافة إلى نداءَي `embed_content`). *(ملاحظة: بسبب حدود معدّل الطلبات أثناء التشغيل المتوازي الأول، تراجعت `101 / 251` من الدفعات الجزئية إلى نص السؤال الأصلي كبديل آمن؛ وأُعيد تشغيل E4 بالكامل دون أي تراجع في القسم 28 أدناه).*

### نتائج E4 على مجموعة التطوير `synthetic_eval_expanded.jsonl` (المصدر: `dev`، `n = 224`)

*(جميع الأرقام في الجدول أدناه مقيسة على مجموعة التطوير `dev: synthetic_eval_expanded.jsonl`، `n = 224`؛ الأوزان ومعاملات المزج $\alpha \in \{0.5, 0.7, 0.8\}$ وأوزان RRF مختارة على `dev`):*

| الإعداد (المصدر: `dev`, `n = 224`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|
| `E1: Dense gemini-001 (3072, query only)` *(مرجع E1)* | **43.3%** | **62.5%** | 71.9% | 80.8% | 93.8% (210/224) | 0.556 | 0.563 |
| `E2 Best: Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)` *(مرجع E2)* | 30.4% | 50.9% | 61.2% | 79.9% | **96.4%** (216/224) | 0.442 | 0.450 |
| `E4: HyDE pseudo-matn only (RETRIEVAL_DOCUMENT -> Dense_m)` | 25.9% | 42.4% | 50.0% | 58.9% | 74.6% (167/224) | 0.360 | 0.367 |
| `E4: HyDE pseudo-matn only (RETRIEVAL_QUERY -> Dense_m)` | 32.6% | 56.2% | 64.7% | 72.8% | 87.9% (197/224) | 0.464 | 0.471 |
| `E4: BM25_matn (HyDE pseudo-matn only)` | 24.1% | 32.1% | 37.0% | 45.5% | 60.3% (135/224) | 0.298 | 0.305 |
| `E4: BM25_matn (query + HyDE pseudo-matn)` | 24.6% | 33.9% | 40.2% | 49.5% | 64.7% (145/224) | 0.313 | 0.321 |
| `E4: Dense_m (0.5*query + 0.5*HyDE_q)` | 38.8% | **65.2%** | 72.3% | 79.5% | 93.3% (209/224) | 0.537 | 0.544 |
| **`E4: Dense_m (0.7*query + 0.3*HyDE_q)`** | 42.4% | **65.2%** | 72.3% | **81.7%** | 93.3% (209/224) | **0.559** | **0.565** |
| **`E4: Dense_m (0.8*query + 0.2*HyDE_q)`** | 42.4% | 64.7% | **73.7%** | 81.2% | 93.8% (210/224) | 0.558 | **0.565** |
| `E4: Dense_m (0.7*query + 0.3*HyDE_doc)` | 42.9% | 62.1% | 69.6% | 79.5% | 92.4% (207/224) | 0.548 | 0.554 |
| `E4: E2 (2:1:1:1) + Dense_m(HyDE_q) (w=0.5)` | 33.9% | 54.9% | 65.2% | 81.2% | 96.0% (215/224) | 0.474 | 0.482 |
| **`E4: E2 (2:1:1:1) + Dense_m(HyDE_q) (w=1.0)`** | 34.8% | 55.8% | 67.4% | **81.7%** | 96.0% (215/224) | 0.483 | 0.491 |
| `E4: E2 (2:1:1:1) + Dense_m(HyDE_doc) (w=0.5)` | 33.9% | 53.6% | 65.2% | 79.5% | 95.1% (213/224) | 0.469 | 0.478 |
| `E4: E2 (2:1:1:1) + Dense_m(HyDE_q) + BM25_m(HyDE) (0.5:0.5)` | 29.9% | 57.6% | 68.8% | 80.4% | 95.1% (213/224) | 0.461 | 0.469 |
| `E4: E2 with blended query vector (0.7*q + 0.3*HyDE_q) (2:1:1:1)` | 30.8% | 54.9% | 64.3% | 79.9% | 95.5% (214/224) | 0.451 | 0.460 |
| `E4: E2 with blended Dense_m (0.8*q + 0.2*HyDE_q) (2:1:1:1)` | 29.5% | 52.2% | 62.5% | 79.5% | 96.0% (215/224) | 0.440 | 0.449 |

### نتائج E4 على المجموعة اليدوية `golden_expanded.jsonl` (المصدر: `golden`، `n = 27`)

*(جميع الأرقام في الجدول أدناه مقيسة على المجموعة اليدوية `golden: golden_expanded.jsonl`، `n = 27` للتأكيد المستقل فقط):*

| الإعداد (المصدر: `golden`, `n = 27`) | hit@1 | hit@3 | hit@5 | hit@10 | **recall@50** | setR@50 | **MRR@10** | MRR@50 |
|---|---|---|---|---|---|---|---|---|
| `E1: Dense gemini-001 (3072, query only)` *(مرجع E1)* | 70.4% | 85.2% | 88.9% | 92.6% | 92.6% (25/27) | 90.2% | 0.790 | 0.790 |
| `E2 Best: Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)` *(مرجع E2)* | 70.4% | 88.9% | 88.9% | 88.9% | **100.0%** (27/27) | **98.2%** | 0.790 | 0.796 |
| `E4: HyDE pseudo-matn only (RETRIEVAL_DOCUMENT -> Dense_m)` | 77.8% | 88.9% | 96.3% | **100.0%** | **100.0%** (27/27) | 95.4% | 0.850 | 0.850 |
| `E4: HyDE pseudo-matn only (RETRIEVAL_QUERY -> Dense_m)` | **85.2%** | 96.3% | **100.0%** | **100.0%** | **100.0%** (27/27) | 95.8% | 0.910 | 0.910 |
| `E4: BM25_matn (HyDE pseudo-matn only)` | 66.7% | 81.5% | 85.2% | 88.9% | 96.3% (26/27) | 91.5% | 0.748 | 0.752 |
| `E4: BM25_matn (query + HyDE pseudo-matn)` | 66.7% | 81.5% | 88.9% | 96.3% | **100.0%** (27/27) | 95.2% | 0.760 | 0.761 |
| **`E4: Dense_m (0.5*query + 0.5*HyDE_q)`** | **85.2%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** (27/27) | 97.6% | **0.926** | **0.926** |
| **`E4: Dense_m (0.7*query + 0.3*HyDE_q)`** | **85.2%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** (27/27) | 95.8% | **0.926** | **0.926** |
| `E4: Dense_m (0.8*query + 0.2*HyDE_q)` | 77.8% | 92.6% | 96.3% | **100.0%** | **100.0%** (27/27) | 95.8% | 0.863 | 0.863 |
| `E4: Dense_m (0.7*query + 0.3*HyDE_doc)` | 70.4% | 96.3% | **100.0%** | **100.0%** | **100.0%** (27/27) | 96.3% | 0.835 | 0.835 |
| `E4: E2 (2:1:1:1) + Dense_m(HyDE_q) (w=0.5)` | 70.4% | 88.9% | 88.9% | 92.6% | **100.0%** (27/27) | **98.2%** | 0.795 | 0.799 |
| **`E4: E2 (2:1:1:1) + Dense_m(HyDE_q) (w=1.0)`** | 74.1% | 88.9% | 88.9% | 96.3% | **100.0%** (27/27) | **98.2%** | 0.819 | 0.822 |
| `E4: E2 (2:1:1:1) + Dense_m(HyDE_doc) (w=0.5)` | 70.4% | 88.9% | 88.9% | 92.6% | **100.0%** (27/27) | **98.2%** | 0.795 | 0.798 |
| `E4: E2 (2:1:1:1) + Dense_m(HyDE_q) + BM25_m(HyDE) (0.5:0.5)` | 66.7% | 88.9% | 92.6% | 96.3% | **100.0%** (27/27) | **98.2%** | 0.785 | 0.788 |
| **`E4: E2 with blended query vector (0.7*q + 0.3*HyDE_q) (2:1:1:1)`** | 74.1% | 92.6% | 96.3% | **100.0%** | **100.0%** (27/27) | **98.2%** | **0.842** | **0.842** |
| `E4: E2 with blended Dense_m (0.8*q + 0.2*HyDE_q) (2:1:1:1)` | 74.1% | 92.6% | 96.3% | **100.0%** | **100.0%** (27/27) | **98.2%** | 0.839 | 0.839 |

### مسودة مجموعة الاختبار المعمّاة `data/raw/holdout_draft.jsonl` (غير مستخدمة في أي تجربة)

بُنيت مسودة `data/raw/holdout_draft.jsonl` (`src/build_holdout_draft.py`) وتحقّق منها برمجيًا `src/validate_holdout_draft.py` للمراجعة اليدوية مستقبلًا (**لم تُستخدم في أي تجربة أو اختيار معاملات**):
- **الحجم والتوزيع (120 سؤالًا فريدًا ومستقلًا تمامًا عن `golden.jsonl` و`synthetic_eval.jsonl`):**
  - `75` سؤالًا معاد الصياغة بالعربية الفصحى المعاصرة (`single_hadith`) لأحاديث مفردة لم ترد في `golden` أو `synthetic_eval`.
  - `30` سؤالًا لعناقيد الأحاديث المتشابهة (`sibling_hadiths`) التي تشترك في المتن النبوي.
  - `15` سؤال رفض خارج نطاق صحيح مسلم (`out_of_scope_refusal`)، متحقَّق برمجيًا من غياب ألفاظها المفتاحية (`probe_terms` / `probe_terms_together`) عن جميع أحاديث `muslim.json` الـ `7,459`.
- **مرشحو المرجع (`candidate_gold_ids`):** لكل سؤال من الـ `105` القابلة للإجابة قائمة مرشحين (`9–12` معرّف حديث، بمتوسط `11.9`) مستخرجة ببحث المتن (تطابق توقيع المتن المطبَّع + `gemini-embedding-001` + `BM25`) وموسومة بـ `verified: false` بانتظار المراجعة البشرية.

---

## 27. فحوص النزاهة وإعادة الإنتاج وعدم التسرب (Step 3 Integrity Audit)

**تاريخ الفحص:** 2026-11-14

### أ) إعادة بناء البيئة الافتراضية (`.venv`) من الصفر وفحص سلامة الحزم وإعادة الإنتاج

1. **فحص التعديلات العرضية في `.venv`:**
   - فُحصت جميع ملفات الحزم المثبتة (`29,038` ملفًا) مقابل بصمات `SHA-256` المسجَّلة في ملفات `*.dist-info/RECORD`.
   - تبيّن وجود `11` ملفًا مفرَّغًا (`0 bytes`) داخل `torch` و`triton` (`torch/_VF.pyi`, `torch/_C/__init__.pyi`, `torch/_C/_VariableFunctions.pyi`, `torch/include/ATen/core/TensorBody.h`, `torch/include/ATen/RedispatchFunctions.h`, `torch/include/ATen/RegistrationDeclarations.h`, `torch/include/ATen/VmapGeneratedPlumbing.h`, `triton/backends/nvidia/include/cuda.h`, `triton/backends/nvidia/include/cuda_runtime_api.h`, `triton/backends/amd/include/hip/hip_runtime_api.h`, `triton/backends/amd/include/hip/amd_detail/hip_prof_str.h`) بسبب امتلاء القرص في الجلسة السابقة.
2. **إعادة البناء والتحقق:**
   - حُذف مجلد `.venv` بالكامل وأُعيد بناؤه من الصفر عبر `uv sync`.
   - أُعيد فحص جميع الـ `29,038` ملفًا مقابل `RECORD`: **`0` ملفات مخالفة (`checked 29038, mismatched 0`)**.
   - اجتازت حزمة الاختبارات الكاملة `uv run pytest`: **`269 passed, 25 subtests passed`**.
   - أُعيد تشغيل تقييم خط الأساس (`uv run python -m src.evaluate golden ...` و`synthetic ...`) وتقييم خط أنابيب الاسترجاع الأفضل (`src/experiment_e2_doc_expansion.py` و`src/experiment_e3_rerankers.py`): **تطابقت جميع الأرقام تطابقًا حرفيًا (`diff = 0`)**.

### ب) فحص التسرب (Leakage Check) بين بناء `synthetic_eval.jsonl` وتوسيع الوثائق (E2)

**السكربت التحليلي والبيانات الخام:** `src/experiment_e5_ablation_and_leakage.py` · `data/processed/e5_ablation_and_leakage.json`

1. **مقارنة النماذج والمطالبات التي ولّدت `synthetic_eval.jsonl` مقابل التوسعات (`doc_expansions`):**
   - **توليد مجموعة التطوير `data/raw/synthetic_eval.jsonl` (`n = 224`):**
     - **الكود:** `src/build_eval_set.py` (التزام `ad221b3` بتاريخ `2026-08-09`).
     - **النموذج:** **`gemini-2.5-pro`** (`MODEL = "gemini-2.5-pro"`, `TEMPERATURE = 0`).
     - **المدخلات والمطالبة (`build_eval_set.PROMPT`):** يأخذ دفعات من 5 متون (`matn` فقط دون سند ودون عنوان باب) من الشظايا الأولى (`*_0`) التي يتراوح طول متنها بين `120` و`900` حرف ولها بادئة فريدة من 8 كلمات، ويطلب:
       ```text
       أنت باحث في الحديث النبوي. لكل متن مرقّم أدناه، اكتب سؤالًا واحدًا فقط باللغة العربية يبحث صاحبه عن المعنى المحدد في هذا المتن دون غيره.
       شروط صارمة:
       1. يجب أن يدور السؤال حول تفصيل خاص في المتن (حكم معيّن، واقعة محددة، صحابي مذكور في المتن، عدد، استثناء، أو علّة)، وليس موضوع الباب العام.
       2. لا تنسخ ألفاظ المتن المميزة في السؤال؛ صِغ السؤال بأسلوب سائل عادي يبحث عن المعلومة دون أن يحفظ نص الحديث.
       3. لا تذكر رقم الحديث ولا أسماء الرواة في السند.
       4. يجب أن يكون السؤال مفهومًا بذاته دون قراءة المتن.
       ```
     - **الفلترة اللاحقة في `build_eval_set.py`:** يستبعد أي سؤال يشترك مع المتن في أكثر من `60%` من الكلمات الدلالية (`MAX_TOKEN_OVERLAP = 0.60`) أو يقل طوله عن 4 كلمات دلالية.
   - **توليد توسعات الوثائق (`doc_expansions.jsonl` و`doc_expansions_g38flash.jsonl`، `7,110` شظية):**
     - **الكود والنماذج:** `src/experiment_e2_doc_expansion.py` (**`gemini-2.5-flash`**، `thinking_budget = 0`) و`src/experiment_step4_newer_llm.py` (**`gemini-3.8-flash`**، `thinking_level = "LOW"`).
     - **المدخلات والمطالبة (`DOC_EXPANSION_PROMPT`):** يأخذ `[chapter_arabic] matn[:450]` في دفعات من 25 شظية لجميع شظايا المدونة الـ `7,110`، ويطلب من 3 إلى 5 عبارات بحثية وأسئلة قصيرة وكلمات مفتاحية فقهية وموضوعية باللغة العربية الفصحى المعاصرة (MSA) تصف موضوع الحديث وحكمه ومعناه ومرادفاته المعاصرة للألفاظ التراثية.

2. **توزيع أقصى تشابه جيب التمام (Cosine Similarity) وجاكارد المقاطع الحرفية الرباعية (Character 4-gram Jaccard) لكل سؤال في `dev` (`n = 224`) مقابل الحديث المرجعي (GOLD) وأعلى حديث غير مرجعي (Best NON-gold):**
   - لكل سؤال من أسئلة `dev` الـ `224`، حُسب أقصى تشابه بين السؤال ونصوص التوسيع المنتمية إلى **حديثه المرجعي (GOLD hadith)** مقابل أقصى تشابه مع نصوص التوسيع المنتمية إلى **أفضل حديث غير مرجعي في المدونة (Best NON-gold hadith)**، وذلك على مستويين:
     1. **على مستوى العبارة المفردة (Item-level symmetric):** بين السؤال وكل عبارة توسيع مفردة من العبارات الـ `3–5` في `row["items"]` (مضمَّنة بتضمين متماثل `gemini-embedding-001` بنمط `RETRIEVAL_QUERY` و3072 بُعدًا، بالإضافة إلى تشابه `Character 4-gram Jaccard` بعد تطبيع العربية).
     2. **على مستوى الشظية المجمّعة (Chunk-level asymmetric):** بين السؤال والنص المجمّع `expansion_text = " ؛ ".join(items)` (`RETRIEVAL_QUERY` مقابل `RETRIEVAL_DOCUMENT`، و`Character 4-gram Jaccard`).

| نموذج التوسيع ومقياس التشابه (`dev`, `n = 224`) | الفئة المقارنة | `min` | `p10` | `p25` | `median` | `mean` (`std`) | `p75` | `p90` | `max` | `>= 0.90` | `>= 0.85` | `>= 0.80` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`gemini-3.8-flash` — Cosine (Item-level 3072d)** | **GOLD hadith** | 0.5169 | 0.6438 | 0.7048 | 0.7728 | 0.7659 (0.0899) | 0.8264 | 0.8715 | 0.9745 | **10 (4.5%)** | 37 (16.5%) | 81 (36.2%) |
| **`gemini-3.8-flash` — Cosine (Item-level 3072d)** | **Best NON-gold** | 0.6618 | 0.7419 | 0.7723 | 0.8150 | 0.8208 (0.0664) | 0.8619 | 0.9167 | 0.9916 | **33 (14.7%)** | 69 (30.8%) | 129 (57.6%) |
| `gemini-3.8-flash` — Cosine (Chunk-level Q vs D) | GOLD hadith | 0.5359 | 0.6465 | 0.6831 | 0.7193 | 0.7133 (0.0525) | 0.7496 | 0.7776 | 0.8215 | **0 (0.0%)** | 0 (0.0%) | 5 (2.2%) |
| `gemini-3.8-flash` — Cosine (Chunk-level Q vs D) | Best NON-gold | 0.6670 | 0.6973 | 0.7209 | 0.7433 | 0.7432 (0.0338) | 0.7651 | 0.7899 | 0.8271 | **0 (0.0%)** | 0 (0.0%) | 14 (6.2%) |
| **`gemini-3.8-flash` — Char 4-gram Jaccard (Item)** | **GOLD hadith** | 0.0000 | 0.0252 | 0.0562 | 0.1019 | 0.1245 (0.1044) | 0.1644 | 0.2309 | 0.6452 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **`gemini-3.8-flash` — Char 4-gram Jaccard (Item)** | **Best NON-gold** | 0.0980 | 0.1490 | 0.1814 | 0.2251 | 0.2539 (0.1114) | 0.2919 | 0.3928 | 0.8333 | 0 (0.0%) | 0 (0.0%) | 1 (0.4%) |
| `gemini-3.8-flash` — Char 4-gram Jaccard (Chunk) | GOLD hadith | 0.0000 | 0.0168 | 0.0361 | 0.0633 | 0.0677 (0.0434) | 0.0933 | 0.1250 | 0.2396 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| `gemini-3.8-flash` — Char 4-gram Jaccard (Chunk) | Best NON-gold | 0.0485 | 0.0805 | 0.0962 | 0.1209 | 0.1301 (0.0479) | 0.1538 | 0.1982 | 0.3295 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **`gemini-2.5-flash` — Cosine (Item-level 3072d)** | **GOLD hadith** | 0.5021 | 0.6465 | 0.7285 | 0.7942 | 0.7826 (0.1027) | 0.8534 | 0.9115 | 0.9801 | **28 (12.5%)** | 58 (25.9%) | 104 (46.4%) |
| **`gemini-2.5-flash` — Cosine (Item-level 3072d)** | **Best NON-gold** | 0.6811 | 0.7503 | 0.7871 | 0.8373 | 0.8366 (0.0682) | 0.8828 | 0.9343 | 0.9929 | **44 (19.6%)** | 93 (41.5%) | 147 (65.6%) |
| `gemini-2.5-flash` — Cosine (Chunk-level Q vs D) | GOLD hadith | 0.5423 | 0.6425 | 0.6915 | 0.7302 | 0.7238 (0.0594) | 0.7653 | 0.7959 | 0.8284 | **0 (0.0%)** | 0 (0.0%) | 18 (8.0%) |
| `gemini-2.5-flash` — Cosine (Chunk-level Q vs D) | Best NON-gold | 0.6524 | 0.7070 | 0.7274 | 0.7507 | 0.7522 (0.0354) | 0.7766 | 0.8015 | 0.8436 | **0 (0.0%)** | 0 (0.0%) | 24 (10.7%) |
| **`gemini-2.5-flash` — Char 4-gram Jaccard (Item)** | **GOLD hadith** | 0.0000 | 0.0188 | 0.0525 | 0.1226 | 0.1514 (0.1351) | 0.2076 | 0.2897 | 0.8864 | 0 (0.0%) | 1 (0.4%) | 1 (0.4%) |
| **`gemini-2.5-flash` — Char 4-gram Jaccard (Item)** | **Best NON-gold** | 0.1061 | 0.1674 | 0.2057 | 0.2620 | 0.2908 (0.1250) | 0.3423 | 0.4505 | 0.8333 | 0 (0.0%) | 0 (0.0%) | 1 (0.4%) |
| `gemini-2.5-flash` — Char 4-gram Jaccard (Chunk) | GOLD hadith | 0.0000 | 0.0124 | 0.0369 | 0.0714 | 0.0766 (0.0510) | 0.1048 | 0.1450 | 0.2830 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| `gemini-2.5-flash` — Char 4-gram Jaccard (Chunk) | Best NON-gold | 0.0526 | 0.0870 | 0.1069 | 0.1333 | 0.1426 (0.0507) | 0.1712 | 0.2148 | 0.3137 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |

   - **ملاحظتان حاسمتان من التوزيعات أعلاه:**
     1. **عدد الأسئلة ذات الشبيه القريب (`cosine >= 0.90`) في توسعات الحديث المرجعي:** على مستوى الشظية المجمّعة (`Chunk-level Q vs D`، وهو المتجه المودع فعليًا في الفهرس الكثيف `Dense_exp`) يبلغ عدد الأسئلة التي يصل تشابهها إلى `>= 0.90` **صفرًا (`0 / 224`)** في كلا النموذجين (`max = 0.8215` في `gemini-3.8-flash` و`0.8284` في `gemini-2.5-flash`). أمّا على مستوى العبارة المفردة (`Item-level symmetric cosine`)، فيوجد **`10` أسئلة فقط من أصل `224` (`4.5%`)** لها عبارة توسيع في حديثها المرجعي بتشابه `>= 0.90` في `gemini-3.8-flash` (مقابل **`28` سؤالًا = `12.5%`** في `gemini-2.5-flash`، لأن `gemini-3.8-flash` يصوغ التوسعات غالبًا كعناوين مصدرية «حكم ... / بيان ...» لا كأسئلة «ما حكم ...؟»).
     2. **توزيع أفضل حديث غير مرجعي (Best NON-gold) أعلى من توزيع الحديث المرجعي (GOLD):** في كلٍّ من تشابه جيب التمام و`Character 4-gram Jaccard`، ينزاح توزيع `Best NON-gold` إلى الأعلى مقارنةً بـ `GOLD` (`mean cosine = 0.8208` مقابل `0.7659`، و`33` سؤالًا غير مرجعي مقابل `10` أسئلة مرجعية عند `cosine >= 0.90`، و`mean 4-gram Jaccard = 0.2539` مقابل `0.1245` في `gemini-3.8-flash`)، لأن أخذ الحد الأقصى عبر ~`7,109` شظية غير مرجعية (~`30,800` عبارة فقهية في أبواب متجاورة من صحيح مسلم) ينتج مطابقات معجمية وموضوعية عالية مع الأحاديث المجاورة في الباب نفسه؛ وهو ما يفسّر لماذا يؤدي إعطاء وزن مرتفع لـ `Dense_exp` و`BM25_exp` (مثل `1:1:1:1` أو `2:1:1:1`) إلى خفض `hit@1` مقارنةً بـ `8:2:1:1`.

3. **المكسب على `dev` مفصولًا للأسئلة ذات الشبيه القريب (`cosine >= 0.90`) مقابل الأسئلة الخالية من أي شبيه قريب (`cosine < 0.90`):**

| نموذج التوسيع والشريحة في `dev` | خط الأنابيب | `n` | `hit@1` | `hit@5` | `hit@10` | `recall@50` | `MRR` |
|---|---|---:|---:|---:|---:|---:|---:|
| **`gemini-3.8-flash` — مع شبيه قريب (`cosine >= 0.90`)** | خط الأساس القديم (`Hybrid + mmarco`) | 10 | 10.0% (1/10) | 50.0% (5/10) | 50.0% (5/10) | 80.0% (8/10) | 0.270 |
| **`gemini-3.8-flash` — مع شبيه قريب (`cosine >= 0.90`)** | الجديد **بدون توسيع الوثائق** (`8:0:1:0`، مع HyDE) | 10 | 50.0% (5/10) | 100.0% (10/10) | 100.0% (10/10) | 100.0% (10/10) | 0.670 |
| **`gemini-3.8-flash` — مع شبيه قريب (`cosine >= 0.90`)** | الجديد **بدون HyDE** (`8:2:1:1`، استعلام خام) | 10 | 70.0% (7/10) | 100.0% (10/10) | 100.0% (10/10) | 100.0% (10/10) | 0.825 |
| **`gemini-3.8-flash` — مع شبيه قريب (`cosine >= 0.90`)** | **الخط الجديد الكامل (`Upgraded E5`, `8:2:1:1`)** | 10 | **70.0%** (7/10) | **100.0%** (10/10) | **100.0%** (10/10) | **100.0%** (10/10) | **0.808** |
| **`gemini-3.8-flash` — بدون شبيه قريب (`cosine < 0.90`)** | خط الأساس القديم (`Hybrid + mmarco`) | 214 | 28.0% (60/214) | 40.2% (86/214) | 43.9% (94/214) | 57.0% (122/214) | 0.334 |
| **`gemini-3.8-flash` — بدون شبيه قريب (`cosine < 0.90`)** | الجديد **بدون توسيع الوثائق** (`8:0:1:0`، مع HyDE) | 214 | **39.3%** (84/214) | **73.4%** (157/214) | 83.6% (179/214) | 93.9% (201/214) | **0.540** |
| **`gemini-3.8-flash` — بدون شبيه قريب (`cosine < 0.90`)** | الجديد **بدون HyDE** (`8:2:1:1`، استعلام خام) | 214 | 34.6% (74/214) | 68.7% (147/214) | 81.8% (175/214) | 93.5% (200/214) | 0.496 |
| **`gemini-3.8-flash` — بدون شبيه قريب (`cosine < 0.90`)** | **الخط الجديد الكامل (`Upgraded E5`, `8:2:1:1`)** | 214 | 36.0% (77/214) | 72.4% (155/214) | **84.6%** (181/214) | **93.9%** (201/214) | 0.515 |
| `gemini-2.5-flash` — مع شبيه قريب (`cosine >= 0.90`) | خط الأساس القديم (`Hybrid + mmarco`) | 28 | 25.0% (7/28) | 46.4% (13/28) | 53.6% (15/28) | 71.4% (20/28) | 0.347 |
| `gemini-2.5-flash` — مع شبيه قريب (`cosine >= 0.90`) | الجديد بدون توسيع الوثائق (`8:0:1:0`، مع HyDE) | 28 | 32.1% (9/28) | 78.6% (22/28) | 92.9% (26/28) | 96.4% (27/28) | 0.512 |
| `gemini-2.5-flash` — مع شبيه قريب (`cosine >= 0.90`) | الخط الجديد الكامل (`8:2:1:1` مع توسعات `g25flash`) | 28 | **39.3%** (11/28) | **82.1%** (23/28) | **92.9%** (26/28) | **96.4%** (27/28) | **0.579** |
| `gemini-2.5-flash` — بدون شبيه قريب (`cosine < 0.90`) | خط الأساس القديم (`Hybrid + mmarco`) | 196 | 27.6% (54/196) | 39.8% (78/196) | 42.9% (84/196) | 56.1% (110/196) | 0.329 |
| `gemini-2.5-flash` — بدون شبيه قريب (`cosine < 0.90`) | الجديد بدون توسيع الوثائق (`8:0:1:0`، مع HyDE) | 196 | **40.8%** (80/196) | **74.0%** (145/196) | 83.2% (163/196) | 93.9% (184/196) | **0.550** |
| `gemini-2.5-flash` — بدون شبيه قريب (`cosine < 0.90`) | الخط الجديد الكامل (`8:2:1:1` مع توسعات `g25flash`) | 196 | 37.2% (73/196) | 72.4% (142/196) | **84.2%** (165/196) | **93.9%** (184/196) | 0.521 |

4. **أثر E2 منفصلًا على المجموعة اليدوية `golden` (`n = 27`، صياغة بشرية 100%) مقابل `dev` (`n = 224`):**
   - حتى بعد استبعاد جميع الأسئلة الـ `10` ذات الشبيه القريب (`cosine >= 0.90`) في `dev`، يرفع خط الاسترجاع الجديد مقياس `hit@10` على الـ `214` سؤالًا المتبقية من **`43.9%` (`94/214`) إلى `84.6%` (`181/214`، مكسب `+40.7` نقطة مئوية)**، ويرفع `MRR` من `0.334` إلى `0.515`. ويلاحظ على شريحة الـ `214` سؤالًا الخالية من الأشباه القريبة أن إزالة توسيع الوثائق (`8:0:1:0`، أي `Dense_matn_HyDE + BM25_matn`) تحقق بمفردها `hit@10 = 83.6%` (`179/214`) و`hit@1 = 39.3%` و`MRR = 0.540`، بينما يضيف توسيع الوثائق في `8:2:1:1` سؤالين إضافيين في `hit@10` (`83.6% -> 84.6%`).
   - أمّا على المجموعة اليدوية `golden` (`n = 27`، التي لم يولّدها أي نموذج لغوي)، فإن إضافة توسيع الوثائق ترفع الاستدعاء والدقة في جميع الإعدادات:

| المقارنة لإثبات أثر E2 المستقل | المجموعة (`المصدر`) | بدون E2 (`matn` فقط) | مع E2 (`+ doc_expansion`) | المكسب الصافي |
|---|---|---|---|---|
| `BM25: matn` مقابل `BM25: matn + doc_expansion (1:1)` (`recall@50`) | `dev` (`n = 224`) | 50.9% (114/224) | **67.0%** (150/224) | **+16.1 نقطة مئوية** (+36 سؤالًا) |
| `BM25: matn` مقابل `BM25: matn + doc_expansion (1:1)` (`recall@50`) | **`golden` (`n = 27`)** | 85.2% (23/27) | **96.3%** (26/27) | **+11.1 نقطة مئوية** (+3 أسئلة، `MRR@10`: `0.464 → 0.548`) |
| `Legacy Hybrid (e5 + BM25_m)` مقابل `+ BM25_exp (1:1:1)` (`recall@50`) | `dev` (`n = 224`) | 58.0% (130/224) | **71.4%** (160/224) | **+13.4 نقطة مئوية** (+30 سؤالًا) |
| `Legacy Hybrid (e5 + BM25_m)` مقابل `+ BM25_exp (1:1:1)` (`recall@50`) | **`golden` (`n = 27`)** | 88.9% (24/27) | **100.0%** (27/27) | **+11.1 نقطة مئوية** (+3 أسئلة، `hit@10`: `85.2% → 92.6%`) |
| `E1 Dense gemini-001 (3072)` مقابل `E2 (2:1:1:1)` (`recall@50`) | `dev` (`n = 224`) | 93.8% (210/224) | **96.4%** (216/224) | **+2.6 نقطة مئوية** (+6 أسئلة) |
| `E1 Dense gemini-001 (3072)` مقابل `E2 (2:1:1:1)` (`recall@50`) | **`golden` (`n = 27`)** | 92.6% (25/27) | **100.0%** (27/27) | **+7.4 نقطة مئوية** (+2 سؤالان، `setR@50`: `90.2% → 98.1%`) |
| `New pipeline without doc expansion (8:0:1:0)` مقابل `New pipeline (8:2:1:1)` (`hit@1` / `MRR`) | **`golden` (`n = 27`)** | 81.5% (22/27) / `0.901` | **85.2%** (23/27) / **`0.926`** | **`+3.7% hit@1` (+1 سؤال) و`+0.025 MRR`** |

### ج) توثيق مصادر الأرقام وضبط المعاملات

- وُسم كل جدول نتائج في هذا السجل وفي `README.md` بمصدر أرقامه (`dev: synthetic_eval.jsonl / synthetic_eval_expanded.jsonl, n = 224` أو `golden: golden.jsonl / golden_expanded.jsonl, n = 27`).
- جميع المعاملات المعايَرة — أوزان دمج RRF (`2:1:1:1`، `8:2:1:1`، إلخ)، ومعامل المزج $\alpha$ في HyDE (`0.7:0.3` / `0.8:0.2`)، وعمق المرشحين `top_k_in` — اختيرت حصريًا على مجموعة التطوير `dev` (`n = 224`)، واستُخدمت المجموعة اليدوية `golden` (`n = 27`) للتأكيد المستقل فقط، بينما لم تُلمس مسودة `holdout_draft.jsonl` (`n = 120`) في أي تجربة.

---

## 28. التجربة Step 4 — إعادة تشغيل E2 وE4 بأحدث نموذج Flash متاح (`gemini-3.8-flash`) وفحص النماذج غير Gemini

**تاريخ القياس:** 2026-11-14 · **الكود:** `src/experiment_step4_newer_llm.py`, `src/build_holdout_draft.py` · **النتائج الخام:** `data/processed/step4_results.json`

### 1) مسح نماذج Vertex AI المتاحة في المشروع (`generate-504115`) والمنطقة (`us-central1` مقابل `global`)

فُحصت جميع نماذج التوليد والتضمين في مشروع Vertex AI الحالي (`generate-504115`) عبر منطقتي `us-central1` (الافتراضية في `.env`) و`global`:

| النموذج | الفئة | `us-central1` | `global` | الحالة وأقل إعداد تفكير (`thinking_config`) يُرجع JSON صالحًا |
|---|---|---|---|---|
| `gemini-2.5-flash-lite` | Flash-Lite (GA) | متاح | متاح | `thinking_budget=0` |
| `gemini-2.5-flash` | Flash (GA — خط الأساس في E2/E4) | متاح | متاح | `thinking_budget=0` (`0` توكن تفكير) |
| `gemini-2.5-pro` | Pro (GA — خط الأساس في التوليد) | متاح | متاح | `thinking_budget=128` |
| `gemini-3-flash-preview` | Flash (Preview) | `404 NOT_FOUND` | متاح | `thinking_level="MINIMAL"` |
| `gemini-3.1-flash-lite` | Flash-Lite (GA) | `404 NOT_FOUND` | متاح | `thinking_level="MINIMAL"` |
| `gemini-3.1-pro-preview` | Pro (Preview) | `404 NOT_FOUND` | متاح | `thinking_level="LOW"` |
| `gemini-3.5-flash-lite` | Flash-Lite (GA) | `404 NOT_FOUND` | متاح | `thinking_level="MINIMAL"` |
| `gemini-3.5-flash` / `3.6-flash` / `3.7-flash` | Flash (GA) | `404 NOT_FOUND` | متاح | `thinking_level="LOW"` |
| **`gemini-3.8-flash`** | **أحدث نموذج Flash مستقر (GA)** | `404 NOT_FOUND` | **متاح** | **`thinking_level="LOW"`** (`MINIMAL` و`thinking_budget=0` يُرجعان `400 INVALID_ARGUMENT`؛ ومع `LOW` كان استهلاك التفكير الفعلي `thoughts_tokens = 0`) |
| **`gemini-4-argon`** (و`hydrogen` / `carbon`) | **أحدث نموذج Pro/Frontier (GA)** | `404 NOT_FOUND` | **متاح** | `thinking_level="LOW"` |
| `claude-sonnet-4-5` / `claude-haiku-4-5` | Anthropic (Vertex Model Garden) | `429` (حصة `0`) | `404` | غير متاح (الحصة المخصصة في المشروع = `0`) |
| `llama-3.3-70b` / `llama-4-*` / `mistral-*` / `deepseek-*` | Model Garden MaaS | `404` | `404` | غير مفعَّل في المشروع |
| **`gemma-4-26b-a4b-it-maas`** | **نموذج مفتوح غير Gemini (Vertex MaaS)** | `404` | **متاح** | يدعم `response_mime_type="application/json"` مباشرةً |

### 2) مقارنة التكلفة واستهلاك التوكنات جنباً إلى جنب (`gemini-2.5-flash` مقابل `gemini-3.8-flash`)

أُعيد تشغيل **E2** (توسيع جميع المتون الـ `7,110` بنفس المطالبة `DOC_EXPANSION_PROMPT` دون أي تعديل) و**E4** (توليد متون افتراضية HyDE لجميع الاستعلامات الـ `251` بنفس المطالبة `HYDE_PROMPT` دون أي تعديل) باستخدام **`gemini-3.8-flash`** (`location="global"`, `thinking_level="LOW"`, `temperature=0`):

| التجربة | النموذج | النداءات (`Flash Calls`) | توكنات الإدخال (`Prompt`) | توكنات الإخراج (`Output`) | توكنات التفكير (`Thoughts`) | إجمالي التوكنات | التكلفة الفعلية (USD) | البصمة (`sha256[:16]`) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **E2 (توسيع 7,110 وثيقة)** | `gemini-2.5-flash` | 285 | 637,598 | 572,369 | 0 | 1,209,967 | **`$1.6222`** | `369fbabbd46872fa` |
| **E2 (توسيع 7,110 وثيقة)** | **`gemini-3.8-flash`** | 286 | 634,935 | 533,825 | 0 | 1,168,760 | **`$2.4780`** | `b989b5dcaf84109a` |
| **E4 (HyDE لـ 251 سؤالًا)** | `gemini-2.5-flash` | 17 | 7,034 | 7,780 | 0 | 14,814 | **`$0.0216`** | `ef69df7509df5ff8` |
| **E4 (HyDE لـ 251 سؤالًا)** | **`gemini-3.8-flash`** | 17 | 7,034 | 28,099 | 0 | 35,133 | **`$0.1106`** | `17ea45adcd81530e` |

*(التسعير القياسي لـ Vertex AI: `$0.30 / $2.50` لكل مليون توكن إدخال/إخراج في `gemini-2.5-flash`، و`$0.75 / $3.75` لكل مليون توكن في `gemini-3.8-flash`، بالإضافة إلى 40 نداء `gemini-embedding-001` لتضمين التوسعات والاستعلامات).*

### 3) مقارنة نتائج E2 جنباً إلى جنب: `gemini-2.5-flash` مقابل `gemini-3.8-flash`

*(المصدر: المجموعة التطويرية `dev` = `synthetic_eval_expanded.jsonl`، `n = 224`، والمجموعة اليدوية `golden` = `golden_expanded.jsonl`، `n = 27`؛ أوزان الدمج معايَرة على `dev`)*

| الإعداد (E2 Document Expansion) | النموذج | `dev` `hit@1` | `dev` `hit@5` | `dev` `hit@10` | `dev` `recall@50` | `dev` `MRR@10` | `golden` `hit@1` | `golden` `hit@5` | `golden` `hit@10` | `golden` `recall@50` | `golden` `MRR@10` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BM25: doc_expansion only` | `gemini-2.5-flash` | 13.8% | 29.5% | 37.9% | 55.8% (125) | 0.211 | 48.1% | 70.4% | 77.8% | 96.3% (26) | 0.579 |
| `BM25: doc_expansion only` | `gemini-3.8-flash` | 12.5% | 25.9% | 33.5% | 50.0% (112) | 0.186 | 33.3% | 70.4% | 70.4% | 88.9% (24) | 0.486 |
| `BM25: matn + doc_expansion (1:1)` | `gemini-2.5-flash` | 17.0% | 38.4% | 46.9% | 67.0% (150) | 0.264 | 44.4% | 70.4% | 74.1% | 96.3% (26) | 0.548 |
| `BM25: matn + doc_expansion (1:1)` | `gemini-3.8-flash` | 15.2% | 33.0% | 44.6% | 64.3% (144) | 0.231 | 44.4% | 70.4% | 77.8% | 92.6% (25) | 0.552 |
| `Dense: doc_expansion (3072) only` | `gemini-2.5-flash` | 29.0% | 58.0% | 71.0% | 87.9% (197) | 0.419 | 59.3% | 92.6% | 92.6% | 100.0% (27) | 0.720 |
| `Dense: doc_expansion (3072) only` | `gemini-3.8-flash` | 24.6% | 50.0% | 62.1% | 78.6% (176) | 0.351 | 40.7% | 92.6% | 96.3% | 96.3% (26) | 0.615 |
| `E2 (3072): Dense_m + Dense_e (1:1)` | `gemini-2.5-flash` | 37.9% | 69.2% | 80.4% | 95.5% (214) | 0.517 | 63.0% | 88.9% | 92.6% | 100.0% (27) | 0.753 |
| `E2 (3072): Dense_m + Dense_e (1:1)` | `gemini-3.8-flash` | 33.9% | 60.3% | 77.2% | 94.2% (211) | 0.468 | 66.7% | 88.9% | 88.9% | 100.0% (27) | 0.772 |
| `E2 (3072): 4-way RRF (2:1:1:1)` | `gemini-2.5-flash` | 33.5% | 67.4% | 79.9% | **96.4%** (216) | 0.483 | 66.7% | 88.9% | 92.6% | **100.0%** (27) | 0.768 |
| `E2 (3072): 4-way RRF (2:1:1:1)` | `gemini-3.8-flash` | 31.7% | 66.5% | 78.1% | 95.1% (213) | 0.463 | 51.9% | **92.6%** | 92.6% | **100.0%** (27) | 0.686 |
| **`E2 (3072): 4-way RRF (8:2:1:1)`** | `gemini-2.5-flash` | **37.5%** | **71.9%** | 81.7% | 94.2% (211) | **0.525** | **81.5%** | 88.9% | 92.6% | 92.6% (25) | **0.858** |
| **`E2 (3072): 4-way RRF (8:2:1:1)`** | **`gemini-3.8-flash`** | 36.2% | 70.1% | **82.6%** | 93.8% (210) | 0.511 | 70.4% | **92.6%** | 92.6% | 92.6% (25) | 0.806 |

### 4) مقارنة نتائج E4 (HyDE) جنباً إلى جنب: `gemini-2.5-flash` مقابل `gemini-3.8-flash`

*(المصدر: `dev` = `synthetic_eval_expanded.jsonl`، `n = 224`، و`golden` = `golden_expanded.jsonl`، `n = 27`؛ أوزان المزج معايَرة على `dev`)*

| الإعداد (E4 HyDE) | النموذج | `dev` `hit@1` | `dev` `hit@5` | `dev` `hit@10` | `dev` `recall@50` | `dev` `MRR@10` | `golden` `hit@1` | `golden` `hit@5` | `golden` `hit@10` | `golden` `recall@50` | `golden` `MRR@10` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `HyDE only (RETRIEVAL_QUERY -> Dense_m)` | `gemini-2.5-flash` | 21.9% | 49.1% | 56.2% | 74.6% (167) | 0.335 | 85.2% | 100.0% | 100.0% | 100.0% (27) | 0.910 |
| **`HyDE only (RETRIEVAL_QUERY -> Dense_m)`** | **`gemini-3.8-flash`** | **29.0%** | **58.0%** | **67.4%** | **81.7%** (183) | **0.416** | **85.2%** | **100.0%** | **100.0%** | **100.0%** (27) | 0.907 |
| `BM25_matn (query + HyDE)` | `gemini-2.5-flash` | 19.6% | 37.9% | 44.6% | 62.1% (139) | 0.276 | 66.7% | 88.9% | 96.3% | 100.0% (27) | 0.760 |
| **`BM25_matn (query + HyDE)`** | **`gemini-3.8-flash`** | **29.9%** | **56.2%** | **61.6%** | **71.9%** (161) | **0.415** | **92.6%** | **96.3%** | **100.0%** | **100.0%** (27) | **0.941** |
| `Dense_m (0.7*q + 0.3*HyDE_q)` | `gemini-2.5-flash` | **42.4%** | 72.3% | 81.7% | 92.4% (207) | **0.559** | **85.2%** | **100.0%** | **100.0%** | **100.0%** (27) | **0.926** |
| **`Dense_m (0.7*q + 0.3*HyDE_q)`** | **`gemini-3.8-flash`** | 40.6% | **72.8%** | **83.9%** | **94.2%** (211) | 0.544 | **85.2%** | **100.0%** | **100.0%** | **100.0%** (27) | **0.926** |
| `Dense_m (0.8*q + 0.2*HyDE_q)` | `gemini-2.5-flash` | **43.3%** | 72.3% | 81.2% | 92.9% (208) | **0.562** | 77.8% | 96.3% | 100.0% | 100.0% (27) | 0.863 |
| **`Dense_m (0.8*q + 0.2*HyDE_q)`** | **`gemini-3.8-flash`** | 41.5% | **75.4%** | **83.5%** | **94.2%** (211) | 0.554 | **85.2%** | **100.0%** | **100.0%** | **100.0%** (27) | **0.917** |
| `E2 (2:1:1:1) with blended q (0.7*q + 0.3*HyDE_q)` | `gemini-2.5-flash` | **36.2%** | **70.5%** | **81.2%** | **96.0%** (215) | **0.509** | **74.1%** | 96.3% | **100.0%** | **100.0%** (27) | **0.842** |
| `E2_g38 (2:1:1:1) with blended q (0.7*q + 0.3*HyDE_q)` | `gemini-3.8-flash` | 34.8% | 68.8% | **81.2%** | **96.0%** (215) | 0.492 | 63.0% | **100.0%** | **100.0%** | **100.0%** (27) | 0.796 |
| **`E2_g38 (8:2:1:1) with blended q (0.7*q + 0.3*HyDE_q)`** | **`gemini-3.8-flash`** | **37.5%** | **73.7%** | **85.3%** | 94.2% (211) | **0.528** | **85.2%** | **100.0%** | **100.0%** | **100.0%** (27) | **0.926** |

**تحليل المقارنة بين `gemini-2.5-flash` و`gemini-3.8-flash`:**
1. **في توسيع الوثائق (E2):** يتفوق `gemini-2.5-flash` قليلًا في التوسيع المعجمي والدلالي للمتون (`recall@50 = 96.4%` مقابل `95.1%` على `dev`، وبأقل تكلفة `$1.62` مقابل `$2.48`)، لأن مخرجات `gemini-2.5-flash` أكثر كثافة في المرادفات الفقهية القياسية، بينما رفع `gemini-3.8-flash` مع الوزن `(8:2:1:1)` مقياس `hit@10` على `dev` إلى `82.6%`.
2. **في الاستعلام الافتراضي (E4 HyDE):** حقق **`gemini-3.8-flash`** قفزة كبيرة جدًا في جودة المتون النبوية الافتراضية المولَّدة؛ إذ ارتفع البحث بالمتن الافتراضي وحده على `dev` من `hit@10 = 56.2%` إلى **`67.4%`** (+11.2 نقطة مئوية)، وفي `BM25 (query + HyDE)` من `hit@10 = 44.6%` إلى **`61.6%`** على `dev` ومن `MRR@10 = 0.760` إلى **`0.941`** (`hit@1 = 92.6%`, `hit@10 = 100%`) على `golden`! وعند مزج متجه الاستعلام مع HyDE (`0.7*q + 0.3*HyDE_q` أو `0.8*q + 0.2*HyDE_q`) من `gemini-3.8-flash`، ارتفع `hit@5` على `dev` إلى **`75.4%`** و`hit@10` إلى **`83.9%–85.3%`** مع **`hit@1 = 85.2%` و`hit@3 = 100%` و`hit@5 = 100%` و`hit@10 = 100%` و`MRR@10 = 0.926`** على `golden`.

### 5) إعادة توليد مسودة الاختبار `data/raw/holdout_draft.jsonl` بنموذج غير Gemini (`gemma-4-26b-a4b-it-maas`)

- تبيّن من فحص Vertex Model Garden أن نماذج الطرف الثالث التجارية (مثل Anthropic `claude-sonnet-4-5` و`claude-haiku-4-5`) غير متاحة في هذا المشروع (`429 Quota exceeded` بحصة مخصصة `0`)، كما أن `Llama` و`Mistral` و`DeepSeek` غير مفعَّلة (`404`).
- في المقابل، يتوفر النموذج المفتوح غير Gemini **`gemma-4-26b-a4b-it-maas`** عبر Vertex Model Garden MaaS (`location="global"`). لذلك أُعيد توليد جميع الأسئلة الـ `105` القابلة للإجابة في `data/raw/holdout_draft.jsonl` (بالإضافة إلى الـ `15` سؤال رفض المتحقَّق من غيابها عن المدونة) باستخدام **`gemma-4-26b-a4b-it-maas`** (`src/build_holdout_draft.py`، `9` نداءات توليد + `1` نداء تضمين، بصمة `sha256[:16] = 71ccb73d0a308371`) وتحقّق منها `src/validate_holdout_draft.py` بالكامل (`120` سؤالًا، `candidate_gold_ids` بمتوسط `11.9`)، لضمان عدم اشتراك مسودة الاختبار المحتجزة في عائلة نماذج Gemini المستخدمة في التوسيع أو التوليد.

---

## 29. التجربة الخامسة (E5) — خط أنابيب الاسترجاع النهائي، تعريف المقاييس، جدول الاستئصال (Ablation)، شبكة ضبط أوزان RRF، وتقييم الإجابات (`answer_eval`)

**تاريخ القياس:** 2026-11-14
**السكربتات والملفات:** `src/experiment_e5_final_pipeline.py` · `src/experiment_e5_ablation_and_leakage.py` · `src/retrieve.py` · `src/config.py` · `data/processed/e5_results.json` · `data/processed/e5_ablation_and_leakage.json`

### 1) تعريف المقاييس والمقامات الدقيقة (Metric Definitions & Denominators)

تجنبًا لأي التباس بين `hit@k` و`recall@k`:
- **`hit@k` (في `src/evaluate.py:first_hit_rank` و`evaluate`):** هو معدل الإصابة الثنائي على مستوى السؤال (`binary query-level hit rate at rank k`)، أي نسبة الأسئلة القابلة للإجابة التي يظهر لها **حديث مرجعي واحد على الأقل** (`item["hadith_ids"]`) ضمن أول `k` نتائج مسترجعة.
- **`recall@50` (في `src/experiment_e0_gold_expansion.py:evaluate_with_recall50`):** هو **`hit@50`** الثنائي (أي نسبة الأسئلة التي يظهر لها حديث مرجعي واحد على الأقل ضمن أول `50` نتيجة). أمّا نسبة استدعاء كامل مجموعة الأحاديث المتكافئة للسؤال الواحد عند العمق `50` فتُسمّى صراحةً **`setR@50`** (`per-query set recall at 50` = $\frac{1}{N}\sum_{i=1}^N \frac{|R_{50}(q_i) \cap G(q_i)|}{|G(q_i)|}$).
- **`MRR` (`MRR@10`):** متوسط مقلوب الرتبة لأول حديث مرجعي ضمن أول `10` نتائج ($\frac{1}{N}\sum_{i=1}^N \frac{1}{\text{rank}_i}$ إذا كان $\text{rank}_i \le 10$، و`0` خلاف ذلك).
- **المقامات الدقيقة (Denominators):**
  - **مجموعة التطوير `dev` (`data/raw/synthetic_eval.jsonl` و`data/processed/synthetic_eval_expanded.jsonl`):** المقام = **`n = 224` سؤالًا قابلًا للإجابة** (جميع عناصر الملف الـ 224 أسئلة قابلة للإجابة).
  - **المجموعة اليدوية `golden` (`data/raw/golden.jsonl` و`data/processed/golden_expanded.jsonl`):** المقام في مقاييس الاسترجاع (`hit@k` / `MRR`) = **`n = 27` سؤالًا قابلًا للإجابة** (من أصل 33 سطرًا في الملف: `27` سؤال متن قابلًا للإجابة + `3` أسئلة رفض خارج النطاق تُفحص في `answer_eval` وتُستثنى من `hit@k` + `3` أسئلة تراجم رواة مستثناة من تقييم المتون).
- **الأرقام الدقيقة وراء القفزة `44% -> 85%` (على `dev`) و`85% -> 100%` (على `golden`):**
  - كلا الرقمين يعبر عن المقياس **`hit@10`**:
    - **على `dev` (`n = 224`):** ارتفع **`hit@10`** من **`44.2%` (`99 / 224`، المقرَّب إلى `44%`)** في خط الأساس القديم (`Hybrid + mmarco` عند عمق 10) إلى **`85.3%` (`191 / 224`، المقرَّب إلى `85%`)** في خط الاسترجاع المرقّى (`Upgraded E5`). وبالتوازي ارتفع `hit@5` من `40.6%` (`91/224`، المقرَّب إلى `41%`) إلى `73.7%` (`165/224`، المقرَّب إلى `74%`)، و`hit@3` من `37.1%` (`83/224`، `37%`) إلى **`63.8%` (`143/224`، المقرَّب إلى `64%`)**، و`hit@1` من `27.2%` (`61/224`، المقرَّب إلى `27%`) إلى `37.5%` (`84/224`، المقرَّب إلى `38%`)، و`recall@50` (`hit@50`) من `58.0%` (`130/224`) إلى `94.2%` (`211/224`)، و`MRR` من `0.331` إلى `0.528`.
    - **على `golden` (`n = 27`):** ارتفع **`hit@10`** من **`85.2%` (`23 / 27`، المقرَّب إلى `85%`)** في خط الأساس القديم إلى **`100.0%` (`27 / 27`، `100%`)** في خط الاسترجاع المرقّى (`Upgraded E5`). وبالتوازي ارتفع `hit@5` من `81.5%` (`22/27`، المقرَّب إلى `81%`) إلى **`100.0%` (`27/27`)**، و`hit@3` من `74.1%` (`20/27`، `74%`) إلى **`100.0%` (`27/27`، `100%`)**، و`hit@1` من `55.6%` (`15/27`، المقرَّب إلى `56%`) إلى **`85.2%` (`23/27`، المقرَّب إلى `85%`)**، و`MRR` من `0.665` إلى **`0.926`**.

### 2) توصيف حقول RRF الأربعة وأوزانها في خط الأنابيب المرقّى (`UpgradedRetriever`)

يدمج `UpgradedRetriever` (المربوط في `src/pipeline.py` و`src/retrieve.py` كمسار افتراضي `RETRIEVAL_PIPELINE = "upgraded"`، مع الإبقاء على `MUSNAD_RETRIEVAL_PIPELINE=legacy` كخط أساس محلي واحتياطي تلقائي عند تعذر واجهة API أو انتهاء مهلتها) أربعة حقول استرجاع عبر Reciprocal Rank Fusion (`RRF_K = 60`، بعمق مرشحين `c = 50` لكل حقل، ودون معيد ترتيب Cross-Encoder استنادًا إلى نتائج E3):
1. **`Dense_matn_HyDE` (الوزن = `8`):** فهرس `gemini-embedding-001` (`3072d`، `RETRIEVAL_DOCUMENT`) لمتون الأحاديث المطبَّعة (`matn` فقط)، يُستعلَم عنه بالمتجه الممزوج المطبَّع طوليًا $v_{\text{blend}} = \text{norm}(0.7 \cdot v_q + 0.3 \cdot v_{\text{HyDE\_q}})$ حيث $v_q$ تضمين السؤال الأصلي و$v_{\text{HyDE\_q}}$ تضمين المتن الافتراضي المولَّد بـ `gemini-3.8-flash` (`RETRIEVAL_QUERY`).
2. **`Dense_exp_HyDE` (الوزن = `2`):** فهرس `gemini-embedding-001` (`3072d`، `RETRIEVAL_DOCUMENT`) لنصوص توسيع الوثائق (`expansion_text` المولَّدة بـ `gemini-3.8-flash` في Step 4)، يُستعلَم عنه بنفس المتجه الممزوج $v_{\text{blend}}$.
3. **`BM25_matn` (الوزن = `1`):** فهرس `BM25Index(k1=1.5, b=0.75)` فوق متون الأحاديث المطبَّعة (`matn`)، يُستعلَم عنه بنص السؤال الأصلي المطبَّع (`question`).
4. **`BM25_exp` (الوزن = `1`):** فهرس `BM25Index(k1=1.5, b=0.75)` فوق نصوص توسيع الوثائق (`expansion_text` من `gemini-3.8-flash`)، يُستعلَم عنه بنص السؤال الأصلي المطبَّع (`question`).

### 3) جدول الاستئصال الكامل (Ablation Table) على `dev` (`n = 224`) و`golden` (`n = 27`)

يوضح الجدول التالي أثر كل مكوّن من مكونات خط الاسترجاع الجديد على كلٍّ من `dev` (`n = 224`) و`golden` (`n = 27`). *(ملاحظة: أرقام `hit@1` و`hit@5` و`hit@10` و`MRR` متطابقة تمامًا سواء حُسبت على ملفات المرجع الأصلية `synthetic_eval.jsonl` / `golden.jsonl` أو الموسَّعة `*_expanded.jsonl` للخطوط الجديدة، وفي الخط القديم يتطابق `hit@1/5/10` تمامًا مع فرق `0.001` فقط في `MRR` على `dev`: `0.330` على الأصلي و`0.331` على الموسَّع)*:

| خط الأنابيب / تجربة الاستئصال (Ablation Variant) | حقول RRF وأوزانها (`Dense_matn : Dense_exp : BM25_matn : BM25_exp`) | `dev` `hit@1` (`n=224`) | `dev` `hit@5` (`n=224`) | `dev` `hit@10` (`n=224`) | `dev` `MRR` (`n=224`) | `golden` `hit@1` (`n=27`) | `golden` `hit@5` (`n=27`) | `golden` `hit@10` (`n=27`) | `golden` `MRR` (`n=27`) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **خط الأساس القديم (`Old pipeline: Hybrid + mmarco`, d=10)** | `e5-base_matn : BM25_matn = 1 : 1` + `mmarco` top-10 | 27.2% (61/224) | 40.6% (91/224) | 44.2% (99/224) | 0.331 | 55.6% (15/27) | 81.5% (22/27) | 85.2% (23/27) | 0.665 |
| خط الأساس القديم بدون معيد ترتيب (`Old Hybrid RRF`) | `e5-base_matn : BM25_matn = 1 : 1` (بدون `mmarco`) | 17.9% (40/224) | 36.6% (82/224) | 44.2% (99/224) | 0.256 | 44.4% (12/27) | 74.1% (20/27) | 85.2% (23/27) | 0.565 |
| **الخط الجديد الكامل (`New pipeline: Upgraded E5`, بأوزان مضبوطة)** | **`8 : 2 : 1 : 1`** (`Dense_matn_HyDE : Dense_exp_HyDE : BM25_matn : BM25_exp`) | **37.5%** (84/224) | **73.7%** (165/224) | **85.3%** (191/224) | **0.528** | **85.2%** (23/27) | **100.0%** (27/27) | **100.0%** (27/27) | **0.926** |
| الخط الجديد **بدون توسيع الوثائق** (`without doc expansion`, `8:1`) | `8 : 0 : 1 : 0` (`Dense_matn_HyDE : BM25_matn = 8 : 1`) | 39.7% (89/224) | 74.6% (167/224) | 84.4% (189/224) | 0.545 | 81.5% (22/27) | 100.0% (27/27) | 100.0% (27/27) | 0.901 |
| الخط الجديد **بدون توسيع الوثائق** (`without doc expansion`, `3:1`) | `3 : 0 : 1 : 0` (`Dense_matn_HyDE : BM25_matn = 3 : 1`) | 33.5% (75/224) | 69.2% (155/224) | 82.6% (185/224) | 0.490 | 63.0% (17/27) | 88.9% (24/27) | 100.0% (27/27) | 0.765 |
| الخط الجديد **بدون توسيع الوثائق** (`without doc expansion`, `1:1`) | `1 : 0 : 1 : 0` (`Dense_matn_HyDE : BM25_matn = 1 : 1`) | 30.4% (68/224) | 59.4% (133/224) | 74.1% (166/224) | 0.424 | 59.3% (16/27) | 85.2% (23/27) | 92.6% (25/27) | 0.700 |
| الخط الجديد **بدون HyDE** (`without HyDE`, استعلام خام $1.0q$) | `8 : 2 : 1 : 1` (`Dense_matn : Dense_exp : BM25_matn : BM25_exp`، بدون HyDE) | 36.2% (81/224) | 70.1% (157/224) | 82.6% (185/224) | 0.511 | 70.4% (19/27) | 92.6% (25/27) | 92.6% (25/27) | 0.806 |
| الخط الجديد **بدون توسيع الوثائق وبدون HyDE** (`8:1`, استعلام خام) | `8 : 0 : 1 : 0` (`Dense_matn : BM25_matn = 8 : 1`، بدون HyDE) | 42.4% (95/224) | 71.4% (160/224) | 80.8% (181/224) | 0.546 | 77.8% (21/27) | 85.2% (23/27) | 92.6% (25/27) | 0.826 |
| الخط الجديد **بأوزان RRF متساوية (`1:1:1:1`)** | `1 : 1 : 1 : 1` (`Dense_matn_HyDE : Dense_exp_HyDE : BM25_matn : BM25_exp`) | 31.7% (71/224) | 65.6% (147/224) | 78.1% (175/224) | 0.461 | 51.9% (14/27) | 100.0% (27/27) | 100.0% (27/27) | 0.733 |
| الخط الجديد **بأوزان RRF متساوية (`1:1:1:1`) وبدون HyDE** | `1 : 1 : 1 : 1` (`Dense_matn : Dense_exp : BM25_matn : BM25_exp`، بدون HyDE) | 29.0% (65/224) | 62.5% (140/224) | 75.9% (170/224) | 0.432 | 51.9% (14/27) | 92.6% (25/27) | 92.6% (25/27) | 0.674 |

### 4) شبكة ضبط أوزان RRF الكاملة (RRF Weight Tuning Grid — مختارة على `dev` ومفحوصة على `golden`)

جميع أوزان RRF الأربعة `(w_Dense_matn : w_Dense_exp : w_BM25_matn : w_BM25_exp)` **ضُبطت واختيرت حصريًا على مجموعة التطوير `dev` (`n = 224`)** لتحقيق أعلى `hit@10` مع الحفاظ على `hit@5` و`MRR`، ثم قيس أداؤها على المجموعة اليدوية `golden` (`n = 27`) للتأكيد المستقل. يعرض الجدولان التاليان جميع إعدادات الأوزان الـ `24` التي جُرّبت (أولًا مع مزج الاستعلام بـ HyDE `0.7*q + 0.3*HyDE_q`، وثانيًا بالاستعلام الخام `1.0*q` بدون HyDE):

#### أ) شبكة أوزان RRF مع HyDE (`0.7*q + 0.3*HyDE_q` من `gemini-3.8-flash`)

| # | الأوزان `(Dense_m : Dense_e : BM25_m : BM25_e)` | الوصف | `dev` `hit@1` | `dev` `hit@5` | `dev` `hit@10` | `dev` `recall@50` | `dev` `MRR` | `golden` `hit@1` | `golden` `hit@5` | `golden` `hit@10` | `golden` `recall@50` | `golden` `MRR` |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `1 : 0 : 0 : 0` | `Dense_matn` فقط | 40.6% | 72.8% | 83.9% | 94.2% | 0.545 | 85.2% | 100.0% | 100.0% | 100.0% | 0.926 |
| 2 | `0 : 1 : 0 : 0` | `Dense_exp` فقط | 27.7% | 56.7% | 67.4% | 84.8% | 0.397 | 63.0% | 96.3% | 100.0% | 100.0% | 0.775 |
| 3 | `0 : 0 : 1 : 0` | `BM25_matn` فقط | 17.9% | 28.6% | 36.6% | 50.9% | 0.228 | 33.3% | 63.0% | 66.7% | 85.2% | 0.464 |
| 4 | `0 : 0 : 0 : 1` | `BM25_exp` فقط | 12.5% | 25.9% | 33.5% | 50.0% | 0.186 | 33.3% | 70.4% | 70.4% | 88.9% | 0.486 |
| 5 | `0 : 0 : 1 : 1` | `BM25_matn + BM25_exp (1:1)` | 15.2% | 33.0% | 44.6% | 64.3% | 0.231 | 44.4% | 70.4% | 77.8% | 92.6% | 0.552 |
| 6 | `1 : 0 : 1 : 0` | `Dense_matn + BM25_matn (1:1)` | 30.4% | 59.4% | 74.1% | 91.1% | 0.424 | 59.3% | 85.2% | 92.6% | 100.0% | 0.700 |
| 7 | `2 : 0 : 1 : 0` | `Dense_matn + BM25_matn (2:1)` | 33.5% | 63.8% | 80.8% | 94.2% | 0.465 | 63.0% | 88.9% | 100.0% | 100.0% | 0.745 |
| 8 | `3 : 0 : 1 : 0` | `Dense_matn + BM25_matn (3:1)` | 33.5% | 69.2% | 82.6% | 94.2% | 0.490 | 63.0% | 88.9% | 100.0% | 100.0% | 0.765 |
| 9 | `8 : 0 : 1 : 0` | `Dense_matn + BM25_matn (8:1)` | 39.7% | 74.6% | 84.4% | 94.2% | 0.545 | 81.5% | 100.0% | 100.0% | 100.0% | 0.901 |
| 10 | `1 : 1 : 0 : 0` | `Dense_matn + Dense_exp (1:1)` | 36.6% | 65.6% | 80.8% | 95.1% | 0.494 | 85.2% | 100.0% | 100.0% | 100.0% | 0.917 |
| 11 | `2 : 1 : 0 : 0` | `Dense_matn + Dense_exp (2:1)` | 35.7% | 69.2% | 81.7% | 94.2% | 0.499 | 81.5% | 100.0% | 100.0% | 100.0% | 0.907 |
| 12 | `1 : 0 : 0 : 1` | `Dense_matn + BM25_exp (1:1)` | 26.8% | 55.8% | 76.8% | 93.3% | 0.401 | 59.3% | 85.2% | 100.0% | 100.0% | 0.720 |
| 13 | `2 : 0 : 0 : 1` | `Dense_matn + BM25_exp (2:1)` | 30.4% | 61.2% | 83.0% | 94.2% | 0.448 | 66.7% | 92.6% | 100.0% | 100.0% | 0.776 |
| 14 | `3 : 0 : 0 : 1` | `Dense_matn + BM25_exp (3:1)` | 33.0% | 68.8% | 83.0% | 94.2% | 0.482 | 66.7% | 92.6% | 100.0% | 100.0% | 0.790 |
| 15 | `2 : 0 : 1 : 1` | `Dense_m + BM25_m + BM25_e (2:1:1)` | 29.9% | 62.5% | 80.4% | 94.6% | 0.446 | 63.0% | 92.6% | 100.0% | 100.0% | 0.761 |
| 16 | `3 : 0 : 1 : 1` | `Dense_m + BM25_m + BM25_e (3:1:1)` | 33.9% | 68.8% | 83.5% | 95.1% | 0.486 | 63.0% | 92.6% | 100.0% | 100.0% | 0.772 |
| 17 | `1 : 1 : 1 : 1` | أوزان متساوية (`Equal 4-way RRF`) | 31.7% | 65.6% | 78.1% | 93.3% | 0.461 | 51.9% | 100.0% | 100.0% | 100.0% | 0.733 |
| 18 | `2 : 1 : 1 : 1` | رباعي الحقول (`2:1:1:1`) | 34.8% | 68.8% | 81.2% | **96.0%** | 0.492 | 63.0% | 100.0% | 100.0% | 100.0% | 0.796 |
| 19 | `3 : 1 : 1 : 1` | رباعي الحقول (`3:1:1:1`) | 36.2% | 70.5% | 82.1% | 95.5% | 0.509 | 74.1% | 100.0% | 100.0% | 100.0% | 0.864 |
| 20 | `4 : 1 : 1 : 1` | رباعي الحقول (`4:1:1:1`) | 39.3% | 71.9% | 83.9% | 94.2% | 0.530 | 77.8% | 100.0% | 100.0% | 100.0% | 0.883 |
| 21 | `4 : 2 : 1 : 1` | رباعي الحقول (`4:2:1:1`) | 37.5% | 70.5% | 83.0% | 95.5% | 0.518 | 77.8% | 100.0% | 100.0% | 100.0% | 0.880 |
| 22 | `6 : 2 : 1 : 1` | رباعي الحقول (`6:2:1:1`) | 38.4% | 71.9% | 83.9% | 94.2% | 0.530 | 77.8% | 100.0% | 100.0% | 100.0% | 0.889 |
| **23** | **`8 : 2 : 1 : 1`** | **رباعي الحقول (`8:2:1:1` — المختار على `dev`)** | **37.5%** | **73.7%** | **85.3%** | **94.2%** | **0.528** | **85.2%** | **100.0%** | **100.0%** | **100.0%** | **0.926** |
| 24 | `10 : 2 : 1 : 1` | رباعي الحقول (`10:2:1:1`) | 37.5% | 74.1% | 85.3% | 94.2% | 0.532 | 85.2% | 100.0% | 100.0% | 100.0% | 0.926 |

#### ب) شبكة أوزان RRF بدون HyDE (استعلام خام `1.0*q` مع توسعات `gemini-3.8-flash`)

| # | الأوزان `(Dense_m : Dense_e : BM25_m : BM25_e)` | الوصف (بدون HyDE) | `dev` `hit@1` | `dev` `hit@5` | `dev` `hit@10` | `dev` `recall@50` | `dev` `MRR` | `golden` `hit@1` | `golden` `hit@5` | `golden` `hit@10` | `golden` `recall@50` | `golden` `MRR` |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `1 : 0 : 0 : 0` | `Dense_matn` فقط | 43.3% | 71.9% | 80.8% | 93.8% | 0.556 | 70.4% | 88.9% | 92.6% | 92.6% | 0.790 |
| 2 | `0 : 1 : 0 : 0` | `Dense_exp` فقط | 24.6% | 50.0% | 62.1% | 78.6% | 0.351 | 40.7% | 92.6% | 96.3% | 96.3% | 0.615 |
| 3 | `0 : 0 : 1 : 0` | `BM25_matn` فقط | 17.9% | 28.6% | 36.6% | 50.9% | 0.228 | 33.3% | 63.0% | 66.7% | 85.2% | 0.464 |
| 4 | `0 : 0 : 0 : 1` | `BM25_exp` فقط | 12.5% | 25.9% | 33.5% | 50.0% | 0.186 | 33.3% | 70.4% | 70.4% | 88.9% | 0.486 |
| 5 | `0 : 0 : 1 : 1` | `BM25_matn + BM25_exp (1:1)` | 15.2% | 33.0% | 44.6% | 64.3% | 0.231 | 44.4% | 70.4% | 77.8% | 92.6% | 0.552 |
| 6 | `1 : 0 : 1 : 0` | `Dense_matn + BM25_matn (1:1)` | 28.6% | 57.6% | 73.7% | 92.4% | 0.409 | 51.9% | 85.2% | 92.6% | 96.3% | 0.664 |
| 7 | `2 : 0 : 1 : 0` | `Dense_matn + BM25_matn (2:1)` | 31.2% | 61.6% | 79.9% | 94.6% | 0.449 | 55.6% | 88.9% | 92.6% | 96.3% | 0.692 |
| 8 | `3 : 0 : 1 : 0` | `Dense_matn + BM25_matn (3:1)` | 33.5% | 67.0% | 81.2% | 94.6% | 0.478 | 55.6% | 88.9% | 92.6% | 92.6% | 0.698 |
| 9 | `8 : 0 : 1 : 0` | `Dense_matn + BM25_matn (8:1)` | 42.4% | 71.4% | 80.8% | 93.8% | 0.546 | 77.8% | 85.2% | 92.6% | 92.6% | 0.826 |
| 10 | `1 : 1 : 0 : 0` | `Dense_matn + Dense_exp (1:1)` | 33.9% | 60.3% | 77.2% | 94.2% | 0.468 | 66.7% | 88.9% | 88.9% | 100.0% | 0.772 |
| 11 | `2 : 1 : 0 : 0` | `Dense_matn + Dense_exp (2:1)` | 35.7% | 65.2% | 79.9% | 93.8% | 0.489 | 66.7% | 88.9% | 88.9% | 100.0% | 0.770 |
| 12 | `1 : 0 : 0 : 1` | `Dense_matn + BM25_exp (1:1)` | 26.8% | 55.4% | 76.8% | 93.3% | 0.398 | 51.9% | 85.2% | 92.6% | 100.0% | 0.659 |
| 13 | `2 : 0 : 0 : 1` | `Dense_matn + BM25_exp (2:1)` | 29.0% | 60.7% | 80.8% | 93.8% | 0.436 | 66.7% | 85.2% | 92.6% | 100.0% | 0.752 |
| 14 | `3 : 0 : 0 : 1` | `Dense_matn + BM25_exp (3:1)` | 31.7% | 66.5% | 81.2% | 93.8% | 0.469 | 66.7% | 85.2% | 92.6% | 92.6% | 0.761 |
| 15 | `2 : 0 : 1 : 1` | `Dense_m + BM25_m + BM25_e (2:1:1)` | 29.9% | 59.8% | 80.4% | 95.1% | 0.438 | 55.6% | 88.9% | 92.6% | 100.0% | 0.697 |
| 16 | `3 : 0 : 1 : 1` | `Dense_m + BM25_m + BM25_e (3:1:1)` | 34.4% | 65.6% | 81.7% | 95.1% | 0.479 | 55.6% | 88.9% | 92.6% | 100.0% | 0.706 |
| 17 | `1 : 1 : 1 : 1` | أوزان متساوية (`Equal 4-way RRF`) | 29.0% | 62.5% | 75.9% | 93.8% | 0.432 | 51.9% | 92.6% | 92.6% | 100.0% | 0.674 |
| 18 | `2 : 1 : 1 : 1` | رباعي الحقول (`2:1:1:1`) | 31.7% | 66.5% | 78.1% | 95.1% | 0.463 | 51.9% | 92.6% | 92.6% | 100.0% | 0.686 |
| 19 | `3 : 1 : 1 : 1` | رباعي الحقول (`3:1:1:1`) | 34.4% | 67.0% | 80.8% | 94.2% | 0.486 | 59.3% | 92.6% | 92.6% | 100.0% | 0.728 |
| 20 | `4 : 1 : 1 : 1` | رباعي الحقول (`4:1:1:1`) | 37.5% | 68.3% | 82.1% | 94.2% | 0.514 | 66.7% | 92.6% | 92.6% | 100.0% | 0.779 |
| 21 | `4 : 2 : 1 : 1` | رباعي الحقول (`4:2:1:1`) | 35.7% | 66.5% | 80.4% | 94.2% | 0.494 | 66.7% | 92.6% | 92.6% | 100.0% | 0.774 |
| 22 | `6 : 2 : 1 : 1` | رباعي الحقول (`6:2:1:1`) | 36.2% | 69.2% | 82.1% | 93.8% | 0.508 | 70.4% | 92.6% | 92.6% | 92.6% | 0.802 |
| 23 | `8 : 2 : 1 : 1` | رباعي الحقول (`8:2:1:1`، بدون HyDE) | 36.2% | 70.1% | 82.6% | 93.8% | 0.511 | 70.4% | 92.6% | 92.6% | 92.6% | 0.806 |
| 24 | `10 : 2 : 1 : 1` | رباعي الحقول (`10:2:1:1`، بدون HyDE) | 38.4% | 70.5% | 82.1% | 93.8% | 0.525 | 70.4% | 88.9% | 92.6% | 92.6% | 0.801 |

### 5) تقييم الإجابات والاستشهادات (`answer_eval`) على `golden.jsonl` (`30` سؤالًا = `27` قابلًا للإجابة + `3` أسئلة رفض، عند `k = 5`)

شُغّل `src/answer_eval.py` (عبر `src/experiment_e5_final_pipeline.py`) على المجموعة اليدوية `golden.jsonl` (`n = 30` سؤالًا: `27` سؤال متن قابلًا للإجابة و`3` أسئلة رفض خارج نطاق صحيح مسلم، مع تمرير أعلى `k = 5` أحاديث مسترجعة للمولّد):
- **3 تشغيلات مستقلة** لخط الاسترجاع القديم (`Hybrid + mmarco-mMiniLMv2-L12-H384-v1`) مع المولّد `gemini-2.5-pro` (`90` نداء Pro).
- **3 تشغيلات مستقلة** لخط الاسترجاع الجديد (`Upgraded E5`) مع المولّد `gemini-2.5-pro` (`90` نداء Pro).
- **3 تشغيلات مستقلة** لخط الاسترجاع الجديد (`Upgraded E5`) مع المولّد **`gemini-4-argon`** (`90` نداء Pro) ومع **`gemini-4-hydrogen`** (`90` نداء Pro)، بالإضافة إلى تشغيل مرجعي واحد مع `gemini-3.1-pro-preview` (`30` نداء Pro).
- **النماذج المتاحة من فئة Pro في Vertex AI بالمشروع (`generate-504115`، `location="global"`، بتاريخ 2026-11-14):** `gemini-2.5-pro`، `gemini-3.1-pro-preview`، `gemini-4-argon`، `gemini-4-hydrogen`، `gemini-4-carbon` *(بينما أعادت `gemini-3-pro` و`gemini-3-pro-preview` و`gemini-3.1-pro` و`gemini-3.5-pro` و`gemini-3.5-pro-preview` و`gemini-3.8-pro` و`gemini-4-pro` و`gemini-4-helium` و`gemini-4-neon` رمز `404`)*.

#### أ) مقارنة خط الاسترجاع القديم والجديد عبر 3 تشغيلات بـ `gemini-2.5-pro` (المتوسط `Mean` والمدى `Min–Max`)

| المقياس (المصدر: `golden.jsonl`, `k = 5`) | المقام | **القديم (`Hybrid + mmarco` + `gemini-2.5-pro`) — التشغيلات 1/2/3** | **القديم — المتوسط (`Mean`) والمدى (`Min–Max`)** | **الجديد (`Upgraded E5` + `gemini-2.5-pro`) — التشغيلات 1/2/3** | **الجديد — المتوسط (`Mean`) والمدى (`Min–Max`)** |
|---|---:|---|---|---|---|
| **وجود الحديث المرجعي في السياق (`Gold in top-5 context`)** | `27` | `22/27` · `22/27` · `22/27` | **81.5%** (`81.5%–81.5%`) | `27/27` · `27/27` · `27/27` | **100.0%** (`100.0%–100.0%`) |
| **الاستشهاد الصحيح بالحديث المرجعي (`Correct citation`)** | `27` | `22/27` · `22/27` · `22/27` | **81.5%** (`81.5%–81.5%`، المقرَّب `81%`) | `26/27` · `25/27` · `27/27` | **96.3%** (`92.6%–100.0%`، المقرَّب **`96%`**) |
| **محاولات استشهاد بمعرّف خارج السياق (`Invalid citation attempts`)** | `30` | `0/30` · `0/30` · `0/30` | **0.0%** (`0.0%–0.0%`، **`0%`**) | `0/30` · `0/30` · `0/30` | **0.0%** (`0.0%–0.0%`، **`0%`**) |
| **إجابات بلا استشهاد قبل الإلحاق (`Missing citation attempts`)** | `30` | `0/30` · `0/30` · `0/30` | **0.0%** (`0.0%–0.0%`، **`0%`**) | `0/30` · `0/30` · `0/30` | **0.0%** (`0.0%–0.0%`، **`0%`**) |
| **استشهاد بحديث غير مرجعي من السياق (`Wrong in-context citation`)** | `30` | `3/30` · `2/30` · `2/30` | **7.8%** (`6.7%–10.0%`، المقرَّب **`8%`**) | `2/30` · `3/30` · `1/30` | **6.7%** (`3.3%–10.0%`، المقرَّب **`7%`**) |
| **رفض خاطئ والحديث في السياق (`False refusals`)** | `22` / `27` | `0/22` · `0/22` · `0/22` | **0.0%** (`0.0%–0.0%`، **`0%`**) | `0/27` · `0/27` · `0/27` | **0.0%** (`0.0%–0.0%`، **`0%`**) |
| **رفض صحيح لأسئلة خارج المدونة (`Correct refusals`)** | `3` | `3/3` · `3/3` · `3/3` | **100.0%** (`100.0%–100.0%`، **`3/3`**) | `2/3` · `2/3` · `2/3` | **66.7%** (`66.7%–66.7%`، **`2/3`**) |

*(المرجع القياسي في §21 قبل الدمج عبر تشغيل منفرد على `golden.jsonl`: خط الأساس `Hybrid (RRF)` حقق `63%` استشهاد صحيح [`17/27`]، `0%` محاولات خارج السياق [`0/30`]، `0%` بلا استشهاد [`0/30`]، `23%` استشهاد غير مرجعي من داخل السياق [`7/30`]، `0%` رفض خاطئ [`0/20`]، `3/3` رفض صحيح؛ وخط الأساس `Hybrid + rerank` حقق `81%` [`22/27`]، `0%` [`0/30`]، `0%` [`0/30`]، `10%` [`3/30`]، `0%` [`0/22`]، `3/3`.)*

#### ب) مقارنة مولّدات فئة Pro فوق خط الاسترجاع الجديد (`Upgraded E5`, `k = 5` — متوسط `Mean` والمدى `Min–Max`)

| المقياس (المصدر: `golden.jsonl`, `k = 5`) | المقام | **`gemini-4-argon`** *(الافتراضي الجديد، 3 تشغيلات)* | **`gemini-2.5-pro`** *(الافتراضي السابق، 3 تشغيلات)* | **`gemini-4-hydrogen`** *(3 تشغيلات\*)* | **`gemini-3.1-pro-preview`** *(تشغيل 1)* |
|---|---:|---|---|---|---|
| **وجود الحديث المرجعي في السياق (`Gold in top-5 context`)** | `27` | **100.0%** (`27/27 · 27/27 · 27/27`) | **100.0%** (`27/27 · 27/27 · 27/27`) | **100.0%** (`27/27 · 27/27 · 27/27`) | **100.0%** (`27/27`) |
| **الاستشهاد الصحيح بالحديث المرجعي (`Correct citation`)** | `27` | **100.0%** (`27/27 · 27/27 · 27/27`، مدى `100.0%–100.0%`، المقرَّب **`100%`**) | **96.3%** (`26/27 · 25/27 · 27/27`، مدى `92.6%–100.0%`، المقرَّب `96%`) | **84.0%** (`23/27 · 22/27 · 23/27`، مدى `81.5%–85.2%`، المقرَّب `84%`) | **88.9%** (`24/27`) |
| **محاولات استشهاد بمعرّف خارج السياق (`Invalid citation attempts`)** | `30` | **0.0%** (`0/30 · 0/30 · 0/30`، **`0%`**) | **0.0%** (`0/30`) | **0.0%** (`0/30 · 0/30 · 0/30`، `0%`) | **0.0%** (`0/30`) |
| **إجابات بلا استشهاد قبل الإلحاق (`Missing citation attempts`)** | `30` | **0.0%** (`0/30 · 0/30 · 0/30`، **`0%`**) | **0.0%** (`0/30`) | **0.0%** (`0/30 · 0/30 · 0/30`، `0%`) | **0.0%** (`0/30`) |
| **استشهاد بحديث غير مرجعي من السياق (`Wrong in-context citation`)** | `30` | **1.1%** (`1/30 · 0/30 · 0/30`، مدى `0.0%–3.3%`، المقرَّب **`1%`**) | **6.7%** (`2/30 · 3/30 · 1/30`، مدى `3.3%–10.0%`، المقرَّب `7%`) | **13.3%** (`5/30 · 4/30 · 3/30`، مدى `10.0%–16.7%`) | **13.3%** (`4/30`) |
| **رفض خاطئ والحديث في السياق (`False refusals`)** | `27` | **0.0%** (`0/27 · 0/27 · 0/27`، **`0%`**) | **0.0%** (`0/27`) | **2.5%** (`0/27 · 1/27 · 1/27`، مدى `0.0%–3.7%`) | **0.0%** (`0/27`) |
| **رفض صحيح لأسئلة خارج المدونة (`Correct refusals`)** | `3` | **88.9%** (`2/3 · 3/3 · 3/3` = **`8/9`**، مدى `66.7%–100.0%`) | **66.7%** (`2/3 · 2/3 · 2/3` = `6/9`) | **88.9%** (`2/3 · 3/3 · 3/3` = `8/9`، مدى `66.7%–100.0%`) | **66.7%** (`2/3`) |

- **قرار اختيار المولّد الافتراضي (`src/answer.py`):** استوفى **`gemini-4-argon`** (`thinking_level="LOW"`, `location="global"`) شرطي التحوّل مقارنةً بـ `gemini-2.5-pro`: تفوّق في متوسط الاستشهاد الصحيح عبر 3 تشغيلات (`100.0%` مقابل `96.3%`، دون أي خطأ استشهاد على الأسئلة القابلة للإجابة الـ 27 في التشغيلات الثلاثة) وكان أفضل في الرفض الصحيح (`88.9%` = `8/9`: `2/3`, `3/3`, `3/3` مقابل `66.7%` = `2/3` في كل تشغيل لـ `gemini-2.5-pro`)، مع خفض الاستشهاد بحديث غير مرجعي من `6.7%` إلى `1.1%`؛ لذا حُوّل `MODEL = "gemini-4-argon"` افتراضيًا في `src/answer.py` (مع إضافة مهلة HTTP `180,000 ms` وعميل منفصل لكل thread). أمّا `gemini-4-hydrogen` فتراجع إلى `84.0%` مع رفض كاذب (`2.5%`).
- \* **ملاحظة تشغيل `gemini-4-hydrogen`:** التشغيل 1 اكتمل على الاسترجاع المرقّى الخالص (`23/27`، `2/3` رفض). في محاولة التشغيل 2 عند `workers=4` ظهر خطأ `429 RESOURCE_EXHAUSTED` فأُعيد التشغيل بتسلسل `workers=1` (إجمالي P3 بقى ضمن ميزانية `200` نداء Pro)، وخلاله تعرّض أحد استعلامات الرفض الثلاثة غير المخزّنة في الكاش لـ `ReadTimeout` (`> 15,000 ms`) فانتقل مؤقتًا للاحتياطي المحلي `legacy` لأسئلة الرفض في التشغيلين 2–3 بينما اعتمدت الأسئلة القابلة للإجابة الـ 27 كلها على متجهات `Upgraded E5` المخزّنة (`27/27` في السياق).
- سجّل `data/processed/e5_results.json` الرفض الصحيح لسؤال فضل قراءة سورة الكهف يوم الجمعة ولسؤال دعاء الاستخارة في جميع التشغيلات المذكورة أعلاه، وجاء التباين بين `2/3` و`3/3` من سؤال «كم عدد ركعات صلاة التراويح؟».
- **تفعيل المسار الافتراضي المرقّى في التوثيق و`build_pipeline`:** ضُبط `build_pipeline(mode="upgraded")` ليكون المسار الافتراضي في `src/pipeline.py` (مع بقاء خط الأساس المحلي متاحًا عبر `MUSNAD_RETRIEVAL_PIPELINE=legacy` وكخيار احتياطي تلقائي عند تعذر واجهة API)، ووُضع الخط المرقّى عنوانًا رئيسيًا في `README.md` مع الإشارة إلى أن الأوزان مضبوطة على مجموعة التطوير `dev` وتقييم المجموعة المعمّاة لا يزال جاريًا.

### 6) فحص البساطة الإحصائي (McNemar) وزمن الاستجابة الحي والتكلفة (Step P4)

أُجريت قياسات هذه الخطوة عبر `src/experiment_p4_simplicity_and_latency.py` وحُفظت مخرجاتها الخام في `data/processed/p4_results.json`:

1. **فحص البساطة الإحصائي (`McNemar` الثنائي الدقيق، دون نداءات API باستخدام المتجهات المخزّنة):** قورنت الصيغ الثلاث داخل `UpgradedRetriever` (`hyde_alpha = 0.7`، `candidates = 50`، `rrf_k = 60`) على الأسئلة القابلة للإجابة في `dev` (`n = 224`) و`golden` (`n = 27`):

| الإعداد (`Dense_m:Dense_e:BM25_m:BM25_e`) | `dev` `hit@1` | `dev` `hit@5` | `dev` `hit@10` | `dev` `MRR` | `golden` `hit@1` | `golden` `hit@5` | `golden` `hit@10` | `golden` `MRR` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`1:0:0:0`** (`Dense_matn_HyDE` فقط) | 40.62% (`91/224`) | 72.77% (`163/224`) | 83.93% (`188/224`) | 0.5445 | 85.19% (`23/27`) | 100.00% (`27/27`) | 100.00% (`27/27`) | 0.9259 |
| **`8:0:1:0`** (`Dense_matn_HyDE + BM25_matn` دون توسعات) | 39.73% (`89/224`) | 74.55% (`167/224`) | 84.38% (`189/224`) | 0.5454 | 81.48% (`22/27`) | 100.00% (`27/27`) | 100.00% (`27/27`) | 0.9012 |
| **`8:2:1:1`** (`Upgraded E5` كامل) | 37.50% (`84/224`) | 73.66% (`165/224`) | 85.27% (`191/224`) | 0.5285 | 85.19% (`23/27`) | 100.00% (`27/27`) | 100.00% (`27/27`) | 0.9259 |

| الزوج (`A` مقابل `B`) | المجموعة | `hit@1` (`A فقط` مقابل `B فقط`، `p`) | `hit@5` (`A فقط` مقابل `B فقط`، `p`) | `hit@10` (`A فقط` مقابل `B فقط`، `p`) |
| --- | --- | --- | --- | --- |
| `8:2:1:1` مقابل `8:0:1:0` | `dev (n = 224)` | `16` مقابل `21` (`p = 0.5114`) | `8` مقابل `10` (`p = 0.8145`) | `7` مقابل `5` (`p = 0.7744`) |
| `8:0:1:0` مقابل `1:0:0:0` | `dev (n = 224)` | `16` مقابل `18` (`p = 0.8642`) | `8` مقابل `4` (`p = 0.3877`) | `3` مقابل `2` (`p = 1.0000`) |
| `8:2:1:1` مقابل `1:0:0:0` | `dev (n = 224)` | `21` مقابل `28` (`p = 0.3916`) | `9` مقابل `7` (`p = 0.8036`) | `9` مقابل `6` (`p = 0.6072`) |
| `8:2:1:1` مقابل `8:0:1:0` | `golden (n = 27)` | `3` مقابل `2` (`p = 1.0000`) | `0` مقابل `0` (`p = 1.0000`) | `0` مقابل `0` (`p = 1.0000`) |
| `8:0:1:0` مقابل `1:0:0:0` | `golden (n = 27)` | `0` مقابل `1` (`p = 1.0000`) | `0` مقابل `0` (`p = 1.0000`) | `0` مقابل `0` (`p = 1.0000`) |
| `8:2:1:1` مقابل `1:0:0:0` | `golden (n = 27)` | `2` مقابل `2` (`p = 1.0000`) | `0` مقابل `0` (`p = 1.0000`) | `0` مقابل `0` (`p = 1.0000`) |

- **الخلاصة الإحصائية:** لا يوجد فرق ذو دلالة إحصائية بين `1:0:0:0` و`8:0:1:0` و`8:2:1:1` عند أي حد قطع (`p >= 0.3916` على `dev` و`p = 1.0000` على `golden`). يعادل `1:0:0:0` مسار `8:2:1:1` على `golden` (`85.19%` `hit@1` و`100.00%` `hit@5/10` و`MRR = 0.9259`) مع فارق غير دال إحصائيًا في `dev hit@10` (`83.93%` مقابل `85.27%`) وتفوق طفيف في `hit@1` و`MRR`، ما يؤكد أن `1:0:0:0` أو `8:0:1:0` بديل أبسط قابل للتطبيق بعد تقييم المجموعة المعمّاة.

2. **زمن الاستجابة الحي دون كاش (`median` و`p95`) وتكلفة الاستعلام الواحد (`n = 20` سؤالًا قابلًا للإجابة من `golden`، `k = 5`):** مسحنا `query_vec_cache` و`hyde_vec_cache` و`_dense_rank_cache` قبل كل استعلام بعد استعلام إحماء أول (`15,782.4 ms` إجماليًا، `7,185.0 ms` استرجاعًا) لقياس الكمون الفعلي لنداءات `Vertex AI` مع المسار الافتراضي (`Upgraded` + `gemini-4-argon`، دون أي رجوع للاحتياطي `0/20` ودون إعادة توليد `0/20`):

| المرحلة | الوسيط (`median`) | المئين 95 (`p95`) | المتوسط (`mean`) | المدى (`min–max`) |
| --- | ---: | ---: | ---: | ---: |
| تضمين الاستعلام (`gemini-embedding-001`) | `2,619.9 ms` | `2,679.6 ms` | `2,617.1 ms` | `2,506.6–2,687.3 ms` |
| توليد `HyDE` (`gemini-3.8-flash`، `LOW`) | `3,851.6 ms` | `5,130.8 ms` | `4,024.5 ms` | `2,960.5–6,453.6 ms` |
| تضمين `HyDE` (`gemini-embedding-001`) | `973.6 ms` | `1,082.9 ms` | `958.8 ms` | `517.2–1,134.5 ms` |
| الدمج المحلي (`matmul + BM25 + 4-way RRF`) | `177.7 ms` | `199.3 ms` | `179.4 ms` | `158.7–228.2 ms` |
| **إجمالي الاسترجاع المرقّى** | **`7,534.2 ms`** | **`9,160.3 ms`** | **`7,779.8 ms`** | `6,805.6–10,357.3 ms` |
| **التوليد (`gemini-4-argon`، `LOW`)** | **`5,525.8 ms`** | **`20,972.5 ms`** | **`7,873.7 ms`** | `2,883.2–35,216.1 ms` |
| **الزمن الكلي (`End-to-End`)** | **`13,526.1 ms`** (`13.53 s`) | **`28,849.3 ms`** (`28.85 s`) | **`15,653.5 ms`** (`15.65 s`) | `10,742.5–42,842.7 ms` |

| المكوّن | متوسط التوكنز / استعلام | التسعير المعتمد (`/ 1M` توكن) | متوسط التكلفة (`/ استعلام`) | وسيط التكلفة (`/ استعلام`) |
| --- | --- | --- | ---: | ---: |
| `gemini-embedding-001` (استعلام + `HyDE`) | `65.2` إدخال (المدى `45–94`) | `$0.15` إدخال | `$0.000010` | `$0.000010` |
| `gemini-3.8-flash` (`HyDE`) | `82.15` إدخال / `120.75` إخراج (`0` تفكير) | `$0.75` إدخال / `$3.75` إخراج | `$0.000514` | `$0.000512` |
| **إجمالي الاسترجاع (`API`)** | — | — | **`$0.000524`** | **`$0.000522`** |
| `gemini-4-argon` (التوليد، السعر التمهيدي حتى `2026-11-30`) | `1,055.0` إدخال / `191.35` إخراج (`0` تفكير) | `$2.00` إدخال / `$10.00` إخراج | `$0.004023` | `$0.003628` |
| `gemini-4-argon` (التوليد، السعر القياسي بدءًا من `2026-12-01`) | `1,055.0` إدخال / `191.35` إخراج (`0` تفكير) | `$4.00` إدخال / `$20.00` إخراج | `$0.008047` | `$0.007256` |
| **الإجمالي الكلي (السعر التمهيدي / القياسي)** | — | — | **`$0.004548`** / **`$0.008571`** | **`$0.004179`** / **`$0.007816`** |

- يتضمن زمن `query_embed` (`2.62 s` بالوسيط مقابل `0.97 s` لـ `hyde_embed`) كلفة تهيئة عميل `genai.Client` في `_blended_query_vector`؛ ومع إعادة استخدام عميل جاهز ينخفض زمن التضمين الأول بنحو `~1.6 s`، كما يعود ارتفاع `p95` إلى استجابتين طويلتين من `gemini-4-argon` (`35.22 s` و`20.22 s`).
- **مهلة API والرجوع الاحتياطي (`Fallback`):** مضبوط في `UpgradedRetriever` (`API_TIMEOUT_MS = 15,000 ms`) و`build_pipeline(mode="upgraded")`, مع تغطية اختبارية محاكاة دون نداءات شبكة في `tests/test_pipeline.py` (`test_default_pipeline_returns_legacy_results_on_api_failure`: مهلة التضمين، فشل HyDE، فشل HTTP، وحالات عدم توفر المفاتيح/الشبكة).

### 7) تطبيق قاعدة البساطة على المسار الافتراضي (`1:0:0:0` دون BM25 أو توسيع وثائق)

بناءً على نتيجة اختبار `McNemar` في §29.6 (`p >= 0.3916` على `dev` و`p = 1.0000` على `golden`)، حُوّلت أوزان المسار الافتراضي `Upgraded` إلى **`(1.0, 0.0, 0.0, 0.0)`** في `src/pipeline.py` و`src/retrieve.py` (`Dense_matn_HyDE` فقط عبر `gemini-embedding-001` `3072d` بمزج `0.7 * q + 0.3 * HyDE_q`، دون تحميل أو تشغيل BM25 أو حقول توسيع الوثائق في المسار الافتراضي، مع بقاء الرجوع الاحتياطي المحلي `legacy` كما هو). أُعيد قياس المسار عبر `src/evaluate.py` و`src/experiment_e5_simple_default.py` وحُفظت النتائج في `data/processed/e5_simple_default_results.json`:

1. **الاسترجاع على `golden` (`n = 27`) و`dev` (`synthetic_eval.jsonl`, `n = 224`):**

| المجموعة | `hit@1` | `hit@3` | `hit@5` | `hit@10` | `MRR` |
| --- | ---: | ---: | ---: | ---: | ---: |
| `golden (n = 27)` | **85.19%** (`23/27`، المقرَّب **`85%`**) | **100.00%** (`27/27`، **`100%`**) | **100.00%** (`27/27`، **`100%`**) | **100.00%** (`27/27`، **`100%`**) | **0.9259** (**`0.926`**) |
| `dev (synthetic_eval, n = 224)` | **40.62%** (`91/224`، المقرَّب **`41%`**) | **63.84%** (`143/224`، **`64%`**) | **72.77%** (`163/224`، **`73%`**) | **83.93%** (`188/224`، **`84%`**) | **0.5445** (**`0.545`** في `evaluate.py`) |

2. **تقييم الإجابات والاستشهادات (`answer_eval` × 3 تشغيلات، `gemini-4-argon`، `k = 5` على `golden.jsonl`، `30` سؤالًا لكل تشغيل):**

| المقياس | المقام | التشغيلات `1 / 2 / 3` | المتوسط (`Mean`) والمدى | المجموع (`3` تشغيلات) |
| --- | ---: | --- | --- | ---: |
| `Gold in top-5 context` | `27` | `27/27 · 27/27 · 27/27` | **100.0%** (`100.0%–100.0%`) | `81/81` |
| `Correct citation` | `27` | `26/27 · 26/27 · 26/27` | **96.3%** (`96.3%–96.3%`، المقرَّب **`96%`**) | `78/81` |
| `Invalid citation attempts (raw)` | `30` | `0/30 · 0/30 · 0/30` | **0.0%** (**`0%`**) | `0/90` |
| `Missing citation attempts (raw)` | `30` | `0/30 · 0/30 · 0/30` | **0.0%** (**`0%`**) | `0/90` |
| `Non-gold citation from context` | `30` | `1/30 · 1/30 · 1/30` | **3.3%** (`3.3%–3.3%`) | `3/90` |
| `False refusals` | `27` | `1/27 · 1/27 · 1/27` | **3.7%** (`3.7%–3.7%`، المقرَّب **`4%`**) | `3/81` |
| `Correct refusals` | `3` | `2/3 · 2/3 · 2/3` | **66.7%** (`66.7%–66.7%`) | **`6/9`** |

- ظهرت حالة `False refusals` (`1/27`) في التشغيلات الثلاثة على سؤال «هل يجوز صيام يوم الشك؟» (جاء الحديث المرجعي `9679` في المرتبة 2 داخل السياق)، وظهرت حالة `Non-gold citation from context` (`1/30` = `3.3%`) في التشغيلات الثلاثة على سؤال الرفض «كم عدد ركعات صلاة التراويح؟» (عبر الاستشهاد بحديث صلاة الليل من السياق)، مع `0` محاولات استشهاد خارج السياق و`0` حالات إعادة توليد.

3. **زمن الاستجابة الحي دون كاش والتكلفة للمسار المبسَّط الافتراضي `1:0:0:0` (`n = 20` سؤالًا قابلًا للإجابة من `golden`، `k = 5`، بعد استعلام إحماء `15,124.6 ms`):**

| المرحلة | الوسيط (`median`) | المئين 95 (`p95`) | المتوسط (`mean`) | المدى (`min–max`) |
| --- | ---: | ---: | ---: | ---: |
| تضمين الاستعلام (`gemini-embedding-001`) | `2,518.3 ms` | `2,785.1 ms` | `2,551.8 ms` | `2,346.3–2,812.8 ms` |
| توليد `HyDE` (`gemini-3.8-flash`، `LOW`) | `4,000.9 ms` (`4.00 s`) | `5,362.9 ms` | `4,204.7 ms` | `3,049.3–8,246.8 ms` |
| تضمين `HyDE` (`gemini-embedding-001`) | `976.5 ms` | `1,079.0 ms` | `905.8 ms` | `383.2–1,095.0 ms` |
| البحث المحلي الكثيف فقط (`Dense matmul`، دون BM25/RRF) | `101.6 ms` | `120.5 ms` | `104.3 ms` | `87.2–127.2 ms` |
| **إجمالي الاسترجاع (`1:0:0:0`)** | **`7,519.5 ms`** (`7.52 s`) | **`9,231.5 ms`** | **`7,766.6 ms`** | `6,649.6–12,133.2 ms` |
| **التوليد (`gemini-4-argon`، `LOW`)** | **`4,992.2 ms`** | **`7,989.6 ms`** | **`5,277.5 ms`** | `2,160.9–11,446.1 ms` |
| **الزمن الكلي (`End-to-End`)** | **`12,550.5 ms`** (**`12.55 s`**) | **`17,972.8 ms`** (**`17.97 s`**) | **`13,044.0 ms`** | `8,997.3–19,602.7 ms` |

- **متوسط التوكنز والتكلفة لكل استعلام (`n = 20`):** استهلك الاسترجاع `66.25` توكن تضمين (`$0.000010`) + `82.15` إدخال / `123.15` إخراج لـ `HyDE` (`$0.000523`) = **`$0.000533`** (`$0.00053`)، واستهلك التوليد (`gemini-4-argon`) `1,045.4` إدخال / `158.5` إخراج = **`$0.003676`** (`$0.00368`) بالسعر التمهيدي (`$2/$10`) أو **`$0.007352`** بالسعر القياسي (`$4/$20`)؛ ليصبح الإجمالي الكلي **`$0.004209`** (**`$0.0042`**, الوسيط `$0.003818`) بالسعر التمهيدي حتى `2026-11-30`، و**`$0.007885`** (**`$0.0079`**, الوسيط `$0.007094`) بالسعر القياسي بدءًا من `2026-12-01`.
- يهيمن توليد `HyDE` (`4.00 s` بالوسيط من أصل `7.52 s` للاسترجاع) واستدعاءات التضمين المتسلسلة على زمن الاسترجاع بينما لا يستغرق البحث الكثيف المحلي سوى `0.10 s`. *(سُجّلت حادثتا رجوع احتياطي عابرتان `504 DEADLINE_EXCEEDED` خلال الجلب الأولي/القياس وأُعيد القياس الحي بنجاح دون رجوع في جميع العينات الـ 20.)*

---

## 30. المرحلة A — إلحاق السند بالإجابات (`src/answer.py`) واتجاه السلسلة وزمن الإلحاق

**تاريخ القياس:** 2026-11-14 · **الكود:** `src/answer.py`, `src/measure_sanad_attachment.py`, `tests/test_sanad_attachment.py` · **المصدر الخام:** `data/processed/e5_simple_default_results.json` · **المخرج الخام:** `data/processed/sanad_attachment_eval.json`

### 1) دليل اتجاه السند في الجراف وصيغة العرض (`A2`)

ثبت اتجاه السلسلة في الجراف عبر أربعة مصادر متطابقة دون افتراض:
1. **`src/sanad_graph.py` (`get_ordered_chain`):** يقرأ خطوات النقل مرتّبة تصاعديًا بعمود `position` ويبني السلسلة `[steps[0]["from_narrator_id"]] + [row["to_narrator_id"] for row in steps]`, مع نصّ صريح أن `from_narrator_id -> to_narrator_id` يعني من الراوي الأقدم (الشيخ) إلى من سمع منه (التلميذ).
2. **`SANAD_GRAPH_READINESS.md` (§2):** يثبت قياسًا أن الاتجاه هو `source → target = earlier → later = teacher → student` (`Companion → Follower`: `13,898` حافة، `Follower → Successor`: `14,059` حافة، `Successor → 3rd Century AH`: `13,689` حافة؛ مع حفظ `43` حالة رواية كبير عن صغير كما هي)، وأن السلسلة تبدأ في `i1` بالصحابي وتنتهي في آخر موضع بشيخ الإمام مسلم المباشر.
3. **الاختبارات (`tests/test_build_sanad_graph.py` و`tests/test_sanad_context.py`):** يؤكد `test_ordered_chain_returns_narrators_in_recorded_order` و`test_narrators_are_returned_in_recorded_chain_order` أن الموضع `1` هو الصحابي (`Comp.(RA)`) والموضع الأعلى هو التابع المتأخر (`Succ. (Taba' Tabi')`)، وأن `get_predecessors_in_chain` يعيد الشيوخ (`from`) بينما `get_successors_in_chain` يعيد التلاميذ (`to`).
4. **التحقق مقابل نص `data/raw/muslim.json`:** في حديث `8950` مثلًا يعيد الجراف المواضع `1..6` من «أبو هريرة» (`Comp.(RA)`) حتى «زهير بن حرب بن شداد أبو خثيمة» (`3rd Century AH`)، بينما يبدأ متن الإسناد في صحيح مسلم بشيخ مسلم: «وحدثني زهير بن حرب، حدثنا معاذ بن هشام، حدثني أبي، عن يحيى بن أبي كثير، قال حدثنا أبو سلمة بن عبد الرحمن، أن أبا هريرة...».

بناءً على ذلك، يحتفظ حقل `"sanad"` في `answer_with_details` بالترتيب المسجّل `chain_position = 1..k` داخل `isnads`، وعند الطباعة في الـ CLI (`format_sanad_chain`) تُعكس السلسلة لتُطبع من **شيخ مسلم نزولًا إلى الصحابي** مفصولةً بـ `" ← "`، مع إضافة `"(+N طرق أخرى)"` عند وجود أكثر من طريق. أما الأحاديث غير المرتبطة أو التي بلا إسناد مسجّل فتحفظ حالة `sanad_context` كما هي وتُعرض في الـ CLI بعبارة عربية واضحة دون اختلاق أي راوٍ أو سلسلة.

### 2) تغطية الإلحاق وزمن الاستجابة على مخرجات `answer_eval` المحفوظة (`A5` — `0` نداءات LLM جديدة)

قيس الإلحاق فوق المخرجات الخام المحفوظة للتشغيلات الثلاثة الأخيرة للمسار الافتراضي `1:0:0:0` + `gemini-4-argon` على `golden.jsonl` (`data/processed/e5_simple_default_results.json`، `3` تشغيلات × `30` سؤالًا = `90` طلبًا: `81` طلبًا يتضمن استشهادًا صارمًا و`9` حالات رفض، دون أي نداءات LLM جديدة):

| المقياس | النتيجة | المقام / النطاق | ملاحظات |
| --- | ---: | --- | --- |
| **تغطية إلحاق السند (`Attachment coverage`)** | **`95.9%`** (`95.91%`) | **`211 / 220`** استشهادًا | التشغيلات: `69/72` (`95.8%`) · `72/75` (`96.0%`) · `70/73` (`95.9%`) |
| **تغطية المعرّفات الفريدة (`Unique hadith coverage`)** | **`97.4%`** (`97.37%`) | **`74 / 76`** حديثًا فريدًا | الحديثان غير المرتبطين هما `7358` و`7360` (`VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK`) |
| **الوسيط الزمني للإلحاق (`Median latency`)** | **`2.226 ms`** | `n = 81` طلبًا مستشهِدًا (اتصال SQLite واحد/طلب) | التشغيلات: `2.467 ms` · `2.200 ms` · `2.148 ms` |
| **المئين 95 لزمن الإلحاق (`p95 latency`)** | **`3.444 ms`** | المدى `0.983–4.125 ms` | زمن مهمل مقارنةً بـ `12.55 s` للاسترجاع والتوليد |



