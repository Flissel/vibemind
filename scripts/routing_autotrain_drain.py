"""Thin shim — the drain logic moved into the brain image.

2026-05-19 (plan: production-saubere Stack-Sidecar-Architektur): the real
implementation now lives at
`vibemind-os/brain/the_brain/production/autotrain_drain.py` so it ships in
the `vibemind-brain-core:latest` image (Dockerfile `COPY brain/the_brain/
/app/`) and the swarm `brain-autotrain-drain` sidecar can run
`python -m production.autotrain_drain`.

This shim is kept so any host-side caller (the soon-to-be-retired
`Claude-Brain-AutotrainDrain` scheduled task, dev/manual runs) keeps
working. It just delegates. Once the sidecar is verified and the
scheduled task removed, this file can be deleted.

All env vars (ROUTING_AUTOTRAIN_API / ROUTING_AUTOTRAIN_QUEUE /
AUTOTRAIN_PREDICT_TIMEOUT) and CLI flags (--max, --dry-run) are honoured
by the moved module verbatim.
"""

from __future__ import annotations

import sys
from pathlib import Path

# the_brain/ holds the moved module; add it to the path then delegate.
_THE_BRAIN = (
    Path(__file__).resolve().parent.parent
    / "vibemind-os" / "brain" / "the_brain"
)
sys.path.insert(0, str(_THE_BRAIN))

from production.autotrain_drain import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
