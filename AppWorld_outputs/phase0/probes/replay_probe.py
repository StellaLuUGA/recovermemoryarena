"""Replay a recorded trajectory into a fresh world, reading the native evaluator
after every step. Measures how many DISTINCT decision boundaries the native
utility can discriminate (utility granularity in practice, not in principle)."""
import json, sys
from appworld import AppWorld

TASK, SRC_EXP = sys.argv[1], sys.argv[2]
world = AppWorld(task_id=TASK, experiment_name="phase0_replay_probe")
out = {"task_id": TASK}
try:
    entries = AppWorld.parse_environment_io_log(
        file_path=f"{sys.argv[3]}"
    )
    out["n_steps"] = len(entries)
    traj = []
    def read():
        t = world.evaluate(suppress_errors=True)
        d = t.to_dict() if hasattr(t, "to_dict") else {}
        return len(d.get("passes") or []), d.get("num_tests"), bool(d.get("success"))
    p, n, s = read()
    traj.append({"step": 0, "passes": p, "num_tests": n, "success": s})
    for i, e in enumerate(entries, 1):
        o = world.execute(e["input"])
        p, n, s = read()
        traj.append({
            "step": i, "passes": p, "num_tests": n, "success": s,
            "exec_ok": not o.startswith("Execution failed"),
        })
    out["trajectory"] = traj
    vals = [t["passes"] for t in traj]
    out["distinct_utility_levels"] = len(set(vals))
    out["n_transitions"] = sum(1 for a, b in zip(vals, vals[1:]) if a != b)
    out["utility_curve"] = vals
    out["final_success"] = traj[-1]["success"]
except Exception as e:
    import traceback; out["error"] = f"{type(e).__name__}: {e}"; out["tb"] = traceback.format_exc()[-800:]
finally:
    try: world.close()
    except Exception as e: out["close_status"] = f"{type(e).__name__}: {e}"
print("###JSON###"); print(json.dumps(out, indent=2, default=str))
