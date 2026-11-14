"""
حارس ضد انحراف التوثيق.

EXPERIMENTS.md هو مصدر الحقيقة للأرقام. الملف ده بيتأكد إن:

1. كل خانة في جداول نتايج README مطابقة للسجل القانوني
2. كل قيمة في السجل القانوني موجودة في القسم اللي بتدّعيه
3. كل نسبة معاها المقام اللي اتحسبت عليه
4. بصمات مجموعات التقييم لسه مطابقة لللي EXPERIMENTS مسجّله

الإصدار الأول كان بيقارن **مجموعة أرقام**: أي رقم في README
لازم يظهر في أي مكان في EXPERIMENTS. ده كان بيمرّر رقمًا صحيحًا
منسوبًا لمقياس غلط — تبديل نسبتين بين مقياسين كان بيعدّي، وكذلك
تغيير اسم مقياس مع إبقاء رقم صالح، والمقامات ما كانتش بتتفحص
أصلًا. دلوقتي المقارنة على (جدول، صف، مقياس) مش على الرقم لوحده.

السجل القانوني كتلة واحدة جوّه EXPERIMENTS نفسه، مش ملف تاني،
عشان ما يبقاش فيه مصدرين للحقيقة؛ والفحص التاني بيربط الكتلة
بالنثر اللي حواليها.

البصمة بتتحسب على نص canonical: CRLF بيتحوّل لـ LF قبل
SHA-256. من غير الخطوة دي نفس الـ commit بيدي بصمة مختلفة
على ويندوز وعلى لينكس، فالبوابة كانت بتفشل من غير ما تتغير
أي بيانات. مفيش أي تطبيع تاني.
"""

import sys
import re
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import BASE_DIR, GOLDEN_PATH, SYNTHETIC_EVAL_PATH, MUSLIM_JSON_PATH

README = BASE_DIR / "README.md"
EXPERIMENTS = BASE_DIR / "EXPERIMENTS.md"

TRACKED_FILES = (GOLDEN_PATH, SYNTHETIC_EVAL_PATH, MUSLIM_JSON_PATH)

HASH_PREFIX = 16

# خلية البصمة في جدول «نسخة القياس» — بالضبط HASH_PREFIX رقم
# ست عشري بين علامتي `. البصمات الكاملة (64) في تجارب تانية
# مش بتطابق، وده مقصود: كل ملف بيتقارن بالخلية بتاعته هو.
_HASH_CELL = re.compile(r"`([0-9a-f]{%d})`" % HASH_PREFIX)

_CANONICAL_BLOCK = re.compile(r"```canonical-results\n(.*?)```", re.DOTALL)

# table | row_id | readme_label | meta | metric=value[@denominator] ...
# The denominator marker is "@" rather than "/", so a literal ratio such
# as 3/3 stays a single value instead of being split into value and base.
_RECORD = re.compile(r"^([\w.]+)\s*\|\s*([\w.]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(.+)$")

# Each README results table, sliced by the markers around it.
README_TABLES = {
    "retrieval_golden": (
        "**Retrieval, hand-verified set",
        "**Retrieval, development set",
    ),
    "retrieval_synthetic": (
        "**Retrieval, development set",
        "**Answer quality",
    ),
    "answer_quality": (
        "**Answer quality",
        "**Chain questions, frozen test set",
    ),
    "chain_eval_test": (
        "**Chain questions, frozen test set",
        "**Intent routing, unseen phrasing and hard negatives",
    ),
    "router_fresh2": (
        "**Intent routing, unseen phrasing and hard negatives",
        "## Engineering decisions",
    ),
}

_PERCENT = re.compile(r"(?<![.\d])\d{1,3}(?:\.\d+)?%")
_DECIMAL = re.compile(r"(?<![.\d])0\.\d{3}\b")


def canonical_bytes(data):
    """نفس النص = نفس البايتات، مهما كان اصطلاح نهاية السطر."""

    return data.replace(b"\r\n", b"\n")


def canonical_hash(path):

    return hashlib.sha256(canonical_bytes(path.read_bytes())).hexdigest()[:HASH_PREFIX]


def recorded_hash(experiments, name):
    """بيجيب البصمة المسجّلة للملف ده تحديدًا، مش أي بصمة في المستند."""

    needle = f"`data/raw/{name}`"

    found = [
        digest
        for line in experiments.splitlines() if needle in line
        for digest in _HASH_CELL.findall(line)
    ]

    if not found:
        return None

    if len(set(found)) > 1:
        raise SystemExit(
            f"{EXPERIMENTS.name} records more than one hash for {name}: "
            f"{sorted(set(found))}"
        )

    return found[0]


# ---------------------------------------------------------------------------
# canonical results registry
# ---------------------------------------------------------------------------

def parse_canonical(experiments):
    """Read the canonical result records out of EXPERIMENTS.

    Returns {(table, row_id): record}; a record carries the README row label,
    its metadata (dataset, n, section) and metric -> (value, denominator).
    """

    match = _CANONICAL_BLOCK.search(experiments)

    if not match:
        raise SystemExit(
            f"{EXPERIMENTS.name} has no ```canonical-results``` block; the "
            f"README results tables cannot be validated without it."
        )

    records = {}

    for line in match.group(1).splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parsed = _RECORD.match(line)

        if not parsed:
            raise SystemExit(f"Unparseable canonical-results line: {line!r}")

        table, row_id, label, meta, metrics = parsed.groups()

        record = {
            "table": table,
            "row_id": row_id,
            "label": label.strip(),
            "meta": dict(item.split("=", 1) for item in meta.split() if "=" in item),
            "metrics": {},
        }

        for item in metrics.split():
            metric, _, rest = item.partition("=")
            value, _, denominator = rest.partition("@")
            record["metrics"][metric] = (value, denominator or None)

        records[(table, row_id)] = record

    return records


def readme_table(readme, table):
    """Slice one README results table out by the headings around it."""

    start_marker, end_marker = README_TABLES[table]
    start = readme.find(start_marker)
    end = readme.find(end_marker, start + 1)

    if start == -1 or end == -1:
        raise SystemExit(
            f"Could not locate the {table!r} table in {README.name} "
            f"(markers {start_marker!r} .. {end_marker!r})."
        )

    rows = []

    for line in readme[start:end].splitlines():
        line = line.strip()

        if not line.startswith("|") or set(line) <= set("|- "):
            continue

        cells = [cell.strip().replace("**", "").strip()
                 for cell in line.strip("|").split("|")]
        rows.append(cells)

    if len(rows) < 2:
        raise SystemExit(f"README table {table!r} has no data rows.")

    return rows[0], rows[1:]


def results_problems(readme, experiments):
    """Every README cell must match the canonical record for its own metric."""

    canonical = parse_canonical(experiments)
    problems = []
    checked = 0

    for table in README_TABLES:
        header, rows = readme_table(readme, table)
        expected = {key[1]: rec for key, rec in canonical.items() if key[0] == table}
        by_label = {rec["label"]: rec for rec in expected.values()}
        seen = set()

        for row in rows:
            label, values = row[0], row[1:]
            record = by_label.get(label)

            if record is None:
                problems.append(
                    f"{table}: README row {label!r} has no canonical record "
                    f"(known rows: {sorted(by_label)})"
                )
                continue

            seen.add(label)

            for column, value in zip(header[1:], values):
                # Column headings carry spaces; the record spells them with
                # underscores so each metric stays one whitespace-free token.
                metric = column.strip().replace(" ", "_")
                declared = record["metrics"].get(metric)

                if declared is None:
                    problems.append(
                        f"{table}/{record['row_id']}: README carries metric "
                        f"{metric!r} with no canonical value"
                    )
                    continue

                checked += 1

                if value != declared[0]:
                    problems.append(
                        f"{table}/{record['row_id']}/{metric}: README says "
                        f"{value!r}, canonical record says {declared[0]!r}"
                    )

        for row_id, record in expected.items():
            if record["label"] not in seen:
                problems.append(
                    f"{table}: canonical row {row_id!r} (label "
                    f"{record['label']!r}) is missing from the README table"
                )

    return problems, checked


def section_problems(experiments):
    """Each canonical value must also appear in the section it claims."""

    canonical = parse_canonical(experiments)
    sections = {}

    for match in re.finditer(r"^## (\d+)\.", experiments, re.MULTILINE):
        start = match.start()
        following = re.search(r"^## \d+\.", experiments[start + 1:], re.MULTILINE)
        end = start + 1 + following.start() if following else len(experiments)
        sections[match.group(1)] = experiments[start:end]

    problems = []
    checked = 0

    for (table, row_id), record in canonical.items():
        section_id = record["meta"].get("section")

        if section_id is None:
            problems.append(f"{table}/{row_id}: canonical record declares no section")
            continue

        section = sections.get(section_id)

        if section is None:
            problems.append(
                f"{table}/{row_id}: declares section {section_id}, which "
                f"{EXPERIMENTS.name} does not contain"
            )
            continue

        for metric, (value, _) in record["metrics"].items():
            checked += 1

            if value not in section:
                problems.append(
                    f"{table}/{row_id}/{metric}: value {value!r} is not in "
                    f"EXPERIMENTS section {section_id}"
                )

    return problems, checked


def denominator_problems(experiments):
    """A rate claim must carry the denominator it was computed over."""

    canonical = parse_canonical(experiments)
    problems = []
    checked = 0

    for (table, row_id), record in canonical.items():
        for metric, (value, denominator) in record["metrics"].items():

            if not value.endswith("%"):
                continue

            checked += 1

            if not denominator:
                problems.append(
                    f"{table}/{row_id}/{metric}: rate {value} carries no "
                    f"denominator; a percentage without one cannot be checked"
                )

    return problems, checked


def prose_problems(readme, experiments):
    """Every percentage or 3-decimal metric in README must appear in EXPERIMENTS."""

    claimed = sorted(set(_PERCENT.findall(readme)) | set(_DECIMAL.findall(readme)))
    recorded = set(_PERCENT.findall(experiments)) | set(_DECIMAL.findall(experiments))
    problems = [
        f"README figure {value!r} does not appear in {EXPERIMENTS.name}"
        for value in claimed
        if value not in recorded
    ]

    return problems, len(claimed)


def _report(problems, checked, ok_message, fail_message):

    if problems:
        print(f"✗ {fail_message}")
        for problem in problems:
            print(f"    {problem}")
        return False

    print(f"✓ {ok_message.format(checked=checked)}")

    return True


def check_results():

    problems, checked = results_problems(
        README.read_text(encoding="utf-8"), EXPERIMENTS.read_text(encoding="utf-8")
    )

    return _report(
        problems, checked,
        "all {checked} README result cells match the canonical record in EXPERIMENTS.md",
        "README results tables disagree with the canonical record:",
    )


def check_canonical_sections():

    problems, checked = section_problems(EXPERIMENTS.read_text(encoding="utf-8"))

    return _report(
        problems, checked,
        "all {checked} canonical values appear in the EXPERIMENTS section they declare",
        "canonical records are not backed by their EXPERIMENTS section:",
    )


def check_denominators():

    problems, checked = denominator_problems(EXPERIMENTS.read_text(encoding="utf-8"))

    return _report(
        problems, checked,
        "all {checked} rate claims declare a denominator",
        "rate claims are missing denominators:",
    )


def check_prose_numbers():

    problems, checked = prose_problems(
        README.read_text(encoding="utf-8"), EXPERIMENTS.read_text(encoding="utf-8")
    )

    return _report(
        problems, checked,
        "all {checked} distinct percentages/decimals in README.md appear in EXPERIMENTS.md",
        "README contains figures not backed by EXPERIMENTS.md:",
    )


def check_hashes():

    experiments = EXPERIMENTS.read_text(encoding="utf-8")

    ok = True

    for path in TRACKED_FILES:

        digest = canonical_hash(path)
        expected = recorded_hash(experiments, path.name)

        if expected is None:
            print(
                f"✗ {path.name} has no recorded hash in {EXPERIMENTS.name} — "
                f"every evaluation dataset must be pinned to the numbers "
                f"measured on it"
            )
            ok = False

        elif digest != expected:
            print(
                f"✗ {path.name} hashes to {digest}, but {EXPERIMENTS.name} "
                f"records {expected} — the dataset changed but the numbers "
                f"were not re-measured"
            )
            ok = False

    if ok:
        print(f"✓ all {len(TRACKED_FILES)} evaluation datasets match the "
              f"hashes recorded in EXPERIMENTS.md")

    return ok


def main():

    print("Documentation consistency\n")

    passed = all([
        check_results(),
        check_canonical_sections(),
        check_denominators(),
        check_prose_numbers(),
        check_hashes(),
    ])

    print()

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
