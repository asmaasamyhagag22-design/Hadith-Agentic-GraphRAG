"""Record 10 real end-to-end runs with full traces into data/demo/recorded_runs.json.

Usage:
    uv run python -m src.record_demo_runs
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.state import build_matn_index, enrich_chunks_matn
from src.answer import answer_with_details
from src.pipeline import build_pipeline
from src.retrieve import load_chunk_lookup
from src.sanad_graph import GRAPH_DB_PATH
from src.trace import TraceCollector

OUTPUT_PATH = ROOT / "data" / "demo" / "recorded_runs.json"
LEDGER_PATH = ROOT / "data" / "demo" / "api_budget_ledger.json"

CURATED_DEMO_QUERIES: tuple[dict[str, str], ...] = (
    # 2 text
    {
        "id": "run_01_text_ramadan",
        "category": "text",
        "question": "ما فضل قيام شهر رمضان إيمانًا واحتسابًا؟",
    },
    {
        "id": "run_02_text_rights",
        "category": "text",
        "question": "ما حق المسلم على المسلم في صحيح مسلم؟",
    },
    # 3 chain (2 direct + 1 topic chain)
    {
        "id": "run_03_chain_id_7306",
        "category": "chain",
        "question": "ما أسانيد حديث رقم 7306 ومن الصحابي الذي رواه؟",
    },
    {
        "id": "run_04_chain_membership_7290",
        "category": "chain",
        "question": "هل ورد أنس بن مالك في سند حديث رقم 7290؟",
    },
    {
        "id": "run_05_chain_topic_nasiha",
        "category": "chain_topic",
        "question": "من الصحابي الذي روى حديث الدين النصيحة، وما سلسلة رواته عن الإمام مسلم؟",
    },
    # 1 refusal
    {
        "id": "run_06_refusal_crypto",
        "category": "refusal",
        "question": "ما حكم تداول العملات الرقمية المشفرة والبيتكوين؟",
    },
    # 1 narrator
    {
        "id": "run_07_narrator_7294",
        "category": "narrator",
        "question": "من هم رواة حديث رقم 7294 وما عدد أسانيده؟",
    },
    # 3 choice
    {
        "id": "run_08_choice_cheating",
        "category": "choice_text",
        "question": "ما جزاء من يغش الناس في البيع؟",
    },
    {
        "id": "run_09_choice_orphan",
        "category": "choice_text",
        "question": "ما فضل من كفل يتيمًا كما جاء في صحيح مسلم؟",
    },
    {
        "id": "run_10_choice_hypocrite",
        "category": "choice_text",
        "question": "ما علامات المنافق كما وردت في صحيح مسلم؟",
    },
)


def _update_budget_ledger(pro: int, flash: int, embed: int, note: str) -> None:
    if LEDGER_PATH.is_file():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    else:
        ledger = {"budget_caps": {"pro": 40, "flash": 40}, "used": {"pro": 0, "flash": 0, "embed": 0}, "runs": []}
    ledger["used"]["pro"] += pro
    ledger["used"]["flash"] += flash
    ledger["used"]["embed"] += embed
    ledger["runs"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": note,
            "pro": pro,
            "flash": flash,
            "embed": embed,
        }
    )
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_all(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Run curated queries against the real pipeline and write recorded_runs.json."""
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    chunk_lookup = load_chunk_lookup()
    matn_index = build_matn_index(chunk_lookup)
    pipeline = build_pipeline(mode="upgraded", chunk_lookup=chunk_lookup)

    recorded: list[dict[str, Any]] = []
    total_pro = 0
    total_flash = 0
    total_embed = 0

    for item in CURATED_DEMO_QUERIES:
        trace = TraceCollector()
        details = answer_with_details(
            item["question"],
            pipeline,
            k=5,
            sanad_db_path=GRAPH_DB_PATH,
            trace=trace,
        )
        trace.finish()
        summary = trace.summary()
        if details.get("chunks"):
            details["chunks"] = enrich_chunks_matn(details["chunks"], matn_index)

        counts = summary["call_counts"]
        total_pro += counts["pro_calls"]
        total_flash += counts["flash_calls"]
        total_embed += counts["embed_calls"]

        print(
            f"[{item['id']}] stages={trace.stages()} "
            f"pro={counts['pro_calls']} flash={counts['flash_calls']} "
            f"embed={counts['embed_calls']} ms={summary['total_duration_ms']:.1f}"
        )

        recorded.append(
            {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "result": details,
                "trace": trace.to_dict(),
            }
        )

    payload = {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_mode": "upgraded",
        "api_calls_used": {
            "pro_calls": total_pro,
            "flash_calls": total_flash,
            "embed_calls": total_embed,
        },
        "runs": recorded,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_budget_ledger(total_pro, total_flash, total_embed, "Step 3: 10 recorded demo runs")
    print(f"Saved {len(recorded)} runs to {output_path} (Pro={total_pro}, Flash={total_flash}, Embed={total_embed})")
    return payload


if __name__ == "__main__":
    record_all()
