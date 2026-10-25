from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
from sqlalchemy.orm import Session

from backend.app.database.models import Evidence
from backend.app.exports.csv_exporter import compute_file_sha256, export_leads_csv


YELLOW_RGB_PREFIXES = ("FFFF00", "FFF2CC", "FFFFE0", "00FFFF00", "00FFF2CC")
GREEN_RGB_PREFIXES = ("C6EFCE", "E2EFDA", "00FF00", "00C6EFCE", "00E2EFDA")


def is_green_or_formula_cell(cell) -> bool:
    if isinstance(cell.value, str) and cell.value.startswith("="):
        return True
    if cell.fill and cell.fill.start_color and cell.fill.start_color.rgb:
        rgb = str(cell.fill.start_color.rgb).upper()
        if any(rgb.endswith(g) for g in GREEN_RGB_PREFIXES):
            return True
    return False


def is_yellow_input_cell(cell) -> bool:
    if is_green_or_formula_cell(cell):
        return False
    if cell.fill and cell.fill.start_color and cell.fill.start_color.rgb:
        rgb = str(cell.fill.start_color.rgb).upper()
        if any(rgb.endswith(y) for y in YELLOW_RGB_PREFIXES):
            return True
    return True


def populate_official_workbook(
    db: Session,
    template_path: Path,
    output_path: Path,
    leads_csv_path: Path | None = None,
    include_synthetic: bool = True,
) -> dict[str, Any]:
    """Populate an supplied Excel workbook template while preserving green calculation cells, formulas, and data validations."""
    if not template_path.exists():
        return {
            "status": "BLOCKED_MISSING_TEMPLATE",
            "message": f"Official workbook template not found at '{template_path}'. Never fabricating a fake completed workbook.",
            "file_path": None,
        }

    wb = openpyxl.load_workbook(template_path)
    sheet_names = wb.sheetnames

    # Gather qualified leads via CSV helper to guarantee 100% consistency with leads.csv
    temp_csv = output_path.parent / "_tmp_workbook_sync_leads.csv"
    csv_info = export_leads_csv(db, temp_csv, include_synthetic=include_synthetic)
    import csv as pycsv

    with temp_csv.open("r", encoding="utf-8") as f:
        lead_rows = list(pycsv.DictReader(f))
    if temp_csv.exists():
        temp_csv.unlink()

    # 1. Populate Leads sheet if present
    leads_sheet_name = next(
        (s for s in sheet_names if "lead" in s.lower() or "creator" in s.lower()),
        sheet_names[0],
    )
    ws_leads = wb[leads_sheet_name]

    headers: list[str] = []
    for col_idx in range(1, ws_leads.max_column + 1):
        val = ws_leads.cell(row=1, column=col_idx).value
        if val:
            headers.append(str(val).strip())

    populated_cells = 0
    preserved_formula_cells = 0

    for row_idx, lead in enumerate(lead_rows, start=2):
        for col_idx, h_name in enumerate(headers, start=1):
            cell = ws_leads.cell(row=row_idx, column=col_idx)
            if is_green_or_formula_cell(cell):
                preserved_formula_cells += 1
                continue
            if h_name in lead:
                cell.value = lead[h_name]
                populated_cells += 1

    # 2. Populate Self-check tab if present
    self_check_name = next((s for s in sheet_names if "self" in s.lower() or "check" in s.lower()), None)
    if self_check_name:
        ws_sc = wb[self_check_name]
        evidences = db.query(Evidence).filter(Evidence.verification_status == "VERIFIED").limit(50).all()
        for idx, ev in enumerate(evidences, start=2):
            c_claim = ws_sc.cell(row=idx, column=1)
            c_link = ws_sc.cell(row=idx, column=2)
            if not is_green_or_formula_cell(c_claim):
                c_claim.value = f"{ev.criterion}: {ev.excerpt[:120]}"
            if not is_green_or_formula_cell(c_link):
                c_link.value = ev.source_url

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)

    return {
        "status": "COMPLETED",
        "sheet_names": sheet_names,
        "populated_cells": populated_cells,
        "preserved_formula_cells": preserved_formula_cells,
        "lead_rows_synced": len(lead_rows),
        "file_path": str(output_path),
        "checksum_sha256": compute_file_sha256(output_path),
        "consistent_with_leads_csv": len(lead_rows) == csv_info["record_count"],
    }
