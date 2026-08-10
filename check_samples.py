#!/usr/bin/env python3
"""Check basic.py and efficient.py against SampleTestCases.

This script stays out of the alignment math entirely:
- it runs the solver programs on each sample input
- reads the solver outputs and the provided expected outputs
- checks that the reported costs match the sample answers
- records time and memory from the solver output files
- generates a Plotly HTML report and a CSV summary

It does not define DELTA or ALPHA; those belong in the alignment solvers.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


@dataclass
class CaseResult:
    case_id: str
    input_file: Path
    expected_output_file: Path
    problem_size: int
    expected_cost: int | None
    basic_cost: int | None
    efficient_cost: int | None
    basic_ok: bool
    efficient_ok: bool
    basic_time_ms: float | None
    efficient_time_ms: float | None
    basic_memory_kb: float | None
    efficient_memory_kb: float | None
    basic_note: str
    efficient_note: str


def run_command(cmd: Sequence[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def natural_case_id(path: Path) -> str:
    m = re.search(r"(\d+)", path.stem)
    return m.group(1) if m else path.stem


def sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"(\d+)", path.stem)
    return (int(m.group(1)) if m else 10**9, path.name)


def find_cases(sample_dir: Path) -> list[tuple[Path, Path, str]]:
    inputs = sorted(sample_dir.glob("input*.txt"), key=sort_key)
    cases: list[tuple[Path, Path, str]] = []
    for inp in inputs:
        cid = natural_case_id(inp)
        expected = sample_dir / f"output{cid}.txt"
        if expected.exists():
            cases.append((inp, expected, cid))
    return cases


def parse_problem_size(input_file: Path) -> int:
    """Compute m + n from the generator file without expanding the strings."""
    with input_file.open() as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    if len(lines) < 2:
        raise ValueError(f"Input file too short: {input_file}")

    i = 0
    s0 = lines[i]
    i += 1

    s_len = len(s0)
    while i < len(lines) and lines[i].isdigit():
        s_len *= 2
        i += 1

    if i >= len(lines):
        raise ValueError(f"Could not parse second base string in {input_file}")

    t0 = lines[i]
    i += 1

    t_len = len(t0)
    while i < len(lines):
        t_len *= 2
        i += 1

    return s_len + t_len


def read_solver_output(path: Path) -> tuple[int, str, str, float | None, float | None]:
    with path.open() as f:
        lines = [ln.rstrip("\n") for ln in f]

    if len(lines) < 3:
        raise ValueError(f"Solver output has fewer than 3 lines: {path}")

    cost = int(lines[0].strip())
    ax = lines[1].strip()
    ay = lines[2].strip()
    time_ms = float(lines[3].strip()) if len(lines) >= 4 and lines[3].strip() else None
    mem_kb = float(lines[4].strip()) if len(lines) >= 5 and lines[4].strip() else None
    return cost, ax, ay, time_ms, mem_kb


def alignment_is_valid(ax: str, ay: str) -> tuple[bool, str]:
    if len(ax) != len(ay):
        return False, "alignment lengths differ"
    if not ax or not ay:
        return False, "empty alignment"
    if set(ax) - set("ACGT_") or set(ay) - set("ACGT_"):
        return False, "invalid alignment characters"
    if any(a == "_" and b == "_" for a, b in zip(ax, ay)):
        return False, "both positions are gaps in at least one column"
    return True, "OK"


def run_solver(project_root: Path, solver: Path, input_file: Path, output_file: Path) -> None:
    if solver.suffix == ".sh":
        run_command(["bash", str(solver), str(input_file), str(output_file)], cwd=project_root)
    elif solver.suffix == ".py":
        run_command([sys.executable, str(solver), str(input_file), str(output_file)], cwd=project_root)
    else:
        raise ValueError(f"Unsupported solver type: {solver}")


def make_plotly_report(results: list[CaseResult], out_html: Path) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Plotly is required. Install it with: pip install plotly") from exc

    x = [r.problem_size for r in results]
    labels = [r.case_id for r in results]
    basic_time = [r.basic_time_ms for r in results]
    efficient_time = [r.efficient_time_ms for r in results]
    basic_mem = [r.basic_memory_kb for r in results]
    efficient_mem = [r.efficient_memory_kb for r in results]
    basic_cost = [r.basic_cost for r in results]
    efficient_cost = [r.efficient_cost for r in results]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Cost by Sample Case", "CPU Time by Sample Case", "Memory by Sample Case"),
        vertical_spacing=0.08,
    )

    fig.add_trace(go.Scatter(x=x, y=basic_cost, mode="lines+markers", name="Basic cost", text=labels), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=efficient_cost, mode="lines+markers", name="Efficient cost", text=labels), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=basic_time, mode="lines+markers", name="Basic time", text=labels), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=efficient_time, mode="lines+markers", name="Efficient time", text=labels), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=basic_mem, mode="lines+markers", name="Basic memory", text=labels), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=efficient_mem, mode="lines+markers", name="Efficient memory", text=labels), row=3, col=1)

    fig.update_layout(
        title="Sample case check for basic.py and efficient.py",
        template="plotly_white",
        hovermode="x unified",
        legend_title_text="Series",
        margin=dict(l=50, r=30, t=80, b=50),
    )
    fig.update_xaxes(title_text="Problem Size (m + n)", row=3, col=1)
    fig.update_yaxes(title_text="Cost", row=1, col=1)
    fig.update_yaxes(title_text="Time (ms)", row=2, col=1)
    fig.update_yaxes(title_text="Memory (KB)", row=3, col=1)

    fig.write_html(str(out_html), include_plotlyjs="cdn")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check basic.py and efficient.py against SampleTestCases")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root directory")
    parser.add_argument("--sample-dir", type=Path, default=Path("SampleTestCases"), help="Folder with input*.txt and output*.txt")
    parser.add_argument("--basic", type=Path, default=Path("basic.py"), help="Path to basic.py")
    parser.add_argument("--efficient", type=Path, default=Path("efficient.py"), help="Path to efficient.py")
    parser.add_argument("--work-dir", type=Path, default=Path("sample_check_runs"), help="Where solver outputs are written")
    parser.add_argument("--csv", type=Path, default=Path("sample_check_report.csv"), help="CSV summary output")
    parser.add_argument("--html", type=Path, default=Path("sample_check_report.html"), help="Plotly HTML report")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    sample_dir = (project_root / args.sample_dir).resolve() if not args.sample_dir.is_absolute() else args.sample_dir.resolve()
    work_dir = (project_root / args.work_dir).resolve() if not args.work_dir.is_absolute() else args.work_dir.resolve()
    basic_path = (project_root / args.basic).resolve() if not args.basic.is_absolute() else args.basic.resolve()
    efficient_path = (project_root / args.efficient).resolve() if not args.efficient.is_absolute() else args.efficient.resolve()
    csv_path = (project_root / args.csv).resolve() if not args.csv.is_absolute() else args.csv.resolve()
    html_path = (project_root / args.html).resolve() if not args.html.is_absolute() else args.html.resolve()

    work_dir.mkdir(parents=True, exist_ok=True)

    if not sample_dir.exists():
        raise SystemExit(f"SampleTestCases folder not found: {sample_dir}")
    if not basic_path.exists():
        raise SystemExit(f"basic.py not found: {basic_path}")
    if not efficient_path.exists():
        raise SystemExit(f"efficient.py not found: {efficient_path}")

    cases = find_cases(sample_dir)
    if not cases:
        raise SystemExit(f"No matching input/output sample cases found in {sample_dir}")

    results: list[CaseResult] = []

    for input_file, expected_output_file, case_id in cases:
        problem_size = parse_problem_size(input_file)

        basic_out = work_dir / f"case{case_id}_basic.out"
        efficient_out = work_dir / f"case{case_id}_efficient.out"

        run_solver(project_root, basic_path, input_file, basic_out)
        run_solver(project_root, efficient_path, input_file, efficient_out)

        expected_cost, expected_ax, expected_ay, _, _ = read_solver_output(expected_output_file)
        basic_cost, basic_ax, basic_ay, basic_time_ms, basic_mem_kb = read_solver_output(basic_out)
        efficient_cost, efficient_ax, efficient_ay, efficient_time_ms, efficient_mem_kb = read_solver_output(efficient_out)

        basic_valid, basic_valid_note = alignment_is_valid(basic_ax, basic_ay)
        efficient_valid, efficient_valid_note = alignment_is_valid(efficient_ax, efficient_ay)

        basic_ok = basic_cost == expected_cost and basic_valid
        efficient_ok = efficient_cost == expected_cost and efficient_valid

        results.append(
            CaseResult(
                case_id=case_id,
                input_file=input_file,
                expected_output_file=expected_output_file,
                problem_size=problem_size,
                expected_cost=expected_cost,
                basic_cost=basic_cost,
                efficient_cost=efficient_cost,
                basic_ok=basic_ok,
                efficient_ok=efficient_ok,
                basic_time_ms=basic_time_ms,
                efficient_time_ms=efficient_time_ms,
                basic_memory_kb=basic_mem_kb,
                efficient_memory_kb=efficient_mem_kb,
                basic_note=("OK" if basic_ok else f"expected cost {expected_cost}, got {basic_cost}; {basic_valid_note}"),
                efficient_note=("OK" if efficient_ok else f"expected cost {expected_cost}, got {efficient_cost}; {efficient_valid_note}"),
            )
        )

    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id",
            "input_file",
            "expected_output_file",
            "problem_size",
            "expected_cost",
            "basic_cost",
            "efficient_cost",
            "basic_ok",
            "efficient_ok",
            "basic_time_ms",
            "efficient_time_ms",
            "basic_memory_kb",
            "efficient_memory_kb",
        ])
        for r in results:
            writer.writerow([
                r.case_id,
                r.input_file.name,
                r.expected_output_file.name,
                r.problem_size,
                r.expected_cost,
                r.basic_cost,
                r.efficient_cost,
                r.basic_ok,
                r.efficient_ok,
                "" if r.basic_time_ms is None else f"{r.basic_time_ms:.6f}",
                "" if r.efficient_time_ms is None else f"{r.efficient_time_ms:.6f}",
                "" if r.basic_memory_kb is None else f"{r.basic_memory_kb:.6f}",
                "" if r.efficient_memory_kb is None else f"{r.efficient_memory_kb:.6f}",
            ])

    make_plotly_report(results, html_path)

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {html_path}")
    print()
    for r in results:
        status = "PASS" if (r.basic_ok and r.efficient_ok) else "FAIL"
        print(f"Case {r.case_id}: {status}")
        print(f"  problem size: {r.problem_size}")
        print(f"  expected cost: {r.expected_cost}")
        print(f"  basic:     cost={r.basic_cost}, time={r.basic_time_ms}, memory={r.basic_memory_kb} | {r.basic_note}")
        print(f"  efficient: cost={r.efficient_cost}, time={r.efficient_time_ms}, memory={r.efficient_memory_kb} | {r.efficient_note}")
        print()


if __name__ == "__main__":
    main()
