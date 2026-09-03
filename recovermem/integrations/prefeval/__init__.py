"""PrefEval integration (classification / MCQ protocol).

Primary setting is frozen in ``results/prefeval/configs/PRIMARY_SETTING.json`` and
mirrored by the constants in :mod:`recovermem.integrations.prefeval.dataset`. The
benchmark is used as data + metric; the PrefEval source tree is never modified and its
AWS-Bedrock driver is not used.
"""

from recovermem.integrations.prefeval.dataset import (
    PREF_FORM,
    INTER_TURNS,
    PrefInstance,
    load_instances,
    group_key_components,
    deterministic_partition,
)

__all__ = [
    "PREF_FORM", "INTER_TURNS", "PrefInstance",
    "load_instances", "group_key_components", "deterministic_partition",
]
