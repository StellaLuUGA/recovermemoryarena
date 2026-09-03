# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shows how to generate a message with Anthropic Claude (on demand).
"""
import boto3
from botocore.config import Config
from typing import Any, Dict, List
import yaml
import json
import logging
from tqdm import tqdm
from botocore.exceptions import ClientError

import os
import argparse
import time

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from bs4 import BeautifulSoup

import xml.etree.ElementTree as ET


def parse_explanation_and_answer(input_string):
    # Create a BeautifulSoup object
    soup = BeautifulSoup(input_string, "html.parser")

    # Find the explanation tag and extract its content
    explanation_tag = soup.find("explanation")
    explanation = explanation_tag.text.strip() if explanation_tag else ""

    # Find the answer tag and extract its content
    answer_tag = soup.find("answer")
    answer = answer_tag.text.strip() if answer_tag else ""

    return explanation, answer


def parse_preference_and_answer(input_string):
    # Create a BeautifulSoup object
    soup = BeautifulSoup(input_string, "html.parser")

    # Find the preference tag and extract its content
    preference_tag = soup.find("preference")
    preference = preference_tag.text.strip() if preference_tag else ""

    # Find the answer tag and extract its content
    answer_tag = soup.find("answer")
    answer = answer_tag.text.strip() if answer_tag else ""

    return preference, answer


def generate_message(bedrock_runtime, model_id, system_prompt, messages, max_tokens, max_retries=20):
    retries = 0
    while retries < max_retries:
        try:
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": messages,
                    "temperature": 0.0,
                }
            )

            response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
            response_body = json.loads(response.get("body").read())

            return response_body
        except ClientError as e:
            retries += 1
            print(str(e), "retrying:", retries)
            if retries == 19:
                time.sleep(1)
                retries = 0
            time.sleep(1)


def print_conversation(messages):
    for message in messages:
        role = message["role"]
        content = message["content"]
        print(f"{role.capitalize()}: {content}\n")
        print()


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration settings from a YAML file."""
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)
    config["dir_path"] = os.path.dirname(os.getcwd())
    return config


def main():
    exp_configs = load_config("../config.yaml")

    parser = argparse.ArgumentParser(description="eval")
    parser.add_argument("--model", type=str, default="claude3s")
    parser.add_argument("--turn", type=int, default=10)
    parser.add_argument("--loc", type=int, default=10)
    parser.add_argument("--topic", type=str, default="travel_restaurant")
    parser.add_argument("--task", type=str, default="zero-shot")
    parser.add_argument("--ft", type=str, default="across_topics_train_with_0turn_mistral")
    parser.add_argument("--pretrained", type=str, default="yes")
    parser.add_argument(
        "--method",
        type=str,
        default="single_pref_remind",
    )
    parser.add_argument("--debug", action="store_false")
    args = parser.parse_args()
    args.dir = exp_configs["dir_path"]
    try:
        client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        max_tokens = 100
        generation_file = f"{args.dir}/SFT/inference_result_with_{args.ft}/{args.turn}turn_{args.task}.json"
        save_file = f"{args.dir}/SFT/inference_result_with_{args.ft}/eval_{args.turn}turn_{args.task}.json"

        with open(generation_file, "r") as f:
            generation_data = json.load(f)

        if os.path.isfile(save_file):
            with open(save_file, "r") as f:
                existing_eval_data = json.load(f)
                if len(existing_eval_data) != len(generation_data):
                    existing_eval_data = generation_data
        else:
            existing_eval_data = generation_data

        for task_id, task in enumerate(tqdm(existing_eval_data)):
            print(save_file)
            if "evaluation_error_analysis" in task:
                analysis = task["evaluation_error_analysis"]
                if (
                    "acknow" in analysis
                    and "violate" in analysis
                    and "hallucinate" in analysis
                    and "helpful" in analysis
                ):
                    print("already task_id", task_id)
                    continue

            preference = task["preference"]
            question = task["question"]
            end_generation = task["model_response"]
            system_prompt = """You are a helpful assistant in evaluating an AI assistant's reponse. You should be fair and strict and follow the user's instruction"""
            BASE_DIR = f"{args.dir}/error_type"
            file_dict = {
                "acknow": "check_acknowledge.txt",
                "violate": "check_violation.txt",
                "hallucinate": "check_hallucination.txt",
                "helpful": "check_helpful.txt",
            }

            eval_message_texts = []
            for metric_name, file_name in file_dict.items():
                file_path = os.path.join(BASE_DIR, file_name)
                with open(file_path, "r") as f:
                    eval_message_texts.append([metric_name, f.read()])
            if "evaluation_error_analysis" in task:
                error_check = task["evaluation_error_analysis"]
            else:
                error_check = {}
            for idx, (metric, eval_message_text) in enumerate(eval_message_texts):
                if metric in error_check:
                    continue
                if metric == "acknow":
                    eval_message_text = eval_message_text.replace("{end_generation}", end_generation)
                    eval_message_text = eval_message_text.replace("{question}", question)
                elif metric == "violate" or metric == "helpful":
                    eval_message_text = eval_message_text.replace("{preference}", preference)
                    eval_message_text = eval_message_text.replace("{question}", question)
                    eval_message_text = eval_message_text.replace("{end_generation}", end_generation)
                elif metric == "hallucinate":
                    extracted_pref = error_check["acknow"]["extract_pref"]
                    eval_message_text = eval_message_text.replace("{preference}", preference)
                    eval_message_text = eval_message_text.replace("{assistant_restatement}", extracted_pref)
                eval_message = [{"role": "user", "content": eval_message_text}]
                eval_response = generate_message(client, model_id, system_prompt, eval_message, max_tokens)["content"][
                    0
                ]["text"]
                error_check[metric] = {}
                if metric != "acknow":
                    explanation, answer = parse_explanation_and_answer(eval_response)
                    error_check[metric]["explanation"] = explanation
                    error_check[metric]["answer"] = answer
                else:
                    extract_preference, answer = parse_preference_and_answer(eval_response)
                    error_check[metric]["answer"] = answer
                    error_check[metric]["extract_pref"] = extract_preference
            task["evaluation_error_analysis"] = error_check
            existing_eval_data[task_id] = task
            with open(save_file, "w") as outfile:
                json.dump(existing_eval_data, outfile, indent=4)
        print("done!", args.model, save_file)
    except ClientError as err:
        message = err.response["Error"]["Message"]
        logger.error("A client error occurred: %s", message)
        print("A client error occured: " + format(message))


if __name__ == "__main__":
    main()
