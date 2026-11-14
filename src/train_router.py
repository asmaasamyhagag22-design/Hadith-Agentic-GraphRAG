"""Embed router datasets with gemini-embedding-001 and train/CV Router v3.

Strict Step 1c + 1d separation:
  - Uses ONLY `data/raw/router_train.jsonl` to fit Logistic Regression weights,
    regularization C, training scope, and probability threshold via 5-fold
    stratified cross-validation maximizing balanced accuracy of `v3`
    (`v2 fast-path OR (logreg_prob >= threshold)`).
  - Never reads or scores `data/raw/router_fresh2.jsonl` during training/CV/1d.
  - Saves compact pure-NumPy inference weights to `src/router_weights.npz`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from google import genai
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import GOLDEN_PATH, PROCESSED_DIR, RAW_DIR, SYNTHETIC_EVAL_PATH
from embed_vertex_e1 import embed_batches, l2_norm
from router import classify_intent as classify_v2_intent
from utils import strip_diacritics

ROUTER_TRAIN_PATH = RAW_DIR / "router_train.jsonl"
CHAIN_DEV_PATH = RAW_DIR / "chain_eval_dev.jsonl"
CHAIN_TEST_PATH = RAW_DIR / "chain_eval_test.jsonl"
ROUTER_FRESH_PATH = RAW_DIR / "router_fresh.jsonl"

CACHE_PATH = PROCESSED_DIR / "router_embeddings_gemini001.npz"
WEIGHTS_PATH = PROJECT_ROOT / "src" / "router_weights.npz"
TRAIN_REPORT_PATH = PROCESSED_DIR / "router_v3_train_report.json"
LEDGER_PATH = PROCESSED_DIR / "c5_api_ledger.json"

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_embedding_cache(cache_path: Path = CACHE_PATH) -> dict[str, np.ndarray]:
    if not cache_path.exists():
        return {}
    data = np.load(cache_path, allow_pickle=True)
    return {
        str(q): np.asarray(v, dtype=np.float32)
        for q, v in zip(data["questions"], data["vecs"])
    }


def save_embedding_cache(cache: dict[str, np.ndarray], cache_path: Path = CACHE_PATH) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    questions = np.array(list(cache.keys()), dtype=object)
    vecs = np.stack([cache[q] for q in questions], axis=0).astype(np.float32)
    np.savez_compressed(cache_path, questions=questions, vecs=vecs)


def ensure_embeddings(
    questions: list[str],
    cache_path: Path = CACHE_PATH,
) -> tuple[dict[str, np.ndarray], int]:
    """Embed missing unique questions via gemini-embedding-001 and persist cache."""
    cache = load_embedding_cache(cache_path)
    missing = list(dict.fromkeys(q for q in questions if q not in cache))
    embed_api_calls = 0
    if missing:
        client = genai.Client()
        stripped = [strip_diacritics(q) for q in missing]
        batch_size = 100
        embed_api_calls = (len(stripped) + batch_size - 1) // batch_size
        raw_vecs = embed_batches(
            client,
            EMBED_MODEL,
            stripped,
            "RETRIEVAL_QUERY",
            dim=EMBED_DIM,
            batch_size=batch_size,
        )
        norm_vecs = l2_norm(raw_vecs)
        for q, v in zip(missing, norm_vecs):
            cache[q] = v
        save_embedding_cache(cache, cache_path)
        if LEDGER_PATH.exists():
            ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
            ledger["embed_calls"] = int(ledger.get("embed_calls", 0)) + embed_api_calls
            LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cache, embed_api_calls


def _train_and_select(
    train_rows: list[dict[str, Any]],
    cache: dict[str, np.ndarray],
) -> dict[str, Any]:
    questions = [str(r["question"]) for r in train_rows]
    y = np.array([1 if r["expected_intent"] == "chain" else 0 for r in train_rows], dtype=np.int64)
    v2_pred = np.array([1 if classify_v2_intent(q) == "chain" else 0 for q in questions], dtype=np.int64)
    X = np.stack([cache[q] for q in questions], axis=0).astype(np.float32)

    v2_bal_acc = float(balanced_accuracy_score(y, v2_pred))
    v2_chain_rec = float(v2_pred[y == 1].mean())
    v2_text_spec = float((1 - v2_pred[y == 0]).mean())

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    folds = list(skf.split(X, y))

    best_cfg: dict[str, Any] | None = None
    best_key = (-1.0, -1.0, -1.0)  # (cv_bal_acc, cv_text_spec, -abs(C-1))

    for scope in ("all", "v2_misses_only"):
        for c_val in (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0):
            for cw in (None, "balanced"):
                oof_probs = np.zeros(len(y), dtype=np.float64)
                for tr_idx, va_idx in folds:
                    if scope == "v2_misses_only":
                        mask = v2_pred[tr_idx] == 0
                        fit_idx = tr_idx[mask]
                    else:
                        fit_idx = tr_idx
                    clf = LogisticRegression(
                        C=c_val,
                        class_weight=cw,
                        max_iter=2000,
                        random_state=42,
                    )
                    clf.fit(X[fit_idx], y[fit_idx])
                    oof_probs[va_idx] = clf.predict_proba(X[va_idx])[:, 1]

                for thresh in np.linspace(0.20, 0.80, 61):
                    pred = ((v2_pred == 1) | (oof_probs >= thresh)).astype(np.int64)
                    bal = float(balanced_accuracy_score(y, pred))
                    tpr = float(pred[y == 1].mean())
                    tnr = float((1 - pred[y == 0]).mean())
                    # Primary criterion: 5-fold CV balanced accuracy on router_train.
                    # Tie-break: higher text specificity (protect synthetic), then balanced C=1.
                    key = (round(bal, 6), round(tnr, 6), -abs(c_val - 1.0))
                    if key > best_key:
                        best_key = key
                        best_cfg = {
                            "scope": scope,
                            "C": float(c_val),
                            "class_weight": cw,
                            "threshold": float(round(float(thresh), 4)),
                            "cv_balanced_accuracy": bal,
                            "cv_chain_recall": tpr,
                            "cv_text_specificity": tnr,
                            "cv_accuracy": float((pred == y).mean()),
                        }

    assert best_cfg is not None
    # Fit final model on full router_train using selected config.
    fit_mask = (v2_pred == 0) if best_cfg["scope"] == "v2_misses_only" else np.ones(len(y), dtype=bool)
    final_clf = LogisticRegression(
        C=best_cfg["C"],
        class_weight=best_cfg["class_weight"],
        max_iter=2000,
        random_state=42,
    )
    final_clf.fit(X[fit_mask], y[fit_mask])

    weights = final_clf.coef_[0].astype(np.float32)
    intercept = float(final_clf.intercept_[0])
    train_sha256 = hashlib.sha256(ROUTER_TRAIN_PATH.read_bytes()).hexdigest()

    return {
        "best_cfg": best_cfg,
        "v2_train": {
            "balanced_accuracy": v2_bal_acc,
            "chain_recall": v2_chain_rec,
            "text_specificity": v2_text_spec,
            "accuracy": float((v2_pred == y).mean()),
            "n": len(y),
            "n_chain": int((y == 1).sum()),
            "n_text": int((y == 0).sum()),
        },
        "weights": weights,
        "intercept": intercept,
        "train_sha256": train_sha256,
    }


def _score_v3(
    questions: list[str],
    cache: dict[str, np.ndarray],
    weights: np.ndarray,
    intercept: float,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    v2_pred = np.array([1 if classify_v2_intent(q) == "chain" else 0 for q in questions], dtype=np.int64)
    X = np.stack([cache[q] for q in questions], axis=0).astype(np.float32)
    logits = X @ weights.astype(np.float32) + float(intercept)
    probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -50.0, 50.0)))
    v3_pred = ((v2_pred == 1) | (probs >= threshold)).astype(np.int64)
    return v2_pred, v3_pred


def main() -> None:
    train_rows = _load_jsonl(ROUTER_TRAIN_PATH)
    fresh_rows = _load_jsonl(ROUTER_FRESH_PATH)
    golden_rows = _load_jsonl(GOLDEN_PATH)
    chain_test_rows = _load_jsonl(CHAIN_TEST_PATH)

    # Pre-cache train + seen-design (router_fresh) + non-fresh2 eval sets.
    # Notice: router_fresh2.jsonl is intentionally NOT touched here before Step 1d decision.
    questions_to_embed = (
        [str(r["question"]) for r in train_rows]
        + [str(r["question"]) for r in fresh_rows]
        + [str(r["question"]) for r in golden_rows]
        + [str(r["question"]) for r in chain_test_rows]
    )
    cache, embed_calls = ensure_embeddings(questions_to_embed)

    trained = _train_and_select(train_rows, cache)
    cfg = trained["best_cfg"]
    weights = trained["weights"]
    intercept = trained["intercept"]

    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        WEIGHTS_PATH,
        weights=weights,
        intercept=np.array([intercept], dtype=np.float64),
        threshold=np.array([cfg["threshold"]], dtype=np.float64),
        metadata=np.array([json.dumps({
            "train_sha256": trained["train_sha256"],
            "scope": cfg["scope"],
            "C": cfg["C"],
            "class_weight": cfg["class_weight"],
            "cv_balanced_accuracy": cfg["cv_balanced_accuracy"],
            "v2_cv_balanced_accuracy": trained["v2_train"]["balanced_accuracy"],
        }, ensure_ascii=False)], dtype=object),
    )

    # Evaluate Step 1d pre-registered decision criterion on router_fresh (seen during design).
    fresh_qs = [str(r["question"]) for r in fresh_rows]
    fresh_v2, fresh_v3 = _score_v3(fresh_qs, cache, weights, intercept, cfg["threshold"])
    fresh_recall_v2 = float(fresh_v2.mean())
    fresh_recall_v3 = float(fresh_v3.mean())

    ship_v3 = (
        cfg["cv_balanced_accuracy"] >= trained["v2_train"]["balanced_accuracy"]
        and fresh_recall_v3 >= fresh_recall_v2
    )

    report = {
        "embed_calls_added": embed_calls,
        "train_sha256": trained["train_sha256"],
        "weights_path": str(WEIGHTS_PATH.relative_to(PROJECT_ROOT)),
        "v2_train_cv": trained["v2_train"],
        "v3_train_cv": cfg,
        "router_fresh_seen": {
            "n": len(fresh_qs),
            "v2_tp": int(fresh_v2.sum()),
            "v2_chain_recall": fresh_recall_v2,
            "v3_tp": int(fresh_v3.sum()),
            "v3_chain_recall": fresh_recall_v3,
        },
        "step_1d_decision": {
            "criterion_1_cv_bal_acc": cfg["cv_balanced_accuracy"] >= trained["v2_train"]["balanced_accuracy"],
            "criterion_2_fresh_recall": fresh_recall_v3 >= fresh_recall_v2,
            "chosen_version": "v3" if ship_v3 else "v2",
        },
    }
    TRAIN_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRAIN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Step 1c Training + 5-fold CV (router_train.jsonl ONLY)")
    print("=" * 72)
    print(
        f"v2 on router_train (n={trained['v2_train']['n']}): "
        f"bal_acc={trained['v2_train']['balanced_accuracy']*100:.2f}% "
        f"chain_rec={trained['v2_train']['chain_recall']*100:.2f}% "
        f"text_spec={trained['v2_train']['text_specificity']*100:.2f}%"
    )
    print(
        f"v3 5-fold CV (scope={cfg['scope']}, C={cfg['C']}, cw={cfg['class_weight']}, thresh={cfg['threshold']}): "
        f"bal_acc={cfg['cv_balanced_accuracy']*100:.2f}% "
        f"chain_rec={cfg['cv_chain_recall']*100:.2f}% "
        f"text_spec={cfg['cv_text_specificity']*100:.2f}%"
    )
    print(
        f"router_fresh (seen during design, n=30): "
        f"v2={int(fresh_v2.sum())}/30 ({fresh_recall_v2*100:.2f}%) | "
        f"v3={int(fresh_v3.sum())}/30 ({fresh_recall_v3*100:.2f}%)"
    )
    print(f"Step 1d pre-registered choice: {report['step_1d_decision']['chosen_version']}")
    print(f"Weights saved: {WEIGHTS_PATH} ({WEIGHTS_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
