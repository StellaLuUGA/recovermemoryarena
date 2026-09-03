"""Mechanical save_state/load_state probe for AppWorld (Phase 0, ReCoverMem).

Runs ONE protocol for ONE task per process invocation (freezegun state is
process-global in AppWorld, so isolation is required):

    python state_restore_probe.py <task_id> a|b <out_json>

PROTOCOL A (in-process rollback):
  init -> read-only prefix -> save_state("cp1") -> hash
       -> define a shell variable + run a state-changing action -> hash (must differ)
       -> load_state("cp1") -> hash (must equal checkpoint hash)
       -> replay the same action -> hash/output (must equal post-mutation)

PROTOCOL B (fresh-instance branch = the realistic paired-counterfactual protocol):
  fresh AppWorld(same task, same experiment) -> load_state("cp1") -> hash
       -> replay the action -> hash/output; compared against protocol A's values.
"""

import hashlib
import json
import os
import shutil
import sys
import traceback

from appworld import AppWorld

EXPERIMENT = "phase0_restore_probe"
PRESERVE_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "preserved_checkpoints"
)

PREFIX_CODE = "print(apis.api_docs.show_app_descriptions())"
POST_CP_VAR_CODE = "phase0_probe_var = 4242\nprint(phase0_probe_var)"
MUTATION_CODE = 'apis.supervisor.complete_task(answer="PHASE0_PROBE_SENTINEL")'
DATETIME_CODE = "print(datetime.now().isoformat())"
VAR_CHECK_CODE = (
    "print('phase0_probe_var' in dir(), globals().get('phase0_probe_var', 'ABSENT'))"
)


def hash_dir(directory: str) -> dict:
    entries = {}
    for root, _dirs, files in os.walk(directory):
        for name in sorted(files):
            path = os.path.join(root, name)
            with open(path, "rb") as handle:
                entries[os.path.relpath(path, directory)] = hashlib.sha256(
                    handle.read()
                ).hexdigest()
    blob = json.dumps(entries, sort_keys=True).encode()
    return {"overall": hashlib.sha256(blob).hexdigest(), "files": entries}


def snapshot(world: AppWorld, tag: str) -> dict:
    scratch = os.path.join(world.output_misc_directory, "probe_snapshots", tag)
    world._save_state(scratch)
    dir_hash = hash_dir(scratch)
    try:
        completed = world.task_completed()
    except Exception as exception:
        completed = f"ERROR: {type(exception).__name__}"
    return {
        "db_hash": dir_hash["overall"],
        "db_files": dir_hash["files"],
        "task_completed": completed,
        "num_interactions": world.num_interactions,
        "shell_user_vars": sorted(
            key
            for key in world.shell.user_ns
            if not key.startswith("_")
            and key not in ("In", "Out", "exit", "quit", "open", "get_ipython")
        ),
    }


def safe_close(world: AppWorld) -> str:
    try:
        world.close()
        return "clean"
    except Exception as exception:
        return f"{type(exception).__name__}: {exception}"


def protocol_a(task_id: str) -> dict:
    world = AppWorld(task_id=task_id, experiment_name=EXPERIMENT)
    out: dict = {
        "task_id": task_id,
        "apps": list(world.task.allowed_apps),
        "task_datetime": str(world.task.datetime),
    }
    world.execute(PREFIX_CODE)
    dt_before = world.execute(DATETIME_CODE).strip()

    world.save_state("cp1")
    at_cp = snapshot(world, "at_checkpoint")
    # A fresh AppWorld() rmtree's its output_directory (environment.py:_prepare_directories),
    # so the checkpoint must be preserved outside it for the fresh-instance branch protocol.
    preserved = os.path.join(PRESERVE_ROOT, task_id, "cp1")
    shutil.rmtree(preserved, ignore_errors=True)
    shutil.copytree(os.path.join(world.output_checkpoints_directory, "cp1"), preserved)
    out["preserved_checkpoint_path"] = preserved

    world.execute(POST_CP_VAR_CODE)
    mut_out_1 = world.execute(MUTATION_CODE).strip()
    after_mut_1 = snapshot(world, "after_mutation_1")

    world.load_state("cp1")
    after_restore = snapshot(world, "after_restore")
    dt_after_restore = world.execute(DATETIME_CODE).strip()
    var_after_restore = world.execute(VAR_CHECK_CODE).strip()

    mut_out_2 = world.execute(MUTATION_CODE).strip()
    after_mut_2 = snapshot(world, "after_mutation_2")

    out.update(
        {
            "hashes": {
                "at_checkpoint": at_cp["db_hash"],
                "after_mutation_1": after_mut_1["db_hash"],
                "after_restore": after_restore["db_hash"],
                "after_mutation_2": after_mut_2["db_hash"],
            },
            "task_completed_flags": {
                "at_checkpoint": at_cp["task_completed"],
                "after_mutation_1": after_mut_1["task_completed"],
                "after_restore": after_restore["task_completed"],
            },
            "num_interactions": {
                "at_checkpoint": at_cp["num_interactions"],
                "after_restore": after_restore["num_interactions"],
            },
            "datetime_before_checkpoint": dt_before,
            "datetime_after_restore": dt_after_restore,
            "shell_var_probe_after_restore": var_after_restore,
            "shell_vars_at_checkpoint": at_cp["shell_user_vars"],
            "shell_vars_after_restore": after_restore["shell_user_vars"],
            "mutation_output_1": mut_out_1[:200],
            "mutation_output_2": mut_out_2[:200],
            "checks": {
                "mutation_changed_db": at_cp["db_hash"] != after_mut_1["db_hash"],
                "restore_reproduces_checkpoint_db": at_cp["db_hash"]
                == after_restore["db_hash"],
                "replayed_action_reproduces_db": after_mut_1["db_hash"]
                == after_mut_2["db_hash"],
                "replayed_action_reproduces_output": mut_out_1 == mut_out_2,
                "task_completed_flag_rolled_back": (
                    after_mut_1["task_completed"] is True
                    and after_restore["task_completed"] is False
                ),
                "interaction_counter_rolled_back": (
                    after_restore["num_interactions"] == at_cp["num_interactions"]
                ),
                "frozen_datetime_preserved_after_restore": dt_before == dt_after_restore,
                "python_namespace_rolled_back": "ABSENT" in var_after_restore,
            },
            "unrestored_db_files": sorted(
                name
                for name in set(at_cp["db_files"]) | set(after_restore["db_files"])
                if at_cp["db_files"].get(name) != after_restore["db_files"].get(name)
            ),
        }
    )
    out["close_status"] = safe_close(world)
    return out


def protocol_b(task_id: str, reference: dict) -> dict:
    world = AppWorld(task_id=task_id, experiment_name=EXPERIMENT)
    target = os.path.join(world.output_checkpoints_directory, "cp1")
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(reference["preserved_checkpoint_path"], target)
    world.load_state("cp1")
    at_restore = snapshot(world, "fresh_after_restore")
    dt_b = world.execute(DATETIME_CODE).strip()
    var_b = world.execute(VAR_CHECK_CODE).strip()
    mut_out_b = world.execute(MUTATION_CODE).strip()
    after_mut = snapshot(world, "fresh_after_mutation")
    out = {
        "task_id": task_id,
        "hashes": {
            "after_restore": at_restore["db_hash"],
            "after_mutation": after_mut["db_hash"],
        },
        "datetime_after_restore": dt_b,
        "shell_var_probe_after_restore": var_b,
        "shell_vars_after_restore": at_restore["shell_user_vars"],
        "mutation_output": mut_out_b[:200],
        "checks": {
            "fresh_restore_matches_checkpoint_db": at_restore["db_hash"]
            == reference["hashes"]["at_checkpoint"],
            "fresh_replay_matches_original_mutation_db": after_mut["db_hash"]
            == reference["hashes"]["after_mutation_1"],
            "fresh_replay_matches_original_output": mut_out_b
            == reference["mutation_output_1"],
            "frozen_datetime_correct": dt_b == reference["datetime_before_checkpoint"],
            "python_namespace_is_clean": "ABSENT" in var_b,
        },
    }
    out["close_status"] = safe_close(world)
    return out


def main() -> None:
    task_id, protocol, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        if protocol == "a":
            result = protocol_a(task_id)
        else:
            with open(sys.argv[4]) as handle:
                reference = json.load(handle)
            result = protocol_b(task_id, reference)
    except Exception as exception:
        result = {
            "task_id": task_id,
            "protocol": protocol,
            "fatal_error": f"{type(exception).__name__}: {exception}",
            "traceback": traceback.format_exc()[-2500:],
        }
    with open(out_path, "w") as handle:
        json.dump(result, handle, indent=2)


if __name__ == "__main__":
    main()
