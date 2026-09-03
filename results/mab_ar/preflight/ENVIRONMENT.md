# MAB-AR preflight: environment (brief §3)

Generated: 2026-08-28T05:54:07-04:00

## Interpreter

```
path:   /home/aristella/miniconda3/envs/MABench/bin/python
python: Python 3.10.16
prefix: /home/aristella/miniconda3/envs/MABench
```

The vLLM serving environment `/home/aristella/.pipenv-venv` was **not** touched during
this task: no install, uninstall, upgrade or downgrade. Every command above uses the
absolute MABench interpreter path; `conda activate` is never relied on.

## What was installed, and why

`pip install -r MemoryAgentBench/requirements.txt` was NOT run. Only the packages the
selected execution path (AR dataset loading, native AR metric, exact Llama tokenizer,
Mem0 host, local OpenAI-compatible endpoint) actually imports were installed:

| package | reason |
|---|---|
| `datasets`, `pyarrow` | upstream `utils.eval_data_utils.load_eval_data` |
| `transformers`, `tokenizers` | exact Llama-3.1-8B-Instruct tokenizer (brief §5) |
| `tiktoken` | upstream `chunk_text_into_sentences` (benchmark-native chunking only) |
| `nltk`, `rouge_score`, `editdistance` | upstream `utils.eval_other_utils` metric module |
| `openai` | local OpenAI-compatible client -> 127.0.0.1:8123 |
| `numpy<2`, `scikit-learn` | ReCoverMem predictor / metrics |
| `mem0ai` (editable, `--no-deps`, from the pinned checkout) | Table 1 host |
| `qdrant-client`, `sqlalchemy`, `posthog`, `protobuf<7` | hard `mem0` imports |
| `faiss-cpu` | Mem0 `vector_store.provider = faiss` |
| `sentence-transformers` | Mem0 `embedder.provider = huggingface` (CPU) |
| `torch` | transitive requirement of `transformers` / `sentence-transformers` |

Deliberately NOT installed: `vllm`, `faiss-gpu`, `flash_attn`, `deepspeed`, `cognee`,
`letta`, `hipporag`. None is reachable from the MAB-AR execution path.

## Frozen versions

```
absl-py==2.5.0
aiohappyeyeballs==2.7.1
aiohttp==3.14.3
aiosignal==1.4.0
annotated-doc==0.0.5
annotated-types==0.8.0
anthropic==1.2.0
anyio==4.14.2
async-timeout==5.0.1
attrs==26.1.0
backoff==2.2.1
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
click==8.5.0
cryptography==50.0.1
cuda-bindings==13.3.1
cuda-pathfinder==1.8.0
cuda-toolkit==13.0.3.0
datasets==5.0.1
defusedxml==0.7.1
dill==0.4.1
distro==1.9.0
docstring_parser==0.18.0
editdistance==0.8.1
exceptiongroup==1.3.1
faiss-cpu==1.15.0
filelock==3.32.4
frozenlist==1.8.0
fsspec==2026.6.0
google-auth==2.57.0
google-genai==2.20.0
greenlet==3.5.5
grpcio==1.83.1
h11==0.16.0
h2==4.4.1
hf-xet==1.6.0
hpack==4.2.0
httpcore==1.0.9
httpcore2==2.12.0
httpx==0.28.1
httpx2==2.12.0
huggingface_hub==1.29.0
hyperframe==6.1.0
idna==3.19
Jinja2==3.1.6
jiter==0.16.0
joblib==1.5.3
jsonpatch==1.33
jsonpointer==3.1.1
langchain-core==1.6.1
langchain-openai==1.6.0
langchain-protocol==0.0.19
langsmith==0.11.2
markdown-it-py==4.2.0
MarkupSafe==3.0.3
mdurl==0.1.2
mem0ai==2.0.19
mpmath==1.3.0
multidict==6.7.1
multiprocess==0.70.19
networkx==3.4.2
nltk==3.10.3
numpy==1.26.4
nvidia-cublas==13.1.1.3
nvidia-cuda-cupti==13.0.85
nvidia-cuda-nvrtc==13.0.88
nvidia-cuda-runtime==13.0.96
nvidia-cudnn-cu13==9.20.0.48
nvidia-cufft==12.0.0.61
nvidia-cufile==1.15.1.6
nvidia-curand==10.4.0.35
nvidia-cusolver==12.0.4.66
nvidia-cusparse==12.6.3.3
nvidia-cusparselt-cu13==0.8.1
nvidia-nccl-cu13==2.29.7
nvidia-nvjitlink==13.3.33
nvidia-nvshmem-cu13==3.4.5
nvidia-nvtx==13.0.85
openai==3.5.0
orjson==3.12.0
packaging==26.3
pandas==2.3.3
pip==26.2.1
portalocker==3.2.0
posthog==7.44.2
propcache==0.5.2
protobuf==6.33.6
pyarrow==25.0.1
pyasn1==0.6.4
pyasn1_modules==0.4.2
pycparser==3.0
pydantic==2.13.4
pydantic_core==2.46.4
Pygments==2.21.0
python-dateutil==2.9.0.post0
python-dotenv==1.2.3
pytz==2026.3.post1
PyYAML==6.0.3
qdrant-client==1.19.0
rank-bm25==0.2.2
regex==2026.7.19
requests==2.34.2
requests-toolbelt==1.0.0
rich==15.0.0
rouge_score==0.1.2
safetensors==0.8.0
scikit-learn==1.7.2
scipy==1.15.3
semantic-text-splitter==0.32.0
sentence-transformers==6.0.0
setuptools==83.0.0
shellingham==1.5.4
six==1.17.0
sniffio==1.3.1
SQLAlchemy==2.0.52
sympy==1.14.0
tenacity==9.1.4
threadpoolctl==3.6.0
tiktoken==0.14.0
tokenizers==0.23.1
torch==2.13.0
tqdm==4.70.0
transformers==5.16.1
triton==3.7.1
truststore==0.10.4
typer==0.27.1
typing_extensions==4.16.0
typing-inspection==0.4.4
tzdata==2026.3
urllib3==2.7.0
uuid_utils==0.17.0
websockets==16.1.1
wheel==0.47.0
xxhash==4.0.1
yarl==1.24.5
zstandard==0.25.0
```

## pip check

```
No broken requirements found.
```
