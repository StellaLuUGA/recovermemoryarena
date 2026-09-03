import os
import json
import torch
import yaml
import argparse
import random
from tqdm import tqdm
from typing import Any, Dict, List
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from sklearn.model_selection import train_test_split
from datasets import load_dataset, Dataset
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from sft_utils import extract_multi_turn_conversation


def load_vllm_model(base_model_name: str, peft_model_path: str):
    """Load the VLLM model with optional PEFT LoRA adapter."""
    llm = LLM(model=base_model_name, enable_lora=True)

    lora_request = LoRARequest("adapter", 1, peft_model_path) if peft_model_path else None
    return llm, lora_request


def preprocess_data(data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Preprocess the conversation data for training or evaluation."""
    return {
        "user_pref": [item["preference"] for item in data],
        "question": [item["question"] for item in data],
        "response_to_pref": [item["response_to_pref"] for item in data],
        "response_to_q": [item["response_to_q"] for item in data],
    }


def generate_response(model: LLM, input_text: str, lora_request: LoRARequest, max_new_tokens: int = 300) -> str:
    """Generate a response from the model given an input text and sampling parameters."""
    sampling_params = SamplingParams(n=1, temperature=0, top_p=1.0, max_tokens=max_new_tokens)
    response = model.generate(input_text, lora_request=lora_request, sampling_params=sampling_params)
    print("token count:", len(response[0].prompt_token_ids))
    return response[0].outputs[0].text


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration settings from a YAML file."""
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)
    config["dir_path"] = os.path.dirname(os.getcwd())
    return config


def main():
    exp_configs = load_config("../config.yaml")

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default="travel_hotel")
    parser.add_argument("--model", type=str, default="mistral8x7b")
    parser.add_argument("--ft", type=str, default="across_prefs_lora")
    parser.add_argument("--pretrained", type=bool, default=True)
    parser.add_argument("--turn", type=int, default=10)
    parser.add_argument("--task", type=str, default="zero-shot")
    args = parser.parse_args()

    args.dir = exp_configs["dir_path"]

    base_model_name = "mistralai/Mistral-7B-Instruct-v0.2"
    if args.pretrained:
        peft_model_path = f"{args.dir}/SFT/{args.ft}/checkpoint"
        print("loading PEFT model:", peft_model_path)
    else:
        peft_model_path = None
        args.ft = "nonSFT"
        print("using base model for inference:", base_model_name)
    save_dir = f"inference_result_with_{args.ft}"
    os.makedirs(save_dir, exist_ok=True)
    topics = [
        "travel_transportation",
        "shop_motors",
        "lifestyle_beauty",
        "travel_restaurant",
        "shop_fashion",
        "entertain_shows",
        "pet_ownership",
        "lifestyle_fit",
        "entertain_games",
        "shop_home",
        "lifestyle_health",
        "travel_activities",
        "education_learning_styles",
        "entertain_music_book",
        "professional_work_location_style",
        "education_resources",
        "lifestyle_dietary",
        "shop_technology",
        "travel_hotel",
        "entertain_sports",
    ]

    train_topics, eval_topics = train_test_split(topics, test_size=0.2, random_state=42)

    train_data = []
    eval_data = []

    # Process train topics
    for topic in train_topics:
        data_path = os.path.join(args.dir, "SFT", "single_pref_remind", topic, f"{args.model}_{topic}_2turn.json")
        with open(data_path, "r") as f:
            topic_data = json.load(f)
        train_data.extend(topic_data)

    # Process eval topics
    for topic in eval_topics:
        data_path = os.path.join(args.dir, "SFT", "single_pref_remind", topic, f"{args.model}_{topic}_2turn.json")
        with open(data_path, "r") as f:
            topic_data = json.load(f)
        eval_data.extend(topic_data)

    processed_data_train = preprocess_data(train_data)
    processed_data_eval = preprocess_data(eval_data)

    eval_dataset = Dataset.from_dict(processed_data_eval)

    model, lora_request = load_vllm_model(base_model_name, peft_model_path)

    with open(os.path.join(args.dir, "benchmark_dataset", "filtered_inter_turns.json"), "r") as infile:
        turns_data = json.load(infile)

    system_prompt = "You are an AI assistant."
    results = []
    inter_turns = args.turn
    if "remind" in args.task:
        reminder_txt = "\nIn your response, please ensure that you take into account our earlier discussion, and provide an answer that is consistent with my preference."
    else:
        reminder_txt = ""
    for item in tqdm(eval_dataset):
        preference = item["user_pref"]
        question = item["question"]
        pref_generation = item["response_to_pref"]

        # Extract multi-turn conversation
        multi_turn_message = []
        for turn_data in turns_data:
            multi_turn_message.extend(turn_data["conversation"])
        if inter_turns > 0:
            multi_inter_message = extract_multi_turn_conversation(multi_turn_message, inter_turns, model_type="mistral")
        else:
            multi_inter_message = ""
        # Format the input message
        message = f"""<s>[INST]
{system_prompt}
{preference}
[/INST]
{pref_generation}</s>
{multi_inter_message}
[INST]
{question}{reminder_txt}
[/INST]
"""
        # Generate response
        response = generate_response(model, message, lora_request)
        print(response)
        # Store results
        results.append(
            {
                "preference": preference,
                "question": question,
                "pref_generation": pref_generation,
                "model_response": response,
                "model_path": peft_model_path,
            }
        )

        save_path = os.path.join(save_dir, f"{inter_turns}turn_{args.task}.json")
        with open(save_path, "w") as f:
            json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
