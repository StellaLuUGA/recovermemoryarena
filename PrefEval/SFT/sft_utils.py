import tiktoken


def count_tokens(text):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # Using a default model
    return len(encoding.encode(text))


def extract_multi_turn_conversation(multi_turn_message, turn_number=3, model_type="llama"):
    message = []
    for turn in multi_turn_message:
        role = turn["role"]
        content = turn["content"]
        if model_type == "llama":
            message.append(f"<|start_header_id|>{role}<|end_header_id|>\n{content}<|eot_id|>")
        elif model_type == "claude":
            message.append({"role": role, "content": content})
        elif model_type == "mistral":
            if role == "user":
                message.append(f"[INST] {content} [/INST]")
            else:
                message.append(f"{content}</s>")
        elif model_type == "gpt":
            message.append({"role": role, "content": content})
        if len(message) == turn_number * 2:
            if role != "assistant":
                raise ValueError("The last turn must be from assistant")
            break
    assert len(message) == turn_number * 2, "The number of turns is less than the specified number"
    if "llama" in model_type or "mistral" in model_type:
        message = "".join(message)
    return message
