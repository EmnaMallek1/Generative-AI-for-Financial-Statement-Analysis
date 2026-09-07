import torch
import os
import tempfile
import pandas as pd
from PIL import Image, ImageOps
from transformers import AutoProcessor, AutoModelForImageTextToText
from io import StringIO

MODEL_PATH = "zai-org/GLM-OCR"

processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
model = AutoModelForImageTextToText.from_pretrained(
    pretrained_model_name_or_path=MODEL_PATH,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)

TASK_PROMPTS = {
    "Text": "Text Recognition:",
    "Formula": "Formula Recognition:",
    "Table": "Table Recognition:",
}

def process_image(image_path, task="Table"):
    image = Image.open(image_path)

    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGB")
    image = ImageOps.exif_transpose(image)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    image.save(tmp.name, "PNG")
    tmp.close()

    prompt = TASK_PROMPTS.get(task, "Text Recognition:")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": tmp.name},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    inputs.pop("token_type_ids", None)

    generated_ids = model.generate(**inputs, max_new_tokens=8192)
    output_text = processor.decode(
        generated_ids[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )

    os.unlink(tmp.name)
    return output_text.strip()


def result_to_dataframe(result):
    """Convert HTML or Markdown table string to a DataFrame."""

    # Case 1: HTML output
    if "<table" in result.lower():
        print("  Detected HTML table.")
        tables = pd.read_html(StringIO(result))
        df = tables[0]
        '''
        def clean_row(row):
            cleaned = row.copy()
            for i in range(1, len(row)):
                if row[i] == row[i - 1]:
                    cleaned[i] = ""
            return cleaned
        '''
        def clean_row(row):
            cleaned = row.copy()
            for i in range(1, len(row)):
                if row[i] == row[i - 1]:
                    # Only clear if the value is NOT a number
                    try:
                        float(str(row[i]).replace(" ", "").replace(",", "."))
                        # It's a number, keep it
                    except (ValueError, TypeError):
                        # It's a string, clear the duplicate
                        cleaned[i] = ""
            return cleaned




        df = df.apply(clean_row, axis=1)

    # Case 2: Markdown output
    elif "|" in result:
        print("  Detected Markdown table.")
        lines = result.strip().split("\n")
        table_lines = [
            line for line in lines
            if "|" in line and not all(c in "| :-" for c in line)
        ]
        rows = []
        for line in table_lines:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append(cells)
        df = pd.DataFrame(rows[1:], columns=rows[0])

    else:
        print("  No table detected.")
        df = None

    return df


if __name__ == "__main__":

    # Define your 3 images and their sheet names
    images = [
        {
            "path": r"C:\Users\Lenovo\Pictures\Screenshots\Capture d'écran 2026-02-22 232221.png",
            "sheet": "Sheet1",
            "md_path": r"C:\Users\Lenovo\Desktop\2AMIndS\PFA2\data_pdf\output_1.md",
        },
        {
            "path": r"C:\Users\Lenovo\Pictures\Screenshots\Capture d'écran 2026-02-22 232320.png",
            "sheet": "Sheet2",
            "md_path": r"C:\Users\Lenovo\Desktop\2AMIndS\PFA2\data_pdf\output_2.md",
        },
        {
            "path": r"C:\Users\Lenovo\Pictures\Screenshots\Capture d'écran 2026-02-22 232409.png",
            "sheet": "Sheet3",
            "md_path": r"C:\Users\Lenovo\Desktop\2AMIndS\PFA2\data_pdf\output_3.md",
        },
    ]

    task = "Table"
    xlsx_path = r"C:\Users\Lenovo\Desktop\2AMIndS\PFA2\data_pdf\output_combined.xlsx"

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for i, img in enumerate(images, 1):
            print(f"\nProcessing image {i}: {img['path']}")

            result = process_image(img["path"], task)

            # Save markdown
            with open(img["md_path"], "w", encoding="utf-8") as f:
                f.write(result)
            print(f"  Markdown saved to {img['md_path']}")

            # Convert to DataFrame and write to Excel sheet
            df = result_to_dataframe(result)
            if df is not None:
                df.to_excel(writer, sheet_name=img["sheet"], index=False)
                print(f"  Written to Excel sheet: {img['sheet']}")
            else:
                print(f"  Skipped Excel sheet for image {i} (no table found).")

    print(f"\nAll done! Excel saved to {xlsx_path}")