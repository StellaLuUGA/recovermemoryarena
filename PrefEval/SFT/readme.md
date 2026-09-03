# Supervised Finetuning of Mistral 8x7B Model

This directory contains code for supervised finetuning of a Mistral 8x7B model downloaded from Huggingface on the PrefEval Benchmark.

## Training Data

The training data is obtained through the following process:

1. Get Mistral 8x7B's responses using the reminder method for all 20 topics with explicit preferences. The responses are stored in `single_pref_remind/`
2. Use LoRA finetuning to train the model.
3. During training, insert inter-turn conversations to simulate multi-session conversation history.
4. Train on 80% of the topics and evaluate on the remaining 20%.

## Evaluation

To evaluate the pretrained checkpoints:

1. Download the pretrained Mistral 8x7B checkpoints from *(add path)*.
2. Run the following command:

```
bash evaluate_pretrainedllms.sh
```

## Training

To train the Mistral model yourself, execute:

```
bash train_llms.sh
```