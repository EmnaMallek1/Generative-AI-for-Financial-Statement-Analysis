# Financial Statement Analysis with a Fine-Tuned LLM (LoRA)

An end-to-end pipeline that turns scanned/screenshotted financial statement
tables into an automated financial analysis, powered by a LoRA fine-tuned
Mistral-7B model. Built as a PFA (end-of-year) project in partnership with
a startup.

## Pipeline overview

```
 Images of financial          OCR              Uniformized       Labeled fine-tuning
 statement tables    ──────▶  (GLM-OCR)  ────▶  Excel files ──▶  JSON dataset
 (screenshots/scans)                                                   │
                                                                        ▼
                                                          LoRA fine-tuning
                                                          (Mistral-7B-Instruct-v0.3)
                                                                        │
                                                                        ▼
                                                          Inference + rendered
                                                          financial dashboard
```

| Stage | File | What it does |
|---|---|---|
| 1. OCR | [`glm_ocr.py`](./glm_ocr.py) | Converts images of financial tables (balance sheet, income statement) into Excel files, using the [GLM-OCR](https://huggingface.co/zai-org/GLM-OCR) vision-language model for table recognition. |
| 2. Data normalization | [`uniformize_each_file_v2.py`](./uniformize_each_file_v2.py) | Normalizes the raw OCR'd Excel files (inconsistent layouts, French labels, mixed number formats) into a single consistent schema per company/year. |
| — Dataset | [`data/`](./data) | The final labeled fine-tuning dataset (64 examples, 36 companies) — see [`data/README.md`](./data/README.md) for the data card. |
| 3. Model exploration | [`markdown.py`](./markdown.py) | Early-phase experimentation: several open-source LLMs were tested via [Ollama](https://ollama.com/), called through Postman, to evaluate raw financial-analysis quality before committing to fine-tuning. This script cleans up the markdown-formatted responses for review. |
| 4. Fine-tuning | [`lora_finetuning_mistral7b.ipynb`](./lora_finetuning_mistral7b.ipynb) | LoRA fine-tuning of `unsloth/mistral-7b-instruct-v0.3-bnb-4bit` on the labeled dataset, run on Google Colab via [Unsloth](https://github.com/unslothai/unsloth). Includes training curves, perplexity, JSON-validity evaluation, and inference/dashboard rendering. |

## Why fine-tune instead of just prompting?

Before fine-tuning, we tested general-purpose LLMs (via Ollama/Postman) on
financial analysis directly. Prompting alone struggled with:
- consistently returning **valid, well-structured JSON** (needed for downstream rendering),
- correctly computing **financial ratios** grounded strictly in the given numbers,
- staying concise and avoiding hallucinated commentary.

Fine-tuning on a labeled dataset of real financial statements (uniformized
and hand-labeled with the help of our startup supervisor) let a smaller,
cheaper-to-run model (Mistral-7B, 4-bit, LoRA) produce more reliable,
schema-consistent output than prompting alone.

## Model & training setup

- **Base model:** `unsloth/mistral-7b-instruct-v0.3-bnb-4bit`
- **Method:** LoRA (via Unsloth), `r=16`, `alpha=64`, dropout `0.15`, applied to all attention + MLP projections
- **Training:** 5 epochs, cosine LR schedule, 8-bit AdamW, gradient checkpointing — single GPU on Google Colab
- **Data:** 64 labeled financial-statement → analysis pairs from 36 Tunisian (BVMT-listed) companies' public financial statements — see [`data/README.md`](./data/README.md) for the full data card

See [`lora_finetuning_mistral7b.ipynb`](./lora_finetuning_mistral7b.ipynb) for the full training notebook, including training curves and perplexity plots.


## Output example

The fine-tuned model takes normalized financial statement data and returns
structured JSON (ratios with ratings, overall assessment, strengths,
weaknesses, recommendations), which is rendered into a readable dashboard —
see the last cells of the fine-tuning notebook for the rendering code.

## Tech stack

- **OCR:** GLM-OCR (Hugging Face `transformers`)
- **Data processing:** `pandas`, `openpyxl`
- **Fine-tuning:** Unsloth, PEFT/LoRA, `trl`, Hugging Face `transformers`, Google Colab
- **Model testing:** Ollama, Postman

## Setup

```bash
pip install -r requirements.txt
```

Each script can be run independently — see the docstring at the top of each file for usage.

## Notes

- All financial data in this repo comes from publicly available financial
  statements of companies listed on the Bourse de Tunis (BVMT) — no
  proprietary or confidential data is included.
- This project was developed as part of a university end-of-year project (PFA)
  in collaboration with a startup, which provided domain expertise for
  defining and reviewing how the fine-tuning dataset's outputs (ratios,
  interpretations, recommendations) should be labeled.
