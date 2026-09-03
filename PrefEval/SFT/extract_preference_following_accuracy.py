import os
import json
import argparse
import yaml
from tqdm import tqdm
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.common_utils import load_config


def setup_paths(args):
    eval_file = f"{args.dir}/SFT/inference_result_with_{args.ft}/eval_{args.turn}turn_{args.task}.json"
    return eval_file


def load_evaluation_data(eval_file):
    if not os.path.isfile(eval_file):
        raise FileNotFoundError(f"File not found: {eval_file}")
    with open(eval_file, "r") as f:
        return json.load(f)


def analyze_errors(data):
    stats = {
        "acknowledgement": 0,
        "hallucination": 0,
        "violation": 0,
        "error_unhelpful": 0,
        "error_inconsistent": 0,
        "hallucination_of_preference_violation": 0,
        "preference_unaware_violation": 0,
        "preference_adherence_accuracy": 0,
    }

    for idx, entry in tqdm(enumerate(data)):
        if "evaluation_error_analysis" not in entry:
            print("Error: this entry has not been evaluated yet!")
        error_types = entry["evaluation_error_analysis"]
        is_acknowledgement = "yes" in error_types.get("acknow", {}).get("answer", "").lower()
        is_hallucination = is_acknowledgement and "yes" in error_types.get("hallucinate", {}).get("answer", "").lower()
        is_violation = "yes" in error_types.get("violate", {}).get("answer", "").lower()
        is_unhelpful = "no" in error_types.get("helpful", {}).get("answer", "").lower()

        is_inconsistent = is_acknowledgement and not is_hallucination and is_violation and not is_unhelpful
        is_hallucination_of_preference_violation = (
            is_acknowledgement and is_hallucination and is_violation and not is_unhelpful
        )
        is_preference_unaware_violation = not is_acknowledgement and is_violation and not is_unhelpful

        preference_following_accuracy = not any(
            [is_inconsistent, is_hallucination_of_preference_violation, is_preference_unaware_violation, is_unhelpful]
        )

        # Update stats
        stats["acknowledgement"] += is_acknowledgement
        stats["hallucination"] += is_hallucination
        stats["violation"] += is_violation
        stats["error_unhelpful"] += is_unhelpful
        stats["error_inconsistent"] += is_inconsistent
        stats["hallucination_of_preference_violation"] += is_hallucination_of_preference_violation
        stats["preference_unaware_violation"] += is_preference_unaware_violation
        stats["preference_adherence_accuracy"] += preference_following_accuracy

    return stats, len(data)


def print_evaluation_results(stats, total_data, args):
    print("\n--- Evaluation Setup ---")
    print(f"Model file: {args.ft}")
    print(f"Inter-Turn Tested: {args.turn}")
    print(f"Task: {args.task}")
    print(f"\n--- Results ---")
    print(f"Total Entries Evaluated: {total_data}")
    print(f"Error Type Distribution:")
    print(f"  Unhelpful Responses: {stats['error_unhelpful']}")
    print(f"  Inconsistent Responses: {stats['error_inconsistent']}")
    print(f"  Hallucination of Preference Violations: {stats['hallucination_of_preference_violation']}")
    print(f"  Preference Unaware Violations: {stats['preference_unaware_violation']}")
    accuracy = (stats["preference_adherence_accuracy"] / total_data) * 100
    print(f"\nPreference Following Accuracy: {accuracy:.2f}%")


def main():
    exp_configs = load_config("../config.yaml")
    parser = argparse.ArgumentParser(description="Evaluation Setup")
    parser.add_argument("--turn", type=int, default=10)
    parser.add_argument("--task", type=str, default="zero-shot", choices=["zero-shot", "remind"])
    parser.add_argument("--ft", type=str, default="across_topics_train_with_0turn_mistral")
    args = parser.parse_args()
    args.dir = exp_configs["dir_path"]
    eval_file = setup_paths(args)
    data = load_evaluation_data(eval_file)
    stats, total_data = analyze_errors(data)
    print_evaluation_results(stats, total_data, args)


if __name__ == "__main__":
    main()
