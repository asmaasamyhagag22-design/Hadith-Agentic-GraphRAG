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
الحديث الصح للسياق (20 للهجين، 22 مع إعادة الترتيب).

```canonical-results
# table | row_id | README row label | meta | metric=value[@denominator]
retrieval_golden | dense_matn | Dense only | dataset=golden.jsonl n=27 section=5 | hit@1=41%@27 hit@3=56%@27 hit@5=59%@27 hit@10=63%@27 MRR=0.493
retrieval_golden | bm25_matn | BM25 only | dataset=golden.jsonl n=27 section=5 | hit@1=33%@27 hit@3=59%@27 hit@5=63%@27 hit@10=67%@27 MRR=0.464
retrieval_golden | hybrid_rrf | Hybrid (RRF) | dataset=golden.jsonl n=27 section=5 | hit@1=44%@27 hit@3=67%@27 hit@5=74%@27 hit@10=85%@27 MRR=0.565
retrieval_golden | hybrid_rerank | Hybrid + rerank | dataset=golden.jsonl n=27 section=6 | hit@1=56%@27 hit@3=74%@27 hit@5=81%@27 hit@10=85%@27 MRR=0.665
retrieval_synthetic | dense_matn | Dense only | dataset=synthetic_eval.jsonl n=224 section=5 | hit@1=14%@224 hit@3=20%@224 hit@5=26%@224 hit@10=32%@224 MRR=0.189
retrieval_synthetic | hybrid_rrf | Hybrid (RRF) | dataset=synthetic_eval.jsonl n=224 section=5 | hit@1=18%@224 hit@3=30%@224 hit@5=37%@224 hit@10=44%@224 MRR=0.256
retrieval_synthetic | hybrid_rerank | Hybrid + rerank | dataset=synthetic_eval.jsonl n=224 section=6 | hit@1=27%@224 hit@3=37%@224 hit@5=41%@224 hit@10=44%@224 MRR=0.330
answer_quality | correct_citation | Correct citation | dataset=golden.jsonl section=9 | Hybrid=70%@27 Hybrid_+_rerank=81%@27
answer_quality | invalid_citation | Invalid citation attempts (measured before filtering) | dataset=golden.jsonl section=9 | Hybrid=0%@30 Hybrid_+_rerank=0%@30
answer_quality | wrong_citation | Cited a non-gold hadith from the context | dataset=golden.jsonl section=9 | Hybrid=13%@30 Hybrid_+_rerank=10%@30
answer_quality | false_refusal | False refusals | dataset=golden.jsonl section=9 | Hybrid=0%@20 Hybrid_+_rerank=0%@22
answer_quality | refusal_tests | Correct refusals | dataset=golden.jsonl section=9 | Hybrid=3/3 Hybrid_+_rerank=3/3
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
