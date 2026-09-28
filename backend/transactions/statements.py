from __future__ import annotations

from datetime import datetime


def _pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def build_statement_pdf_bytes(
    *,
    user_email: str,
    start_date: str,
    end_date: str,
    summary: dict,
    entries: list[dict],
) -> bytes:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        "gPawa Transaction Statement",
        f"Account: {user_email}",
        f"Period: {start_date} to {end_date}",
        f"Generated: {generated_at}",
        "",
        "Summary",
        f"Transactions: {summary.get('transactions_count', 0)}",
        f"Money In (UGX): {summary.get('money_in_ugx', 0):,.2f}",
        f"Money Out (UGX): {summary.get('money_out_ugx', 0):,.2f}",
        f"Net Money (UGX): {summary.get('money_net_ugx', 0):,.2f}",
        f"Units In (kWh): {summary.get('units_in_kwh', 0):,.2f}",
        f"Units Out (kWh): {summary.get('units_out_kwh', 0):,.2f}",
        f"Net Units (kWh): {summary.get('units_net_kwh', 0):,.2f}",
        "",
        "Transactions",
    ]
    for item in entries[:120]:
        tx_date = item.get("created_at") or "-"
        tx_type = item.get("transaction_type_display") or item.get("transaction_type") or "-"
        status = item.get("status") or "-"
        amount = item.get("amount")
        units = item.get("units")
        amount_txt = f"UGX {float(amount):,.2f}" if amount is not None else "-"
        units_txt = f"{float(units):,.2f} kWh" if units is not None else "-"
        lines.append(f"{tx_date} | {tx_type} | {status} | {amount_txt} | {units_txt}")

    if len(entries) > 120:
        lines.append(f"... {len(entries) - 120} more transactions not shown in this PDF.")

    stream_lines = ["BT", "/F1 10 Tf", "50 790 Td", "12 TL"]
    first = True
    for raw in lines:
        text = _pdf_escape(raw)
        if first:
            stream_lines.append(f"({text}) Tj")
            first = False
        else:
            stream_lines.append("T*")
            stream_lines.append(f"({text}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")

    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for idx, obj in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objs) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            "trailer\n"
            f"<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_pos}\n"
            "%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(pdf)
