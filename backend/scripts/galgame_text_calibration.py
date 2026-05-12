"""Run the offline galgame free-text calibration set.

This script is deterministic and does not call LLM, embedding, or reranker providers.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.domain.galgame_calibration import FREE_TEXT_CALIBRATION_CASES, build_calibration_choices
from app.services.ai_service import ai_service


def main() -> int:
    choices = build_calibration_choices()
    passed = 0
    for case in FREE_TEXT_CALIBRATION_CASES:
        inference = ai_service.classify_galgame_free_text_offline(case["text"], choices)
        actual = inference.inferred_option_key
        ok = actual == case["expected_option_key"]
        passed += int(ok)
        status = "PASS" if ok else "FAIL"
        print(
            f"{status}\t{case['label']}\texpected={case['expected_option_key']}\t"
            f"actual={actual}\tconfidence={inference.confidence:.3f}\tsource={inference.source}"
        )
    total = len(FREE_TEXT_CALIBRATION_CASES)
    print(f"pass_rate={passed / max(total, 1):.3f} ({passed}/{total})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
