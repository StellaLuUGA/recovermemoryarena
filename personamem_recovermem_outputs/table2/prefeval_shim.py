"""Make PrefEval's ``utils`` package importable again for the Table-2 cost replay.

``LocalLlamaAnswerer.__init__`` imports PrefEval's released ``extract_choice``. Two things
have drifted since the formal run: a PyPI package named ``utils`` now shadows PrefEval's
namespace-package ``utils``, and ``google-genai`` (imported at the top of PrefEval's
``common_utils`` and used nowhere on this path) is no longer installed. Both are fixed here
without touching PrefEval or recovermem: the real PrefEval module is bound under the name
``utils``, and ``google.genai`` is stubbed only far enough for the import statement.

This affects nothing in the PersonaMem-v2 answer path -- ``V2Answerer.answer`` parses with
the released PersonaMem ``extract_final_answer``, not with ``extract_choice``.
"""
from __future__ import annotations

import sys
import types

PREFEVAL_UTILS = "/home/aristella/recoverappworld/PrefEval/utils"


def install() -> dict:
    if "google.genai" not in sys.modules:
        try:
            from google import genai  # noqa: F401
        except Exception:
            g = sys.modules.get("google") or types.ModuleType("google")
            genai = types.ModuleType("google.genai")
            genai.types = types.ModuleType("google.genai.types")
            g.genai = genai
            sys.modules["google"] = g
            sys.modules["google.genai"] = genai
            sys.modules["google.genai.types"] = genai.types
    if not isinstance(sys.modules.get("utils"), types.ModuleType) or \
            PREFEVAL_UTILS not in list(getattr(sys.modules.get("utils"), "__path__", []) or []):
        pkg = types.ModuleType("utils")
        pkg.__path__ = [PREFEVAL_UTILS]
        sys.modules["utils"] = pkg
    from utils.utils_mcq import extract_choice
    return {"extract_choice_module": extract_choice.__module__,
            "extract_choice_file": sys.modules[extract_choice.__module__].__file__}
