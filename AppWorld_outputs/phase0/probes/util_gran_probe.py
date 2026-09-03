"""Utility-granularity probe: can AppWorld's native evaluator be read at an
arbitrary decision boundary (not just episode end), and at what granularity?"""
import json, os, sys
from appworld import AppWorld

TASK = sys.argv[1]
EXP = "phase0_util_gran_probe"
out = {"task_id": TASK}

world = AppWorld(task_id=TASK, experiment_name=EXP)
try:
    def snap(label):
        t = world.evaluate(suppress_errors=True)
        d = t.to_dict() if hasattr(t, "to_dict") else {}
        return {
            "label": label,
            "num_tests": d.get("num_tests"),
            "num_passes": len(d.get("passes") or []),
            "num_failures": len(d.get("failures") or []),
            "success": d.get("success"),
            "interactions": len(world.environment_io),
            "task_completed": world.task_completed(),
        }

    out["supervisor_instruction_len"] = len(world.task.instruction)
    out["snapshots"] = []
    out["snapshots"].append(snap("t0_before_any_action"))

    # take a few real actions, evaluating after each
    steps = [
        "print(apis.api_docs.show_app_descriptions())",
        "print(apis.supervisor.show_account_passwords())",
        "print(apis.supervisor.show_profile())",
    ]
    for i, code in enumerate(steps, 1):
        o = world.execute(code)
        s = snap(f"t{i}_after_step")
        s["step_ok"] = not o.startswith("Execution failed")
        out["snapshots"].append(s)

    out["evaluate_on_live_env"] = "OK"
except Exception as e:
    out["evaluate_on_live_env"] = f"{type(e).__name__}: {e}"
finally:
    try:
        world.close()
    except Exception as e:
        out["close_status"] = f"{type(e).__name__}: {e}"

print(json.dumps(out, indent=2, default=str))
