import json
import os

folder = "simcse_explicit_pref"

all_json_files = os.listdir(
    f"/data/siyanz-sandbox/clean_code/benchmark_dataset/rag_retrieval/{folder}"
)
total = 0
num_chatgpt = 0
num_claude = 0
for json_file in all_json_files:
    if "json" not in json_file or "msg" in json_file:
        continue
    with open(
        f"/data/siyanz-sandbox/clean_code/benchmark_dataset/rag_retrieval/{folder}/"
        + json_file,
        "r",
    ) as f:
        data = json.load(f)
    print(json_file, len(data))
    for idx, task in enumerate(data):
        total += 1
        data[idx].pop("rating_gpt4o-mini", None)
        data[idx].pop("violation_rating_gpt4o-mini", None)
        data[idx].pop("violation_probability", None)
        data[idx].pop("evaluation", None)
        data[idx].pop("sampled_response", None)
        data[idx].pop("violation_rating", None)
        data[idx].pop("model", None)
        data[idx].pop("rating", None)
    with open(
        f"/data/siyanz-sandbox/clean_code/benchmark_dataset/rag_retrieval/{folder}/"
        + json_file,
        "w",
    ) as outfile:
        json.dump(data, outfile, indent=4)
    # if 'model' not in task.keys():
    #     print(json_file, idx)
    # if "gpt" in task['model']:
    #     num_chatgpt += 1
    # else:
    #     num_claude += 1
print("Total", total)
