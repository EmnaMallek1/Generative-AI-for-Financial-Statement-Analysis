import json
import re
import unicodedata
import math
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR
OUTPUT_DIR = BASE_DIR / "uniformized_samples"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    text = str(text).strip().lower().replace("\n", " ").replace("’", "'").replace("`", "'")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


def clean_number(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if math.isnan(value):
                return None
        except Exception:
            pass
        return float(value)

    s = str(value).strip()
    if s == "" or normalize_text(s) in {"-", "nan", "none", "null"}:
        return None

    s = s.replace("\xa0", " ").replace("*", "").strip()

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()

    # remove spaces used as thousand separators
    s = s.replace(" ", "")

    # French numbers: comma decimal separator
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        # keep the last separator as decimal separator
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")

    s = re.sub(r"[^0-9.\-]", "", s)
    if s in {"", "-", ".", "-.", ".-"}:
        return None

    try:
        num = float(s)
        return -num if negative else num
    except Exception:
        return None


# =========================================================
# AJOUT MINIMAL : NORMALISATION DES SIGNES
# =========================================================
def normalize_sign(label, value):
    if value is None:
        return None

    label = normalize_text(label)

    # DO NOT touch results
    if any(k in label for k in [
        "resultat",
        "benefice"
    ]):
        return value

    # convert expenses to positive
    if any(k in label for k in [
        "charge",
        "charges",
        "perte",
        "pertes",
        "amortissement",
        "provision",
        "impot"
    ]):
        return abs(value)

    return value


YEAR_EXACT = re.compile(r"^(20\d{2})$")
DATE_FULL = re.compile(r"^\d{1,2}[./-]\d{1,2}[./-](20\d{2})$")
DATE_2DIGIT_YEAR = re.compile(r"^\d{1,2}[./-][a-zéûîôèàç]+[./-](\d{2})$")


def extract_year_from_cell(cell: Any) -> Optional[str]:
    if cell is None:
        return None

    if isinstance(cell, (dt.datetime, dt.date)):
        return str(cell.year)

    txt = normalize_text(cell)
    if not txt:
        return None

    m = YEAR_EXACT.match(txt)
    if m:
        return m.group(1)

    m = DATE_FULL.match(txt)
    if m:
        return m.group(1)

    m = DATE_2DIGIT_YEAR.match(txt)
    if m:
        yy = int(m.group(1))
        return f"20{yy:02d}"

    years = re.findall(r"(20\d{2})", txt)
    if years:
        return years[-1]

    return None


def detect_year_columns(rows: List[List[Any]]) -> Tuple[Dict[int, str], Optional[int], Optional[int]]:
    """
    Find the true header row containing year/date columns.
    Also detect a Notes column when it is a standalone cell.
    """
    best = None
    best_score = -1

    for i, row in enumerate(rows[:12]):
        current_years: Dict[int, str] = {}
        note_col: Optional[int] = None
        score = 0

        for j, cell in enumerate(row):
            txt = normalize_text(cell)

            # Note column only if the cell is exactly "notes"/"note"
            if txt in {"notes", "note", "notes:", "note:"}:
                note_col = j
                score += 1
                continue

            year = extract_year_from_cell(cell)
            if year:
                current_years[j] = year
                score += 3

        if len(current_years) >= 2:
            cols = sorted(current_years)
            gap = sum(cols[k + 1] - cols[k] for k in range(len(cols) - 1))
            score -= gap * 0.01
            if score > best_score:
                best = (current_years, note_col, i)
                best_score = score

    if best:
        return best

    return {}, None, None


def sheet_kind(rows: List[List[Any]], title: str = "") -> str:
    txt = " ".join(normalize_text(c) for row in rows[:15] for c in row if c is not None)
    title_n = normalize_text(title)

    if (
        "etat de resultat" in txt
        or "produits d'exploitation" in txt
        or "charges d'exploitation" in txt
        or "etat de resultat" in title_n
    ):
        return "income"

    if (
        "capitaux propres et passifs" in txt
        or "capitaux propres & passifs" in txt
        or ("passifs" in txt and "capitaux propres" in txt)
    ):
        return "liabilities"

    if "actifs" in txt:
        return "assets"

    return "unknown"


def best_label_from_row(row: List[Any], year_cols: Dict[int, str], note_col: Optional[int] = None) -> str:
    skip = set(year_cols.keys())
    if note_col is not None:
        skip.add(note_col)

    for j, cell in enumerate(row):
        if j in skip:
            continue
        txt = normalize_text(cell)
        if txt:
            return txt

    return ""


def extract_year_values(row: List[Any], year_cols: Dict[int, str]) -> Dict[str, Optional[float]]:
    return {year: clean_number(row[j] if j < len(row) else None) for j, year in year_cols.items()}


def parse_assets(label: str) -> Optional[str]:
    if "total des actifs" in label and "courants" not in label and "non courants" not in label and "immobilis" not in label:
        return "total_assets"
    if "total des actifs non courants" in label:
        return "non_current_assets"
    if "total des actifs courants" in label:
        return "current_assets"
    return None


def parse_liabilities(label: str) -> Optional[str]:
    if "capitaux propres et passifs" in label:
        return None
    if "avant resultat" in label and "capitaux propres" in label:
        return "equity_before_result"
    if (
        ("avant affectation" in label and "capitaux propres" in label)
        or label in {"total des capitaux propres", "total capitaux propres"}
    ):
        return "equity"
    if "total des passifs non courants" in label or "total passifs non courants" in label:
        return "non_current_liabilities"
    if "total des passifs courants" in label or "total passifs courants" in label:
        return "current_liabilities"
    if label in {"total des passifs", "total passifs"}:
        return "total_liabilities"
    return None


def parse_income(label: str) -> Optional[str]:
    if label == "revenus" or "total des revenus" in label or label.startswith("ventes, travaux") or label.startswith("ventes "):
        return "revenue"
    if "total des produits d'exploitation" in label or "total des produits dexploitation" in label:
        return "total_operating_income"
    if "total des charges d'exploitation" in label or "total des charges dexploitation" in label:
        return "total_operating_expense"
    if "resultat d'exploitation" in label or "resultat dexploitation" in label:
        return "operating_result"
    if "charges financieres nettes" in label:
        return "financial_expense_net"
    if (
        "produits des placements et autres produits financiers" in label
        or label == "produits des placements"
        or label == "produits financiers"
    ):
        return "financial_income"
    if "autres gains ordinaires" in label:
        return "other_ordinary_gains"
    if "autres pertes ordinaires" in label or "autres perte ordinaires" in label:
        return "other_ordinary_losses"
    if "resultat des activites ordinaires avant impot" in label or "resultat courant des societes integrees" in label:
        return "profit_before_tax"
    if "impot sur les benefices" in label or "impot sur les societes" in label:
        return "income_tax"
    if (
        "resultat net revenant a la societe consolidante" in label
        or "resultat net de l'exercice" in label
        or "resultat net de la periode" in label
        or "resultat net de l'ensemble consolide" in label
    ):
        return "net_income"
    return None


def maybe_compute_operating_result(vals: Dict[str, float]) -> Optional[float]:
    toi = vals.get("total_operating_income")
    toe = vals.get("total_operating_expense")
    if toi is None or toe is None:
        return None

    # Some files store expenses as positive amounts, others as negative amounts
    if toe >= 0:
        return toi - toe
    return toi + toe


def process_workbook(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    data: Dict[str, Dict[str, float]] = {}
    debug: Dict[str, Any] = {"sheets": {}}

    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        kind = sheet_kind(rows, ws.title)
        year_cols, note_col, header_row = detect_year_columns(rows)

        debug["sheets"][ws.title] = {
            "kind": kind,
            "year_cols": year_cols,
            "note_col": note_col,
            "header_row": header_row,
        }

        if not year_cols or kind == "unknown":
            continue

        prev_label = "__none__"
        prev_vals = None

        for row in rows:
            label = best_label_from_row(row, year_cols, note_col)
            vals = extract_year_values(row, year_cols)

            # =========================================================
            # AJOUT MINIMAL : NORMALISATION DES SIGNES
            # =========================================================
            for year in vals:
                vals[year] = normalize_sign(label, vals[year])

            field = None
            if kind == "assets":
                field = parse_assets(label)
            elif kind == "liabilities":
                field = parse_liabilities(label)
            elif kind == "income":
                field = parse_income(label)

            # Fallback: some files place the numeric values on the row above an empty label row
            if field and all(v is None for v in vals.values()) and prev_label == "" and prev_vals and any(v is not None for v in prev_vals.values()):
                vals = prev_vals

            if field:
                for year, value in vals.items():
                    if value is not None:
                        data.setdefault(year, {})
                        # Later matches overwrite earlier ones
                        data[year][field] = value

            prev_label = label
            prev_vals = vals

    # Post-processing / consistency corrections
    for year, vals in data.items():
        ncl = vals.get("non_current_liabilities")
        cl = vals.get("current_liabilities")
        ta = vals.get("total_assets")
        ca = vals.get("current_assets")
        eq = vals.get("equity")

        if "total_liabilities" not in vals and ncl is not None and cl is not None:
            vals["total_liabilities"] = ncl + cl

        tl = vals.get("total_liabilities")

        if eq is None and ta is not None and tl is not None:
            vals["equity"] = ta - tl

        if "non_current_assets" not in vals and ta is not None and ca is not None:
            vals["non_current_assets"] = ta - ca
        elif ta is not None and ca is not None and vals.get("non_current_assets") is not None:
            nca = vals["non_current_assets"]
            if abs((nca + ca) - ta) > max(1.0, 0.01 * abs(ta)):
                corrected = ta - ca
                if corrected > 0:
                    vals["non_current_assets"] = corrected

        if "operating_result" not in vals:
            op = maybe_compute_operating_result(vals)
            if op is not None:
                vals["operating_result"] = op

        if "net_income" not in vals:
            pbt = vals.get("profit_before_tax")
            tax = vals.get("income_tax")
            if pbt is not None and tax is not None:
                vals["net_income"] = pbt + tax

    sample = {
        "source_file": path.name,
        "statement_data": data
    }
    return sample, debug


def main():
    excel_files = sorted(INPUT_DIR.glob("*.xlsx"))
    all_samples: List[Dict[str, Any]] = []

    if not excel_files:
        print("No .xlsx files found in", INPUT_DIR)
        return

    for xlsx_file in excel_files:
        try:
            sample, debug = process_workbook(xlsx_file)
            all_samples.append(sample)

            out_path = OUTPUT_DIR / f"{xlsx_file.stem}.json"
            dbg_path = OUTPUT_DIR / f"{xlsx_file.stem}_debug.json"

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(sample, f, ensure_ascii=False, indent=2)

            with open(dbg_path, "w", encoding="utf-8") as f:
                json.dump(debug, f, ensure_ascii=False, indent=2)

            print(f"✅ JSON generated: {out_path}")
            print(f"✅ Debug generated: {dbg_path}")

        except Exception as e:
            print(f"❌ Error with {xlsx_file.name}: {e}")

    dataset_path = OUTPUT_DIR / "dataset_inputs.json"
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, ensure_ascii=False, indent=2)

    print(f"✅ Combined dataset -> {dataset_path}")


if __name__ == "__main__":
    main()