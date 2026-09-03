#!/bin/bash
# Long-context agent against the local vLLM server (llama-3.1-8b-instruct-local).
# Requires the vLLM server on $LOCAL_LLM_BASE_URL (see .env) to be up.

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
root=$(pwd)
PY=${PY:-/home/aristella/miniconda3/envs/MABench/bin/python}

file_name=local_llama_agents.txt

# lines 5-8 = datasets that fit in the 32k window; 11-13 = truncated long-context ones
for line in {5..8..1}
    do
        cfg=$(sed -n "$line"p ${root}/bash_files/configs/${file_name})
        agent_config=$(echo $cfg | cut -f 1 -d ' ')
        dataset_config=$(echo $cfg | awk '{print $2}')

        echo ................Start...........
        $PY main.py \
            --agent_config      configs/agent_conf/Long_Context_Agents/${agent_config} \
            --dataset_config    configs/data_conf/${dataset_config}
        echo ................End...........
    done

# bash bash_files/sh/run_memagent_local_llama.sh
