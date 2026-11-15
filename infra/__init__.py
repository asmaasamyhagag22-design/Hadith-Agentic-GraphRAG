"""AWS CDK infrastructure-as-code package for the Musnad Streamlit demo."""

from __future__ import annotations

import os
from pathlib import Path
import shutil


def ensure_node_for_jsii() -> None:
    """Ensure a ``node`` binary is on PATH for aws-cdk-lib JSII when running in Python-only envs."""
    if shutil.which("node") is not None:
        return
    try:
        import playwright

        node_dir = Path(playwright.__file__).resolve().parent / "driver"
        if (node_dir / "node").is_file():
            os.environ["PATH"] = f"{node_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            os.environ.setdefault("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")
    except ImportError:
        pass
