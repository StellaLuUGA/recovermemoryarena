"""Phase-0 native viability runner for AppWorld + local Qwen3-32B-AWQ.

Uses the OFFICIAL agent (appworld_agents simplified_react_code_agent), the OFFICIAL
prompt, the OFFICIAL ReAct loop (Agent.solve_tasks -> world.batch_execute), and the
OFFICIAL programmatic evaluator (appworld.evaluator.evaluate_dataset).

Nothing about the agent, prompt, environment, or evaluator is modified. The only
deviation from `appworld run <experiment>` is that the experiment config is read from
a JSON file outside the AppWorld repo (instead of a .jsonnet inside it), so that the
official checkout stays byte-clean. The resulting runner_config is handed to the same
appworld_agents.code.simplified.run.run_experiment entry point the CLI calls.

NO Mem0. NO ReCoverMem. NO recovery. NO paired branching. NO predictor.
"""

import json
import os
import sys
import time
import traceback

os.environ.setdefault("NO_API_KEY", "EMPTY")

from appworld.common.path_store import path_store  # noqa: E402
from appworld.evaluator import evaluate_dataset  # noqa: E402
from appworld.task import load_task_ids  # noqa: E402

OUT_ROOT = "/home/aristella/recoverappworld/AppWorld_outputs"
EXPERIMENT_NAME = os.environ.get(
    "PHASE0_EXPERIMENT", "phase0_native_react_qwen3_32b_awq/dev15"
)
DATASET_OVERRIDE = os.environ.get("PHASE0_DATASET")
CONFIG_PATH = os.path.join(OUT_ROOT, "native_viability", "phase0_config.json")


def install_transport_chat_template_kwargs(chat_template_kwargs: dict) -> None:
    """Attach vLLM chat_template_kwargs to every OpenAI chat request.

    The official qwen3-*-without-reasoning model configs
    (experiments/configs/_generator/models/alibaba.py) express non-thinking mode as
    model_kwargs.extra_body = {"chat_template_kwargs": {"enable_thinking": False}},
    and the official jsonnet templates emit it. However, non_cached_lm_call in this
    checkout does not whitelist `extra_body`, so it cannot be passed through
    model_config. We therefore attach it one layer lower, on the OpenAI client itself.

    This is a TRANSPORT-LEVEL setting (which chat template the server renders). It
    changes no prompt text, no agent logic, no AppWorld code, and no evaluator.
    Without it Qwen3 emits raw <think>...</think> into message content.
    """
    import functools

    import openai.resources.chat.completions as chat_completions

    original_create = chat_completions.Completions.create

    @functools.wraps(original_create)  # keeps inspect.signature() intact for
    def create(self, *args, **kwargs):  # LanguageModel's kwargs validation
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body.setdefault("chat_template_kwargs", chat_template_kwargs)
        kwargs["extra_body"] = extra_body
        return original_create(self, *args, **kwargs)

    chat_completions.Completions.create = create
    print(f"[phase0] transport chat_template_kwargs installed: {chat_template_kwargs}")


def install_vllm_response_normalization() -> None:
    """Normalize vLLM's OpenAI-compatible response shape for the official agent.

    vLLM returns `"reasoning": null` on every non-reasoning chat completion. The
    official helper appworld_agents...language_model.maybe_insert_reasoning_content
    copies that straight across as `reasoning_content = None`, and
    react_code_agent.py:81 then does `output.get("reasoning_content", "").strip()`,
    which raises AttributeError on None. Providers that simply omit the field (OpenAI,
    Anthropic) never hit this.

    The shim below declines to insert a null reasoning_content, so the key is absent
    and `.get(..., "")` yields "" exactly as for the providers the agent was tested
    against. It normalizes a response-schema difference only: no prompt, agent logic,
    AppWorld code, or evaluator behaviour is changed.
    """
    from appworld_agents.code.simplified import language_model as language_model_module

    original = language_model_module.maybe_insert_reasoning_content

    def maybe_insert_reasoning_content(message: dict) -> None:
        if message.get("reasoning", "sentinel") is None:
            message.pop("reasoning", None)
        original(message)
        if message.get("reasoning_content", "sentinel") is None:
            message.pop("reasoning_content", None)

    language_model_module.maybe_insert_reasoning_content = maybe_insert_reasoning_content
    print("[phase0] vLLM response normalization installed (null reasoning_content)")


def load_runner_config() -> dict:
    config = json.load(open(CONFIG_PATH))
    config.pop("_comment", None)
    runner_type = config.pop("type")
    runner_config = config.pop("config")
    prompts = path_store.experiment_prompts
    agent = runner_config["agent"]
    agent["prompt_file_path"] = agent["prompt_file_path"].replace("{PROMPTS}", prompts)
    chat_template_kwargs = agent["model_config"].pop(
        "_transport_chat_template_kwargs", None
    )
    if chat_template_kwargs:
        install_transport_chat_template_kwargs(chat_template_kwargs)
    install_vllm_response_normalization()
    return runner_type, runner_config


def collect_task_record(task_id: str, dataset_name: str, wall_clock: float) -> dict:
    task_dir = os.path.join(path_store.experiment_outputs, EXPERIMENT_NAME, "tasks", task_id)
    record: dict = {"task_id": task_id, "wall_clock_seconds": round(wall_clock, 2)}

    # --- environment interactions (world.execute calls) + observable history ---
    io_path = os.path.join(task_dir, "logs", "environment_io.md")
    execute_calls = 0
    invalid_executions = 0
    if os.path.exists(io_path):
        from appworld import AppWorld

        entries = AppWorld.parse_environment_io_log(file_path=io_path)
        execute_calls = len(entries)
        invalid_executions = sum(
            1 for e in entries if e.get("output", "").startswith("Execution failed")
        )
    record["world_execute_calls"] = execute_calls
    record["invalid_executions"] = invalid_executions

    # --- API calls actually issued to the apps ---
    api_path = os.path.join(task_dir, "logs", "api_calls.jsonl")
    api_calls = 0
    apps_touched: set[str] = set()
    if os.path.exists(api_path):
        for line in open(api_path):
            line = line.strip()
            if not line:
                continue
            api_calls += 1
            try:
                url = json.loads(line).get("url", "")
            except json.JSONDecodeError:
                continue
            parts = [p for p in url.split("/") if p]
            if parts:
                apps_touched.add(parts[0])
    record["api_calls"] = api_calls
    record["apps_touched"] = sorted(apps_touched)

    # --- model turns + observable-history tokens (from the LM call log) ---
    lm_path = os.path.join(task_dir, "logs", "lm_calls.jsonl")
    model_turns = 0
    prompt_tokens_by_turn: list[int] = []
    completion_tokens = 0
    context_limit_hit = False
    if os.path.exists(lm_path):
        for line in open(lm_path):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            model_turns += 1
            usage = (entry.get("output") or {}).get("usage") or {}
            if usage.get("prompt_tokens"):
                prompt_tokens_by_turn.append(int(usage["prompt_tokens"]))
            completion_tokens += int(usage.get("completion_tokens") or 0)
            blob = json.dumps(entry).lower()
            if "contextwindow" in blob or "context_length_exceeded" in blob or "maximum context" in blob:
                context_limit_hit = True
    record["model_turns"] = model_turns
    record["prompt_tokens_by_turn"] = prompt_tokens_by_turn
    record["observable_history_tokens"] = max(prompt_tokens_by_turn) if prompt_tokens_by_turn else 0
    record["completion_tokens_total"] = completion_tokens
    record["context_limit_hit"] = context_limit_hit

    # --- was apis.supervisor.complete_task actually called? ---
    # apis.supervisor.complete_task is routed as POST /supervisor/message
    # (see src/appworld/apps/supervisor/apis.py: @app.post("/message") complete_task).
    completed_called = False
    if os.path.exists(api_path):
        for line in open(api_path):
            if '"/supervisor/message"' in line and '"post"' in line:
                completed_called = True
                break
    record["task_completed_called"] = completed_called
    return record


def main() -> None:
    runner_type, runner_config = load_runner_config()
    if DATASET_OVERRIDE:
        runner_config["dataset"] = DATASET_OVERRIDE
    dataset_name = runner_config["dataset"]
    task_ids = load_task_ids(dataset_name)
    manifest = json.load(
        open(os.path.join(OUT_ROOT, "manifests", "phase0_15_tasks.json"))
    )
    is_frozen_run = not DATASET_OVERRIDE
    if is_frozen_run:
        assert task_ids == manifest["task_ids"], "dataset drifted from the frozen manifest"
    print(f"[phase0] experiment={EXPERIMENT_NAME}")
    print(f"[phase0] dataset={dataset_name} n={len(task_ids)}")
    print(f"[phase0] model={runner_config['agent']['model_config']['name']} "
          f"@ {runner_config['agent']['model_config']['base_url']}")
    sys.stdout.flush()

    import importlib

    run_module = importlib.import_module(f"appworld_agents.code.{runner_type}.run")

    results_path = os.path.join(
        OUT_ROOT,
        "native_viability",
        "native_results.jsonl" if is_frozen_run else f"smoke_results_{dataset_name}.jsonl",
    )
    per_task_timing: dict[str, float] = {}
    infra_errors: dict[str, str] = {}

    # Run one task at a time so a single infra failure cannot abort the sample,
    # and so wall-clock is attributable per task. Ordering is the frozen manifest order.
    from appworld_agents.code.simplified.agent import Agent
    from appworld import AppWorld

    agent_config = json.loads(json.dumps(runner_config["agent"]))
    appworld_config = agent_config.get("appworld_config", {})

    with AppWorld.initializer(
        update_defaults=True, experiment_name=EXPERIMENT_NAME, **appworld_config
    ):
        for index, task_id in enumerate(task_ids, start=1):
            print(f"\n[phase0] === ({index}/{len(task_ids)}) {task_id} ===", flush=True)
            started = time.time()
            try:
                agent = Agent.from_dict(json.loads(json.dumps(agent_config)))
                agent.logger.initialize(
                    experiment_name=EXPERIMENT_NAME,
                    num_tasks=1,
                    num_processes=1,
                    process_index=0,
                )
                agent.solve_task(task_id)
            except Exception as exception:
                infra_errors[task_id] = f"{type(exception).__name__}: {exception}"
                print(f"[phase0] INFRA ERROR on {task_id}: {infra_errors[task_id]}", flush=True)
                traceback.print_exc()
            per_task_timing[task_id] = time.time() - started
            print(f"[phase0] {task_id} finished in {per_task_timing[task_id]:.1f}s", flush=True)

    AppWorld.close_all()

    print("\n[phase0] running official offline evaluator ...", flush=True)
    metrics = evaluate_dataset(
        experiment_name=EXPERIMENT_NAME,
        dataset_name=dataset_name,
        suppress_errors=True,
        include_details=True,
        save_reports=True,
        print_report=True,
    )

    individual = metrics.get("individual", {})
    records = []
    for task_id in task_ids:
        record = collect_task_record(task_id, dataset_name, per_task_timing.get(task_id, 0.0))
        evaluation = individual.get(task_id, {})
        record["evaluator_success"] = bool(evaluation.get("success", False))
        record["evaluator_num_tests"] = evaluation.get("num_tests")
        record["evaluator_num_passed"] = len(evaluation.get("passes", []) or [])
        record["evaluator_num_failed"] = len(evaluation.get("failures", []) or [])
        record["evaluator_failed_requirements"] = [
            f.get("requirement") for f in (evaluation.get("failures", []) or [])
        ]
        record["difficulty"] = evaluation.get("difficulty")
        record["infra_exception"] = infra_errors.get(task_id)
        entry = next((t for t in manifest["tasks"] if t["task_id"] == task_id), None)
        if entry:
            record["required_apps"] = entry["required_apps"]
            record["dependency_class"] = entry["dependency_class"]
        records.append(record)

    with open(results_path, "w") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    metrics_name = (
        "official_metrics.json" if is_frozen_run else f"smoke_metrics_{dataset_name}.json"
    )
    with open(os.path.join(OUT_ROOT, "native_viability", metrics_name), "w") as handle:
        json.dump(metrics, handle, indent=2, default=str)

    successes = sum(1 for r in records if r["evaluator_success"])
    print(f"\n[phase0] DONE. native evaluator successes: {successes}/{len(records)}")
    print(f"[phase0] results: {results_path}")


if __name__ == "__main__":
    main()
