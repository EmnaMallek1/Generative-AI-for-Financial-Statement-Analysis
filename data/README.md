# Dataset: `financial_dataset_qlora_cleaned_v2.json`

The labeled instruction-tuning dataset used to fine-tune the model in
[`lora_finetuning_mistral7b.ipynb`](../lora_finetuning_mistral7b.ipynb).
Built from the earlier pipeline stages: OCR (`glm_ocr.py`) → normalization
(`uniformize_each_file_v2.py`) → this final labeled JSON.

## Summary

- **64 examples**, drawn from **36 companies**' financial statements
- **Source:** publicly available annual and semi-annual financial statements
  of companies listed on the Bourse de Tunis (BVMT — Tunis Stock Exchange),
  collected from public filings/investor-relations disclosures. No
  proprietary or startup-internal data is used.
- **Periods covered:** mostly FY2023–FY2025 (annual and half-year statements)
- **Format:** JSON list, one object per example, each with `instruction`, `input`, `output`

## Schema

```json
{
  "instruction": "Analyze the structured financial data below. Compute only ratios that are directly supported by the provided values and economically meaningful. Return only valid JSON. ...",
  "input": {
    "source_file": "CARTHAGE_CEMENT.xlsx",
    "period": "2024",
    "reporting_unit": "tnd",
    "financial_data": {
      "cash": 51565274.0,
      "current_assets": 265121045.0,
      "current_liabilities": 226638637.0,
      "equity": 328587754.0,
      "revenue": 212961548.0,
      "total_assets": 873522266.0,
      "...": "... (balance sheet + income statement fields, see uniformize_each_file_v2.py for the full field list)"
    }
  },
  "output": {
    "ratios": {
      "net_profit_margin": {
        "name": "Net Profit Margin",
        "formula": "Net income / Revenue",
        "calculation": "35492965.00 / 212961548.00 = 16.6664%",
        "value": 16.6664,
        "unit": "%",
        "status": "computed",
        "interpretation": "Strong positive margin."
      },
      "...": "... (profitability, liquidity, leverage ratios)"
    },
    "conclusion": {
      "overall_assessment": "...",
      "strengths": ["..."],
      "weaknesses": ["..."],
      "recommendations": ["..."],
      "summary_paragraph": "..."
    }
  }
}
```

The `financial_data` fields come from `uniformize_each_file_v2.py`,
which normalizes each company's raw (often French-labeled, inconsistently
formatted) Excel export into this consistent schema.

## Labeling process

`input` values are extracted and normalized automatically by the pipeline.
The `output` (computed ratios + qualitative analysis) was labeled with
guidance from our project supervisor at the startup we partnered with for
this project, to ensure ratio interpretations and the overall-assessment
logic reflected sound financial-analysis practice — the startup did not
contribute or own the underlying financial data itself, only labeling
guidance.

Note on `status: "not_available"`: several ratios are intentionally left
uncomputed when the required inputs weren't available or economically
meaningful for that company/period (e.g. ROE when equity is negative) —
the model is trained to recognize this rather than hallucinate a value.

## Known limitations

- Small dataset (64 examples) — fine-tuning at this scale is meant as a
  proof of concept, not a production-grade model.
- All companies are Tunisian and reported in TND — the model has not been
  validated on other currencies, accounting standards (e.g. US GAAP), or
  reporting formats.
- Some `source_file` entries are OCR'd from scanned PDFs and may contain
  minor extraction noise despite the normalization step.
