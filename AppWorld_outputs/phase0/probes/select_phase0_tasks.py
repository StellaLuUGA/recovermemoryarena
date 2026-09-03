"""Freeze the Phase-0 15-task DEV viability sample.

Selection uses ONLY task metadata and offline structural analysis. No model has been
run on any DEV task at the time of selection, so no performance signal can enter.

Rule (seed = 13):
  1. DEV = 57 tasks = 19 scenarios x 3 near-duplicate variants. The unit of selection
     is the SCENARIO, so the sample never contains two paraphrases of one problem.
  2. Scenarios are bucketed by required-apps signature (the only native task-type
     metadata AppWorld exposes): spotify, phone+venmo, venmo, file_system,
     file_system+simple_note.
  3. Within each bucket, scenarios are sorted by id and shuffled with Random(13).
  4. Scenarios are drawn ROUND-ROBIN across buckets (buckets ordered by descending
     size, then name), skipping exhausted buckets, until 15 are chosen. This
     stratifies across apps and prevents the largest bucket (spotify) from dominating.
  5. From each chosen scenario one variant is drawn with Random(13).choice over the
     sorted variant ids.

No filtering on difficulty, solution length, or dependency class is applied, so the
sample is not cherry-picked toward tasks that look easy or look memory-hungry.
"""

import json
import os
import random
import sys
from collections import Counter, defaultdict

SEED = 13


def main() -> None:
    audit_path, manifest_path = sys.argv[1], sys.argv[2]
    records = json.load(open(audit_path))

    scenarios: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        scenarios[record["scenario_id"]].append(record)

    buckets: dict[str, list[str]] = defaultdict(list)
    for scenario_id, variants in scenarios.items():
        signature = "+".join(sorted(variants[0]["required_apps"]))
        buckets[signature].append(scenario_id)

    rng = random.Random(SEED)
    ordered_buckets = sorted(buckets, key=lambda s: (-len(buckets[s]), s))
    shuffled: dict[str, list[str]] = {}
    for signature in ordered_buckets:
        members = sorted(buckets[signature])
        rng.shuffle(members)
        shuffled[signature] = members

    chosen_scenarios: list[str] = []
    cursor = {signature: 0 for signature in ordered_buckets}
    while len(chosen_scenarios) < 15:
        progressed = False
        for signature in ordered_buckets:
            if len(chosen_scenarios) >= 15:
                break
            index = cursor[signature]
            if index < len(shuffled[signature]):
                chosen_scenarios.append(shuffled[signature][index])
                cursor[signature] = index + 1
                progressed = True
        if not progressed:
            raise RuntimeError("ran out of scenarios before reaching 15")

    entries = []
    for scenario_id in chosen_scenarios:
        variants = sorted(scenarios[scenario_id], key=lambda r: r["task_id"])
        chosen = rng.choice(variants)
        entries.append(
            {
                "task_id": chosen["task_id"],
                "scenario_id": scenario_id,
                "required_apps": chosen["required_apps"],
                "app_signature": "+".join(sorted(chosen["required_apps"])),
                "difficulty": chosen["difficulty"],
                "num_apps": chosen["num_apps"],
                "num_apis": chosen["num_apis"],
                "num_api_calls_reference": chosen["num_api_calls"],
                "num_solution_code_lines": chosen["num_solution_code_lines"],
                "n_call_sites": chosen.get("n_call_sites"),
                "max_substantive_span": chosen.get("max_substantive_span"),
                "dependency_class": chosen["classification"],
                "instruction": chosen["instruction"],
            }
        )

    entries.sort(key=lambda e: e["task_id"])
    manifest = {
        "name": "phase0_15_tasks",
        "split": "dev",
        "seed": SEED,
        "n_tasks": len(entries),
        "selection_unit": "scenario (one variant per scenario)",
        "stratification": "round-robin over required-apps signature buckets",
        "frozen_before_any_model_run_on_dev": True,
        "task_ids": [e["task_id"] for e in entries],
        "tasks": entries,
        "summary": {
            "by_app_signature": dict(Counter(e["app_signature"] for e in entries)),
            "by_dependency_class": dict(Counter(e["dependency_class"] for e in entries)),
            "by_difficulty": dict(Counter(e["difficulty"] for e in entries)),
        },
    }
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=2)

    print(f"selected {len(entries)} DEV tasks (seed={SEED})")
    for entry in entries:
        print(
            f"  {entry['task_id']:12s} d={entry['difficulty']} "
            f"{entry['app_signature']:24s} {entry['dependency_class']}"
        )
    print("\nsummary:", json.dumps(manifest["summary"], indent=2))


if __name__ == "__main__":
    main()
