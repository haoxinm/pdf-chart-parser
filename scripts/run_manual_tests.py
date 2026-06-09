#!/usr/bin/env python3
"""Manual test harness: run extraction over fixtures and compare against expected values.

Default mode: in-process (no MCP transport, no LLM).
Optional --http URL: invoke over streamable-http against a running MCP server.

Usage:
    uv run python scripts/run_manual_tests.py
    uv run python scripts/run_manual_tests.py --http http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PDFS_DIR = REPO_ROOT / "tests" / "fixtures" / "pdfs"
EXPECTED_DIR = REPO_ROOT / "tests" / "fixtures" / "expected"
OUTPUT_DIR = REPO_ROOT / "manual_test_output"


def run_in_process(pdf_path: Path) -> dict:
    from pdf_chart_parser.pipeline import extract_usage_chart

    return extract_usage_chart(pdf_path=str(pdf_path), return_annotated_image=True)


def run_over_http(pdf_path: Path, server_url: str) -> dict:
    import httpx

    # Use MCP client SDK if available, otherwise fall back to raw HTTP
    try:
        import base64

        pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode()
        # Minimal MCP streamable-http call via httpx
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "extract_usage_chart",
                "arguments": {
                    "pdf_base64": pdf_b64,
                    "return_annotated_image": True,
                },
            },
        }
        resp = httpx.post(f"{server_url}/mcp", json=payload, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        content = body.get("result", {}).get("content", [])
        for item in content:
            if item.get("type") == "text":
                return json.loads(item["text"])
        return {"chart_found": False, "method": "failed", "error": "no text content in response"}
    except Exception as exc:
        return {"chart_found": False, "method": "failed", "error": str(exc)}


def compare(result: dict, expected: dict, stem: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not result.get("chart_found"):
        errors.append("chart not found")
        return False, errors

    if result.get("chart_type") != expected.get("chart_type"):
        errors.append(
            f"chart_type mismatch: got {result.get('chart_type')!r}, "
            f"expected {expected.get('chart_type')!r}"
        )

    tolerance = expected.get("tolerance_pct", 2.0) / 100.0

    for exp_series in expected.get("series", []):
        matching = [s for s in result.get("series", []) if s["type"] == exp_series["type"]]
        if not matching:
            errors.append(f"missing {exp_series['type']} series")
            continue

        act_pts = {p["x_label"]: p["value"] for p in matching[0].get("points", [])}
        n_pass = n_total = 0
        for exp_pt in exp_series["points"]:
            lbl = exp_pt["x_label"]
            if lbl not in act_pts:
                continue
            exp_val = exp_pt["value"]
            act_val = act_pts[lbl]
            if exp_val == 0:
                continue
            n_total += 1
            pct_err = abs(act_val - exp_val) / abs(exp_val)
            if pct_err <= tolerance:
                n_pass += 1
            else:
                errors.append(
                    f"{exp_series['type']} {lbl}: got {act_val:.2f}, "
                    f"expected {exp_val:.2f} (err {pct_err*100:.1f}%)"
                )

        if n_total > 0 and n_pass < int(n_total * 0.9):
            errors.append(
                f"{exp_series['type']}: only {n_pass}/{n_total} within "
                f"{tolerance*100:.1f}% tolerance"
            )

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual test harness for pdf-chart-parser")
    parser.add_argument("--http", metavar="URL", help="Run against HTTP MCP server at this URL")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    pdfs = sorted(PDFS_DIR.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in tests/fixtures/pdfs/ — run generate_synthetic.py first.")
        return 1

    rows: list[tuple[str, str, str]] = []
    overall_pass = True

    for pdf in pdfs:
        stem = pdf.stem
        print(f"  Processing {pdf.name}...")

        if args.http:
            result = run_over_http(pdf, args.http)
        else:
            result = run_in_process(pdf)

        # Write JSON output
        png: bytes | None = result.pop("annotated_png", None)
        (OUTPUT_DIR / f"{stem}.json").write_text(json.dumps(result, indent=2))

        # Write annotated PNG
        if png:
            (OUTPUT_DIR / f"{stem}.annotated.png").write_bytes(png)

        # Compare against expected if it exists
        expected_path = EXPECTED_DIR / f"{stem}.json"
        if expected_path.exists():
            expected = json.loads(expected_path.read_text())
            ok, errors = compare(result, expected, stem)
            status = "PASS" if ok else "FAIL"
            if not ok:
                overall_pass = False
                for err in errors:
                    print(f"    [!] {err}")
        else:
            status = "NO_EXPECTED"

        method = result.get("method", "?")
        chart_type = result.get("chart_type", "?")
        rows.append((pdf.name, f"{method}/{chart_type}", status))

    # Print summary table
    print()
    print(f"{'PDF':<35} {'Method/Type':<20} {'Status'}")
    print("-" * 65)
    for name, info, status in rows:
        print(f"{name:<35} {info:<20} {status}")
    print()
    print(f"Output written to {OUTPUT_DIR}/")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
