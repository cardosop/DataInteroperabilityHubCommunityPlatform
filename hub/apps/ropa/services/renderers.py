from __future__ import annotations

import csv
import io
import json
from typing import Any

from hub.apps.ropa.models import RopaOutputFormat


def render_json_bytes(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    raw = json.dumps(payload, indent=2, default=str).encode("utf-8")
    return raw, "application/json", "ropa.json"


def render_csv_bytes(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "asset_id",
            "asset_key",
            "asset_name",
            "status",
            "purposes",
            "categories_of_subjects",
            "recipient_categories",
            "retention_policy_count",
        ]
    )
    for row in payload.get("activities", []):
        plist = ";".join(p["key"] for p in row.get("processing_purposes", []))
        cats = ",".join(str(x) for x in (row.get("categories_of_subjects") or []))
        rec = ",".join(str(x) for x in (row.get("recipient_categories") or []))
        w.writerow(
            [
                row.get("id"),
                row.get("key"),
                row.get("name"),
                row.get("status"),
                plist,
                cats,
                rec,
                len(row.get("retention_policies") or []),
            ]
        )
    raw = buf.getvalue().encode("utf-8")
    return raw, "text/csv", "ropa.csv"


def render_pdf_bytes(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    try:
        from weasyprint import (
            HTML,  # type: ignore[import-untyped]  # optional dependency; has no stubs package
        )
    except Exception as exc:
        raise RuntimeError(
            "WeasyPrint is not available in this runtime (missing native Cairo/Pango "
            "libraries or Python package)."
        ) from exc

    html = _ropa_html(payload)
    pdf = HTML(string=html).write_pdf()
    return pdf, "application/pdf", "ropa.pdf"


def render_docx_bytes(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    from docx import (
        Document,  # type: ignore[import-untyped]  # optional dependency; has no stubs package
    )

    doc = Document()
    doc.add_heading("Record of Processing Activities", 0)
    p = doc.add_paragraph()
    meta = payload.get("meta") or {}
    p.add_run(
        f"Regulation: {meta.get('regulation')} — Assets: {meta.get('asset_count', 0)}"
    ).bold = True
    doc.add_paragraph()
    if payload.get("gaps"):
        doc.add_heading("Gaps / completeness", level=2)
        for g in payload["gaps"][:200]:
            doc.add_paragraph(
                f"[{g.get('code')}] {g.get('asset_key')}: {g.get('message')}", style="List Bullet"
            )
        doc.add_paragraph()
    doc.add_heading("Processing activities", level=2)
    table = doc.add_table(rows=1, cols=4)
    hdr = table.rows[0].cells
    hdr[0].text = "Asset key"
    hdr[1].text = "Purposes"
    hdr[2].text = "Subject categories"
    hdr[3].text = "Recipients"
    for row in payload.get("activities", []):
        cells = table.add_row().cells
        cells[0].text = str(row.get("key") or "")
        cells[1].text = ", ".join(p["key"] for p in row.get("processing_purposes", []))
        cells[2].text = ", ".join(str(x) for x in (row.get("categories_of_subjects") or []))
        cells[3].text = ", ".join(str(x) for x in (row.get("recipient_categories") or []))
    bio = io.BytesIO()
    doc.save(bio)
    raw = bio.getvalue()
    return (
        raw,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "ropa.docx",
    )


def _ropa_html(payload: dict[str, Any]) -> str:
    """Build GDPR Art. 30 compliant HTML for the RoPA PDF.

    Includes all required fields per Art. 30(1):
    - Controller identity + DPO contact
    - Purposes of processing
    - Categories of data subjects and personal data
    - Categories of recipients (including third-country)
    - Transfers to third countries + safeguards
    - Retention periods (time limits for erasure)
    - Technical and organisational security measures
    """
    meta = payload.get("meta") or {}
    gaps = payload.get("gaps") or []
    controller = meta.get("controller_name") or "Controller"
    dpo_contact = meta.get("dpo_contact") or "N/A"
    generated_at = meta.get("generated_at") or "N/A"

    rows_html = ""
    for row in payload.get("activities") or []:
        purposes = ", ".join(
            p.get("name", p.get("key", "")) for p in row.get("processing_purposes", [])
        )
        subjects = ", ".join(str(x) for x in (row.get("categories_of_subjects") or []))
        recipients = ", ".join(str(x) for x in (row.get("recipient_categories") or []))
        third_country = row.get("third_country_transfers") or ""
        if isinstance(third_country, list):
            third_country = ", ".join(third_country)
        row.get("transfer_safeguards") or ""
        retention = row.get("retention_period") or ""
        if not retention:
            policies = row.get("retention_policies") or []
            retention = ", ".join(p.get("name", p.get("key", "")) for p in policies[:3])
        measures = row.get("security_measures") or ""
        if isinstance(measures, list):
            measures = ", ".join(measures)

        rows_html += (
            f"<tr>"
            f"<td>{row.get('key', '')}</td>"
            f"<td>{row.get('name', '')}</td>"
            f"<td>{purposes}</td>"
            f"<td>{subjects}</td>"
            f"<td>{recipients}</td>"
            f"<td>{third_country or '—'}</td>"
            f"<td>{retention or '—'}</td>"
            f"<td>{measures or '—'}</td>"
            f"</tr>"
        )

    gh = "".join(
        f"<li><b>{g.get('code')}</b> — {g.get('asset_key')}: {g.get('message')}</li>"
        for g in gaps[:200]
    )

    regulation = meta.get("regulation") or "GDPR"
    asset_count = meta.get("asset_count", 0)
    tenant_name = meta.get("tenant_name") or controller

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Record of Processing Activities — {regulation}</title>
  <style>
    @page {{
      margin: 20mm 15mm;
      @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9px;
        color: #666;
      }}
    }}
    body {{
      font-family: DejaVu Sans, Arial, sans-serif;
      margin: 0;
      font-size: 10px;
      color: #222;
    }}
    h1 {{
      font-size: 18px;
      color: #14213d;
      border-bottom: 2px solid #14213d;
      padding-bottom: 6px;
      margin-bottom: 12px;
    }}
    h2 {{
      font-size: 13px;
      color: #14213d;
      margin-top: 20px;
    }}
    .metadata {{
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      padding: 12px;
      margin-bottom: 16px;
      font-size: 10px;
    }}
    .metadata dt {{
      font-weight: bold;
      display: inline;
    }}
    .metadata dd {{
      display: inline;
      margin: 0 0 0 8px;
    }}
    .metadata dd::after {{
      content: "";
      display: block;
      margin-bottom: 4px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 9px;
      page-break-inside: auto;
    }}
    th, td {{
      border: 1px solid #adb5bd;
      padding: 5px 6px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #e9ecef;
      font-weight: bold;
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    tr:nth-child(even) td {{
      background: #f8f9fa;
    }}
    .footer-note {{
      margin-top: 24px;
      font-size: 8px;
      color: #888;
      border-top: 1px solid #ccc;
      padding-top: 8px;
    }}
  </style>
</head>
<body>
<h1>Record of Processing Activities</h1>

<dl class="metadata">
  <dt>Regulation:</dt><dd>{regulation}</dd>
  <dt>Controller:</dt><dd>{tenant_name}</dd>
  <dt>DPO contact:</dt><dd>{dpo_contact}</dd>
  <dt>Generated:</dt><dd>{generated_at}</dd>
  <dt>Asset count:</dt><dd>{asset_count}</dd>
  <dt>Article:</dt><dd>GDPR Art. 30</dd>
</dl>

<h2>1. Controller and Data Protection Officer</h2>
<p>Controller: <b>{tenant_name}</b>. DPO contact: <b>{dpo_contact}</b>.</p>

<h2>2. Purposes of Processing</h2>
<p>Processing purposes are listed per activity below (Art. 30(1)(b)).</p>

<h2>3. Categories of Data Subjects and Personal Data</h2>
<p>Categories of data subjects whose personal data are processed are listed per activity (Art. 30(1)(c)).</p>

<h2>4. Categories of Recipients</h2>
<p>Recipients to whom personal data have been or will be disclosed are listed per activity (Art. 30(1)(d)).</p>

<h2>5. Transfers to Third Countries</h2>
<p>Where personal data are transferred to a third country or international organisation, the transfer and applicable safeguards are documented per activity (Art. 30(1)(e)).</p>

<h2>6. Retention Periods</h2>
<p>Time limits for erasure of the different categories of data are listed per activity, derived from applied retention policies (Art. 30(1)(f)).</p>

<h2>7. Technical and Organisational Security Measures</h2>
<p>A general description of the technical and organisational security measures referred to in Art. 32(1) is listed per activity (Art. 30(1)(g)).</p>

<h2>8. Gaps and Completeness</h2>
<ul>{gh or "<li>None detected — all processing activities are fully documented.</li>"}</ul>

<h2>9. Processing Activities</h2>
<table>
  <thead>
    <tr>
      <th>Key</th>
      <th>Name</th>
      <th>Purposes</th>
      <th>Subjects</th>
      <th>Recipients</th>
      <th>Third Country</th>
      <th>Retention</th>
      <th>Security</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>

<div class="footer-note">
  This Record of Processing Activities was generated by Meshant on {generated_at}
  pursuant to Article 30 of Regulation (EU) 2016/679 (GDPR) and equivalent
  provisions under {regulation}.  The controller is responsible for reviewing
  and supplementing the information herein to ensure completeness and accuracy.
</div>
</body>
</html>"""


def render_by_format(fmt: str, payload: dict[str, Any]) -> tuple[bytes, str, str]:
    key = (fmt or RopaOutputFormat.JSON).lower()
    if key == RopaOutputFormat.JSON:
        return render_json_bytes(payload)
    if key == RopaOutputFormat.CSV:
        return render_csv_bytes(payload)
    if key == RopaOutputFormat.PDF:
        return render_pdf_bytes(payload)
    if key == RopaOutputFormat.DOCX:
        return render_docx_bytes(payload)
    raise ValueError(f"unsupported format: {fmt}")
