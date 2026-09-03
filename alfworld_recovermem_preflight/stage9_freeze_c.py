"""Config C section 1: freeze the configuration and verify non-thinking mode."""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent_c as C

OUTD = os.path.join(L.OUT, "competence_c")
THINK = re.compile(r"<\s*think|</\s*think|<\s*reasoning|^\s*(okay|let me|first,|i need to|the user)",
                   re.IGNORECASE)


def main():
    icl = json.load(open(os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")))
    cfg = C.config_dict(icl)
    h = C.config_hash(cfg)
    cfg["config_sha256"] = h
    L.jdump(cfg, os.path.join(OUTD, "agent_config_c.json"))
    print("CONFIG_C_SHA256 =", h)

    # 3 harmless action-format smoke requests on a Config-B game (no new games consumed)
    frozen = json.load(open(os.path.join(L.OUT, "competence_b", "FROZEN_CONFIG_B_20.json")))
    g = frozen["games"][0]["game_file"]
    env = L.make_env([g])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    intro, history = obs[0], []

    smoke = {"config_sha256": h, "model": C.MODEL, "calls": []}
    for i in range(3):
        out = C.act(icl, intro, history, gs["admissible_commands"])
        raw, cmd = out["raw"], out["command"]
        nums_model = [t for t in raw.replace(":", " ").split() if t.isdigit()]
        nums_exec = [t for t in cmd.split() if t.isdigit()]
        rec = {
            "call": i, "raw": raw, "reasoning_content": out["reasoning_content"],
            "command": cmd, "in_admissible": out["valid"],
            "finish_reason": out["finish_reason"],
            "completion_tokens": out["completion_tokens"],
            "n_lines_in_raw": len([l for l in raw.splitlines() if l.strip()]),
            "hidden_reasoning_markers": bool(THINK.search(raw)) or bool(out["reasoning_content"]),
            "single_parseable_action": len([l for l in raw.splitlines() if l.strip()]) == 1 and bool(cmd),
            "entity_numbers_model": nums_model, "entity_numbers_executed": nums_exec,
            "entity_numbers_preserved": nums_model == nums_exec,
        }
        smoke["calls"].append(rec)
        print(f"  smoke {i}: raw={raw!r} reasoning={out['reasoning_content']!r} "
              f"-> {cmd!r} adm={out['valid']} tok={out['completion_tokens']}")
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        history.append((cmd, obs[0]))
    env.close()

    smoke["no_hidden_reasoning"] = not any(c["hidden_reasoning_markers"] for c in smoke["calls"])
    smoke["exactly_one_parseable_action"] = all(c["single_parseable_action"] for c in smoke["calls"])
    smoke["entity_identity_preserved"] = all(c["entity_numbers_preserved"] for c in smoke["calls"])
    smoke["in_admissible"] = sum(c["in_admissible"] for c in smoke["calls"])
    smoke["external_api_traffic"] = "none - endpoint is http://localhost:8124/v1"
    smoke["NON_THINKING_VERIFIED"] = ("YES" if (smoke["no_hidden_reasoning"]
                                                and smoke["exactly_one_parseable_action"]
                                                and smoke["entity_identity_preserved"]) else "NO")
    L.jdump(smoke, os.path.join(OUTD, "smoke_c.json"))
    print("NON_THINKING_VERIFIED =", smoke["NON_THINKING_VERIFIED"],
          "| in_admissible:", smoke["in_admissible"], "/3")


if __name__ == "__main__":
    main()
