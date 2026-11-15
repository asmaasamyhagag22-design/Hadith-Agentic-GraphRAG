"""Environment-driven configuration for the Musnad Streamlit demo."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class ExampleQuestion:
    """Preset button metadata displayed on the main query bar."""

    key: str
    label: str
    category: str
    question: str


DEFAULT_EXAMPLES: tuple[ExampleQuestion, ...] = (
    ExampleQuestion(
        key="text",
        label="سؤال متني: قيام رمضان",
        category="متن الحديث",
        question="ما فضل قيام شهر رمضان إيمانًا واحتسابًا؟",
    ),
    ExampleQuestion(
        key="chain",
        label="سؤال إسنادي: حديث رقم 7294",
        category="سلسلة السند",
        question="من هم رواة حديث رقم 7294 وما عدد أسانيده؟",
    ),
    ExampleQuestion(
        key="refusal",
        label="خارج المصادر: العملات الرقمية",
        category="الامتناع المنضبط",
        question="ما حكم تداول العملات الرقمية المشفرة والبيتكوين؟",
    ),
    ExampleQuestion(
        key="narrator",
        label="سؤال راوٍ طبيعي: الدين النصيحة",
        category="راوي الحديث",
        question="من الصحابي الذي روى حديث الدين النصيحة، وما سلسلة رواته عن الإمام مسلم؟",
    ),
)


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings read from environment variables."""

    app_title: str
    app_subtitle: str
    pipeline_mode: str
    agent_mode: str
    top_k: int
    demo_replay: bool
    cloud_mode: bool
    replay_path: Path
    sanad_db_path: Path
    router_weights_path: Path
    chunks_path: Path
    daily_cap: int
    session_limit: int
    ip_hourly_limit: int
    usage_table: str
    gcp_project: str
    gcp_location: str
    log_level: str


def load_config() -> AppConfig:
    """Build AppConfig from current environment variables."""
    pipeline_mode = _env_str("MUSNAD_PIPELINE_MODE", "upgraded").lower()
    if pipeline_mode not in {"upgraded", "legacy"}:
        pipeline_mode = "upgraded"

    agent_mode = _env_str("MUSNAD_AGENT_MODE", "auto").lower()
    if agent_mode not in {"auto", "on", "off"}:
        agent_mode = "auto"

    cloud_mode = _env_bool("MUSNAD_CLOUD", False)
    if cloud_mode:
        pipeline_mode = "upgraded"

    return AppConfig(
        app_title=_env_str("MUSNAD_APP_TITLE", "مُسنَد — مساعد بحث صحيح مسلم"),
        app_subtitle=_env_str(
            "MUSNAD_APP_SUBTITLE",
            "استرجاع موثَّق للمتون مع تحقيق حتمي لأسانيد الرواة من قاعدة بيانات السند",
        ),
        pipeline_mode=pipeline_mode,
        agent_mode=agent_mode,
        top_k=max(1, _env_int("MUSNAD_TOP_K", 5)),
        demo_replay=_env_bool("MUSNAD_DEMO_REPLAY", False),
        cloud_mode=cloud_mode,
        replay_path=Path(
            _env_str(
                "MUSNAD_REPLAY_PATH",
                str(PROJECT_ROOT / "data" / "demo" / "recorded_runs.json"),
            )
        ),
        sanad_db_path=Path(
            _env_str(
                "MUSNAD_SANAD_DB_PATH",
                str(PROJECT_ROOT / "data" / "processed" / "sanad_graph.sqlite"),
            )
        ),
        router_weights_path=Path(
            _env_str(
                "MUSNAD_ROUTER_WEIGHTS_PATH",
                str(PROJECT_ROOT / "src" / "router_weights.npz"),
            )
        ),
        chunks_path=Path(
            _env_str(
                "MUSNAD_CHUNKS_PATH",
                str(PROJECT_ROOT / "data" / "processed" / "muslim_chunks.json"),
            )
        ),
        daily_cap=max(1, _env_int("MUSNAD_DAILY_CAP", 200)),
        session_limit=max(1, _env_int("MUSNAD_SESSION_LIMIT", 10)),
        ip_hourly_limit=max(1, _env_int("MUSNAD_IP_HOURLY_LIMIT", 20)),
        usage_table=_env_str("MUSNAD_USAGE_TABLE", ""),
        gcp_project=_env_str(
            "GOOGLE_CLOUD_PROJECT",
            _env_str("GCP_PROJECT", ""),
        ),
        gcp_location=_env_str(
            "GOOGLE_CLOUD_LOCATION",
            _env_str("GCP_LOCATION", "global"),
        ),
        log_level=_env_str("MUSNAD_LOG_LEVEL", "INFO").upper(),
    )
