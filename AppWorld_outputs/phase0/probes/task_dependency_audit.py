"""Offline structural within-task past-observation dependence audit for AppWorld DEV tasks.

Method (deterministic, offline, no model involvement, no execution):

Each task ships a reference `compiled_solution.py`: a flat, self-contained program over
`apis.<app>.<api>(...)` calls. We AST-parse it and build a def-use graph over API CALL
SITES in source order (index 0, 1, 2, ...), with transitive provenance:

  provenance(expr) = min( indices of API calls syntactically inside expr,
                          producers of the names expr reads )

  * an assignment binds its targets to provenance(RHS)
  * a `for` target / comprehension target binds to provenance(iterable)
    -- so `for page_index in range(0, 10)` binds nothing, while
       `for song in song_library` inherits song_library's producing API call
  * an API call at index j reading a name produced at index i < j is a
    dependency EDGE (i -> j) with SPAN j - i

AUTH BOILERPLATE IS EXCLUDED. Every AppWorld task fetches the supervisor profile and
passwords and logs in, so access-token reuse is universal and non-discriminating.
Edges whose producer is an auth API, or whose carrier name is a credential/pagination
name, are dropped before scoring.

Classification (applied in this order):
  TOO SHORT                                n_call_sites <= 3
  LONG-HORIZON PAST-OBSERVATION DEPENDENT  max_substantive_span >= 2  OR
                                           an accumulator fed by >= 2 API calls
                                           feeds the final answer/action
  MULTI-STEP BUT SELF-CONTAINED            n_call_sites > 3, every substantive
                                           API result consumed within 1 call site,
                                           no accumulator
  AMBIGUOUS                                solution unparseable / analysis failed
"""

import ast
import json
import os
import re
import sys
from collections import Counter

from appworld.common.path_store import path_store
from appworld.task import load_task_ids

AUTH_API_NAMES = {"login", "show_profile", "show_account_passwords", "access_token_from"}
EXCLUDED_CARRIER_RE = re.compile(
    r"^(page_index|index|idx|i|j|k|n|offset|limit|token)$"
    r"|access_token|password|credential|supervisor_profile",
    re.I,
)


def api_call_target(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    owner = func.value
    if not (isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name)):
        return None
    if owner.value.id != "apis":
        return None
    return f"{owner.attr}.{func.attr}"


def names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def ordered_nodes(node: ast.AST) -> list[ast.AST]:
    nodes = [n for n in ast.walk(node) if hasattr(n, "lineno")]
    return sorted(nodes, key=lambda n: (n.lineno, n.col_offset))


class Analyzer:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.name_to_producer: dict[str, int] = {}
        self.edges: list[dict] = []
        self.accumulator_sources: dict[str, set[int]] = {}
        self.answer_names: set[str] = set()
        self.registered: set[int] = set()

    # ---- provenance -----------------------------------------------------
    def provenance(self, expr: ast.AST | None) -> int | None:
        if expr is None:
            return None
        candidates: list[int] = []
        for node in ordered_nodes(expr):
            if api_call_target(node) is not None and id(node) in self.call_index_of:
                candidates.append(self.call_index_of[id(node)])
        for name in names_in(expr):
            if name in self.name_to_producer:
                candidates.append(self.name_to_producer[name])
        return min(candidates) if candidates else None

    def bind(self, target: ast.AST, expr: ast.AST | None) -> None:
        producer = self.provenance(expr)
        if producer is None:
            return
        for name in names_in(target):
            if EXCLUDED_CARRIER_RE.search(name):
                continue
            existing = self.name_to_producer.get(name)
            self.name_to_producer[name] = (
                producer if existing is None else min(existing, producer)
            )

    # ---- call registration ---------------------------------------------
    call_index_of: dict[int, int]

    def register(self, node: ast.AST | None) -> list[int]:
        """Register API calls inside `node` in source order; also record read edges."""
        if node is None:
            return []
        indices: list[int] = []
        for sub in ordered_nodes(node):
            target = api_call_target(sub)
            if target is None or id(sub) in self.registered:
                continue
            self.registered.add(id(sub))
            index = len(self.calls)
            self.call_index_of[id(sub)] = index
            app, api = target.split(".", 1)
            self.calls.append({"index": index, "app": app, "api": api})
            read: set[str] = set()
            for argument in list(sub.args) + [kw.value for kw in sub.keywords]:
                read |= names_in(argument)
            for name in read:
                producer = self.name_to_producer.get(name)
                if producer is not None and producer < index:
                    self.edges.append(
                        {
                            "producer": producer,
                            "consumer": index,
                            "span": index - producer,
                            "via": name,
                            "producer_call": f"{self.calls[producer]['app']}."
                            f"{self.calls[producer]['api']}",
                            "consumer_call": target,
                        }
                    )
            indices.append(index)
            # comprehension targets inside this call's arguments
        # bind comprehension targets encountered anywhere in this node
        for sub in ordered_nodes(node):
            if isinstance(sub, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for generator in sub.generators:
                    self.bind(generator.target, generator.iter)
        return indices


def analyse_source(source: str) -> dict:
    tree = ast.parse(source)
    function = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "solution"),
        None,
    )
    if function is None:
        raise ValueError("no solution() function")

    analyzer = Analyzer()
    analyzer.call_index_of = {}

    def note_accumulator(name: str, expr: ast.AST) -> None:
        producer = analyzer.provenance(expr)
        if producer is not None:
            analyzer.accumulator_sources.setdefault(name, set()).add(producer)

    def walk_body(body: list[ast.stmt]) -> None:
        for statement in body:
            if isinstance(statement, ast.For):
                analyzer.register(statement.iter)
                analyzer.bind(statement.target, statement.iter)
                walk_body(statement.body)
                walk_body(statement.orelse)
            elif isinstance(statement, ast.While):
                analyzer.register(statement.test)
                walk_body(statement.body)
                walk_body(statement.orelse)
            elif isinstance(statement, ast.If):
                analyzer.register(statement.test)
                walk_body(statement.body)
                walk_body(statement.orelse)
            elif isinstance(statement, ast.With):
                for item in statement.items:
                    analyzer.register(item.context_expr)
                walk_body(statement.body)
            elif isinstance(statement, ast.Try):
                walk_body(statement.body)
                for handler in statement.handlers:
                    walk_body(handler.body)
                walk_body(statement.orelse)
                walk_body(statement.finalbody)
            elif isinstance(statement, ast.Assign):
                analyzer.register(statement.value)
                for target in statement.targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                        note_accumulator(target.value.id, statement.value)
                    analyzer.bind(target, statement.value)
            elif isinstance(statement, ast.AugAssign):
                analyzer.register(statement.value)
                for name in names_in(statement.target):
                    note_accumulator(name, statement.value)
                analyzer.bind(statement.target, statement.value)
            elif isinstance(statement, ast.Return):
                analyzer.register(statement.value)
                if statement.value is not None:
                    analyzer.answer_names |= names_in(statement.value)
            elif isinstance(statement, ast.Expr):
                value = statement.value
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
                    if value.func.attr in ("append", "extend", "update", "add") and isinstance(
                        value.func.value, ast.Name
                    ):
                        for argument in value.args:
                            note_accumulator(value.func.value.id, argument)
                    if value.func.attr == "complete_task":
                        for keyword in value.keywords:
                            if keyword.arg == "answer":
                                analyzer.answer_names |= names_in(keyword.value)
                analyzer.register(value)
            else:
                analyzer.register(statement)

    walk_body(function.body)

    calls = analyzer.calls
    n_call_sites = len(calls)

    substantive_edges = [
        edge
        for edge in analyzer.edges
        if calls[edge["producer"]]["api"] not in AUTH_API_NAMES
        and not EXCLUDED_CARRIER_RE.search(edge["via"])
    ]
    max_span = max((edge["span"] for edge in substantive_edges), default=0)

    multi_source_accumulators = {
        name: sorted(indices)
        for name, indices in analyzer.accumulator_sources.items()
        if len(indices) >= 2 and not EXCLUDED_CARRIER_RE.search(name)
    }
    answer_producers = sorted(
        {
            analyzer.name_to_producer[name]
            for name in analyzer.answer_names
            if name in analyzer.name_to_producer
        }
    )
    answer_span = (n_call_sites - answer_producers[0]) if answer_producers else 0
    accumulator_feeds_answer = bool(multi_source_accumulators) and (
        bool(analyzer.answer_names & set(multi_source_accumulators)) or answer_span >= 2
    )

    if n_call_sites <= 3:
        label = "TOO SHORT"
    elif max_span >= 2 or accumulator_feeds_answer:
        label = "LONG-HORIZON PAST-OBSERVATION DEPENDENT"
    elif n_call_sites > 3:
        label = "MULTI-STEP BUT SELF-CONTAINED"
    else:
        label = "AMBIGUOUS"

    return {
        "n_call_sites": n_call_sites,
        "n_distinct_apis": len({f"{c['app']}.{c['api']}" for c in calls}),
        "solution_apps": sorted({c["app"] for c in calls}),
        "n_substantive_edges": len(substantive_edges),
        "max_substantive_span": max_span,
        "multi_source_accumulators": multi_source_accumulators,
        "accumulator_feeds_answer": accumulator_feeds_answer,
        "answer_span": answer_span,
        "top_edges": sorted(substantive_edges, key=lambda e: -e["span"])[:6],
        "classification": label,
    }


def main() -> None:
    task_ids = load_task_ids("dev")
    tasks_directory = os.path.join(path_store.data, "tasks")
    records = []
    for task_id in task_ids:
        directory = os.path.join(tasks_directory, task_id)
        specs = json.load(open(os.path.join(directory, "specs.json")))
        gt = os.path.join(directory, "ground_truth")
        metadata = json.load(open(os.path.join(gt, "metadata.json")))
        record = {
            "task_id": task_id,
            "scenario_id": task_id.split("_")[0],
            "instruction": specs["instruction"],
            "required_apps": json.load(open(os.path.join(gt, "required_apps.json"))),
            "difficulty": metadata.get("difficulty"),
            "num_apps": metadata.get("num_apps"),
            "num_apis": metadata.get("num_apis"),
            "num_api_calls": metadata.get("num_api_calls"),
            "num_solution_code_lines": metadata.get("num_solution_code_lines"),
        }
        try:
            record.update(
                analyse_source(open(os.path.join(gt, "compiled_solution.py")).read())
            )
        except Exception as exception:
            record["classification"] = "AMBIGUOUS"
            record["analysis_error"] = f"{type(exception).__name__}: {exception}"
        records.append(record)

    with open(sys.argv[1], "w") as handle:
        json.dump(records, handle, indent=2)

    counts = Counter(r["classification"] for r in records)
    print(f"inspected: {len(records)} DEV tasks")
    for label, count in counts.most_common():
        print(f"  {count:3d}  {label}")


if __name__ == "__main__":
    main()
