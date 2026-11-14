"""Live 3 text + 3 chain CLI smoke test in default `auto` mode (Step 1f, <= 15 Pro calls)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

import src.answer as ans_mod
from src.config import PROCESSED_DIR
from src.experiment_c5_agent import (
    ApiInstrument,
    PRO_BUDGET_CAP,
    load_ledger,
    save_ledger,
)
from src.pipeline import resolve_agent_mode

SMOKE_CLI_TXT = PROCESSED_DIR / "auto_smoke_cli.txt"
SMOKE_CLI_JSON = PROCESSED_DIR / "auto_smoke_cli.json"

SMOKE_CASES: list[dict[str, str]] = [
    {
        "id": "text_01_fasting",
        "kind": "text",
        "source": "golden#1 (8950)",
        "question": "ما جزاء من صام رمضان إيماناً واحتساباً؟",
    },
    {
        "id": "text_02_fajr",
        "kind": "text",
        "source": "golden#17 (8859)",
        "question": "ما فضل ركعتي الفجر؟",
    },
    {
        "id": "text_03_refusal_taraweeh",
        "kind": "text_refusal",
        "source": "golden#29 (refusal)",
        "question": "كم عدد ركعات صلاة التراويح؟",
    },
    {
        "id": "chain_01_comp",
        "kind": "chain",
        "source": "chain_dev#1 (7296)",
        "question": "من الصحابي الذي روى حديث رقم 7296 عن النبي صلى الله عليه وسلم؟",
    },
    {
        "id": "chain_02_count",
        "kind": "chain",
        "source": "chain_dev#8 (9000, isnad_count=2)",
        "question": "كم طريقًا ورد بها إسناد الحديث رقم 9000؟",
    },
    {
        "id": "chain_03_topic",
        "kind": "chain",
        "source": "chain_dev#13 / golden#32 (14561)",
        "question": "من هو الصحابي الذي روى حديث «كافل اليتيم أنا وهو كهاتين في الجنة»؟",
    },
]


class _Tee(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase):
        self._streams = streams

    def write(self, s: str) -> int:
        for stream in self._streams:
            stream.write(s)
        return len(s)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def main() -> None:
    os.environ.pop("MUSNAD_AGENT", None)
    mode = resolve_agent_mode()
    if mode != "auto":
        raise SystemExit(f"Expected default MUSNAD_AGENT mode 'auto', got {mode!r}")

    ledger = load_ledger()
    start_pro = int(ledger.get("pro_calls", 0))
    start_flash = int(ledger.get("flash_calls", 0))
    start_embed = int(ledger.get("embed_calls", 0))

    if start_pro + 15 > PRO_BUDGET_CAP:
        raise SystemExit(
            f"Skipping live smoke: {start_pro} + 15 exceeds cap {PRO_BUDGET_CAP}."
        )

    argv: list[str] = []
    for case in SMOKE_CASES:
        argv.extend(["-q", case["question"]])

    captured = io.StringIO()
    tee = _Tee(sys.stdout, captured)

    t0 = time.perf_counter()
    with ApiInstrument(ledger, stage="step1f_auto_cli_smoke") as inst:
        with contextlib.redirect_stdout(tee):
            ans_mod.main(argv)
    elapsed_s = time.perf_counter() - t0

    pro_used = int(inst.ledger["pro_calls"]) - start_pro
    flash_used = int(inst.ledger["flash_calls"]) - start_flash
    embed_used = int(inst.ledger["embed_calls"]) - start_embed

    inst.ledger.setdefault("history", []).append(
        {
            "stage": "step1f_auto_cli_smoke",
            "mode": mode,
            "queries": len(SMOKE_CASES),
            "pro_calls": pro_used,
            "flash_calls": flash_used,
            "embed_calls": embed_used,
            "elapsed_s": round(elapsed_s, 2),
        }
    )
    save_ledger(inst.ledger)

    cli_text = captured.getvalue()
    SMOKE_CLI_TXT.parent.mkdir(parents=True, exist_ok=True)
    SMOKE_CLI_TXT.write_text(cli_text, encoding="utf-8")

    # Split CLI output blocks by the 80-'=' separator emitted per question.
    sep = "=" * 80
    raw_blocks = [b.strip() for b in cli_text.split(sep) if b.strip()]
    summary = {
        "default_agent_mode": mode,
        "cases": SMOKE_CASES,
        "blocks_count": len(raw_blocks),
        "pro_calls_used": pro_used,
        "flash_calls_used": flash_used,
        "embed_calls_used": embed_used,
        "pro_budget_after": f"{inst.ledger['pro_calls']}/{PRO_BUDGET_CAP}",
        "flash_budget_after": f"{inst.ledger['flash_calls']}/{inst.ledger.get('flash_cap', 800)}",
        "elapsed_s": round(elapsed_s, 2),
        "cli_output_path": str(SMOKE_CLI_TXT),
    }
    SMOKE_CLI_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n" + "-" * 72)
    print(
        f"Auto CLI Smoke Done in {elapsed_s:.2f}s | mode={mode} | "
        f"Pro={pro_used} (cap<=15, total={inst.ledger['pro_calls']}/{PRO_BUDGET_CAP}), "
        f"Flash={flash_used} (total={inst.ledger['flash_calls']}/800), "
        f"Embed={embed_used}"
    )
    if pro_used > 15:
        raise SystemExit(f"Smoke test exceeded 15 Pro calls: {pro_used}")


if __name__ == "__main__":
    main()
