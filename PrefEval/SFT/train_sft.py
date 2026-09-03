import os
import json
import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, List

import torch
import yaml
from datasets import Dataset
from sklearn.model_selection import train_test_split
from accelerate import Accelerator, PartialState
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedTokenizerBase,
    Trainer,
    TrainingArguments,
)

from sft_utils import extract_multi_turn_conversation, count_tokens


@dataclass
class PreferenceDataCollatorSFT:
    tokenizer: PreTrainedTokenizerBase
    multi_conversation: List[Any] = field(default_factory=list)
    max_tokens: int = 0
    min_tokens: int = 400000
    inter_turn: int = 0

    def __call__(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        input_texts = []
        responses = []

        for ex in examples:
            input_text = self.process_input(ex)
            response = ex["response_to_q"]
            input_texts.append(input_text)
            responses.append(response)

        # Tokenize and pad inputs
        inputs = self.tokenizer(
            input_texts,
            padding=True,
            truncation=True,
            max_length=8000,
            return_tensors="pt",
        )
        response_encodings = self.tokenizer(
            responses,
            padding=True,
            truncation=True,
            max_length=8000,
            return_tensors="pt",
        )

        # Create labels tensor initialized with -100
        labels = torch.full_like(inputs["input_ids"], -100)

        # Find where the response starts in each input
        for i, (input_text, response) in enumerate(zip(input_texts, responses)):
            response_start = input_text.rfind(response)
            if response_start != -1:
                response_tokens = self.tokenizer.encode(response, add_special_tokens=False)
                response_length = len(response_tokens)

                # Find the starting position of the response in the tokenized input
                response_start_token = len(self.tokenizer.encode(input_text[:response_start], add_special_tokens=False))

                # Replace -100 with actual token IDs for the response part
                labels[i, response_start_token : response_start_token + response_length] = response_encodings[
                    "input_ids"
                ][i, :response_length]

        inputs["labels"] = labels
        return inputs

    def process_input(self, ex: Dict[str, Any]) -> str:
        preference = ex["user_pref"]
        question = ex["question"]
        pref_generation = ex["response_to_pref"]
        response = ex["response_to_q"]
        multi_turn_message = []

        for turn_data in self.multi_conversation[-4:]:
            multi_turn_message.extend(turn_data["conversation"])

        if self.inter_turn > 0:
            multi_inter_message = extract_multi_turn_conversation(
                multi_turn_message, self.inter_turn, model_type="mistral"
            )
        else:
            multi_inter_message = ""

        system_prompt = "You are an AI assistant."
        message = f"""<s>[INST]
{system_prompt}
{preference}
[/INST]
{pref_generation}</s>
{multi_inter_message}
[INST]
{question}
[/INST]
{response}
</s>"""

        num_tokens = count_tokens(message)
        self.max_tokens = max(self.max_tokens, num_tokens)
        self.min_tokens = min(self.min_tokens, num_tokens)
        print(f"Number of tokens in the prompt: {num_tokens} | " f"Inter Turns inserted: {self.inter_turn}")
        return message


def load_model_and_tokenizer(model_name: str, load_in_8bit: bool = True):
    """
    Load the model and tokenizer.
    """
    config = BitsAndBytesConfig(
        load_in_8bit=True,
        # bnb_4bit_quant_type="nf4",
        # bnb_4bit_use_double_quant=True,
        # bnb_4bit_compute_dtype=torch.bfloat16,
    )
    # config = BitsAndBytesConfig(
    #     load_in_4bit=True,
    #     bnb_4bit_quant_type="nf4",
    #     bnb_4bit_use_double_quant=True,
    #     bnb_4bit_compute_dtype=torch.bfloat16,
    # )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=config,
        device_map={"": PartialState().process_index},
    )
    model = prepare_model_for_kbit_training(model)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer


def train(
    model,
    args,
    tokenizer,
    train_dataset,
    eval_dataset,
    output_dir: str,
    num_train_epochs: int = 1,
    per_device_train_batch_size: int = 1,
    per_device_eval_batch_size: int = 1,
    gradient_accumulation_steps: int = 2,
    optim: str = "paged_adamw_8bit",
    save_steps: int = 10,
    logging_steps: int = 10,
    learning_rate: float = 2e-4,
    max_grad_norm: float = 0.3,
    max_steps: int = -1,
    warmup_ratio: float = 0.03,
    group_by_length: bool = True,
    lr_scheduler_type: str = "constant",
    multi_turn: List[Any] = None,
) -> None:
    """
    Train the model using the Trainer class.
    """
    if multi_turn is None:
        multi_turn = []

    # Configure LoRA
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    # Apply LoRA to the model
    model = get_peft_model(model, peft_config)
    model.config.use_cache = False
    accelerator = Accelerator()

    # Set up training arguments
    training_arguments = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        per_device_eval_batch_size=per_device_eval_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        optim=optim,
        save_steps=save_steps,
        logging_steps=logging_steps,
        learning_rate=learning_rate,
        fp16=True,
        eval_strategy="steps",
        eval_steps=5,
        max_grad_norm=max_grad_norm,
        max_steps=max_steps,
        warmup_ratio=warmup_ratio,
        remove_unused_columns=False,
        lr_scheduler_type=lr_scheduler_type,
        ddp_find_unused_parameters=False,
    )

    pref_collator = PreferenceDataCollatorSFT(
        tokenizer=tokenizer,
        multi_conversation=multi_turn,
        inter_turn=args.inter_turn,
    )

    trainer = accelerator.prepare(
        Trainer(
            model=model,
            args=training_arguments,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=tokenizer,
            data_collator=pref_collator,
        )
    )

    # Start training
    trainer.train()

    # Save the final model
    trainer.model.save_pretrained(os.path.join(output_dir, "final_model"))


def preprocess_data(data: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    processed_data = {
        "user_pref": [],
        "question": [],
        "response_to_pref": [],
        "response_to_q": [],
    }

    for item in data:
        processed_data["user_pref"].append(item["preference"])
        processed_data["question"].append(item["question"])
        processed_data["response_to_pref"].append(item["response_to_pref"])
        processed_data["response_to_q"].append(item["response_to_q"])

    return processed_data


def load_config(config_file: str) -> Dict[str, Any]:
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)

    # Get the parent directory
    parent_dir = os.path.dirname(os.getcwd())
    config["dir_path"] = parent_dir
    return config


if __name__ == "__main__":
    # Load configuration
    exp_configs = load_config("../config.yaml")
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="mistral8x7b")
    parser.add_argument("--inter_turn", type=int, default=10)
    args = parser.parse_args()
    args.dir = exp_configs["dir_path"]

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

    train_dataset = Dataset.from_dict(processed_data_train)
    eval_dataset = Dataset.from_dict(processed_data_eval)

    with open(os.path.join(args.dir, "benchmark_dataset", "filtered_inter_turns.json"), "r") as infile:
        turns_data = json.load(infile)

    print(f"Length of train dataset: {len(train_dataset)}")
    print(f"Length of eval dataset: {len(eval_dataset)}")

    model_name = "mistralai/Mistral-7B-Instruct-v0.2"
    model, tokenizer = load_model_and_tokenizer(model_name, load_in_8bit=True)

    train(
        model=model,
        args=args,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        output_dir=os.path.join(args.dir, f"SFT/across_topics_train_with_{args.inter_turn}turn"),
        multi_turn=turns_data,
    )
