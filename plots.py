#!/usr/bin/env python3
"""Generate Plotly graphs for the CSCI 570 sequence alignment project.

This script:
1) Reads every input file in a Datapoints/ folder.
2) Runs the basic and memory-efficient implementations on each input.
3) Collects problem size (m + n), CPU time, and memory usage.
4) Writes a CSV table and two Plotly graphs (HTML + optional PNG).

Expected project layout:
    project_root/
        basic.py
        efficient.sh   (or efficient.py)
        Datapoints/
            in1.txt
            in2.txt
            ...

Usage:
    python3 plots.py
    python3 plots.py --datapoints Datapoints --output-dir plots_out
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

def _grow(base: str, indices: Iterable[int]) -> str:
    s = base
    for n in indices:
        s = s[: n + 1] + s + s[n + 1 :]
    return s


def parse_and_generate(path: Path) -> Tuple[str, str]:
    """Parse a generator input file and produce the two expanded strings."""
    with path.open() as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    if len(lines) < 2:
        raise ValueError(f"Input file {path} is too short")

    i = 0
    s0 = lines[i]
    i += 1

    s_indices: List[int] = []
    while i < len(lines) and lines[i].isdigit():
        s_indices.append(int(lines[i]))
        i += 1

    if i >= len(lines):
        raise ValueError(f"Could not find second base string in {path}")

    t0 = lines[i]
    i += 1
    t_indices = [int(x) for x in lines[i:]]

    return _grow(s0, s_indices), _grow(t0, t_indices)


def natural_input_sort(path: Path) -> Tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    return (int(match.group(1)) if match else 10**9, path.name)


def run_command(cmd: List[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def read_output_metrics(output_path: Path) -> Tuple[float, float]:
    """Read elapsed time (line 4) and memory (line 5) from a project output file."""
    with output_path.open() as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    if len(lines) < 5:
        raise ValueError(f"Output file {output_path} does not contain 5 lines")

    elapsed_ms = float(lines[3])
    mem_kb = float(lines[4])
    return elapsed_ms, mem_kb


def ensure_plotly():
    try:
        import plotly.graph_objects as go  # type: ignore
        from plotly.subplots import make_subplots  # noqa: F401  # type: ignore
        return go
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "Plotly is required to run this script. Install it with: pip install plotly"
        ) from exc


def build_line_plot(go, title: str, y_label: str, x_values, basic_values, efficient_values):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=basic_values,
            mode="lines+markers",
            name="Basic",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=efficient_values,
            mode="lines+markers",
            name="Efficient",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Problem Size (m + n)",
        yaxis_title=y_label,
        template="plotly_white",
        hovermode="x unified",
        legend_title_text="Algorithm",
        margin=dict(l=50, r=30, t=70, b=50),
    )
    return fig


def try_write_png(fig, png_path: Path) -> bool:
    try:
        fig.write_image(str(png_path))
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Plotly charts for CSCI 570 datapoints")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root directory")
    parser.add_argument(
        "--datapoints",
        type=Path,
        default=Path("Datapoints"),
        help="Folder containing input files (default: Datapoints)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("plot_outputs"),
        help="Directory where charts and CSV will be written",
    )
    parser.add_argument(
        "--basic-script",
        type=Path,
        default=Path("basic.py"),
        help="Basic implementation script (default: basic.py)",
    )
    parser.add_argument(
        "--efficient-script",
        type=Path,
        default=Path("efficient.sh"),
        help="Memory-efficient wrapper script (default: efficient.sh)",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Only build plots from an existing results.csv in output-dir",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    datapoints_dir = (project_root / args.datapoints).resolve() if not args.datapoints.is_absolute() else args.datapoints.resolve()
    output_dir = (project_root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()
    basic_script = (project_root / args.basic_script).resolve() if not args.basic_script.is_absolute() else args.basic_script.resolve()
    efficient_script = (project_root / args.efficient_script).resolve() if not args.efficient_script.is_absolute() else args.efficient_script.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    results_csv = output_dir / "results.csv"

    if not args.skip_run:
        if not datapoints_dir.exists():
            raise SystemExit(f"Datapoints folder not found: {datapoints_dir}")
        if not basic_script.exists():
            raise SystemExit(f"basic.py not found: {basic_script}")
        if not efficient_script.exists() and not (project_root / "efficient.py").exists():
            raise SystemExit(
                f"Neither {efficient_script.name} nor efficient.py was found in {project_root}"
            )

        input_files = sorted(datapoints_dir.glob("*.txt"), key=natural_input_sort)
        if not input_files:
            raise SystemExit(f"No .txt files found in {datapoints_dir}")

        records = []
        for input_path in input_files:
            X, Y = parse_and_generate(input_path)
            problem_size = len(X) + len(Y)

            basic_out = output_dir / f"{input_path.stem}_basic.out"
            efficient_out = output_dir / f"{input_path.stem}_efficient.out"

            # Run basic.py
            run_command([sys.executable, str(basic_script), str(input_path), str(basic_out)], cwd=project_root)
            basic_time_ms, basic_mem_kb = read_output_metrics(basic_out)

            # Run memory-efficient implementation (prefer the provided shell wrapper)
            if efficient_script.exists():
                run_command(["bash", str(efficient_script), str(input_path), str(efficient_out)], cwd=project_root)
            else:
                efficient_py = project_root / "efficient.py"
                run_command([sys.executable, str(efficient_py), str(input_path), str(efficient_out)], cwd=project_root)
            efficient_time_ms, efficient_mem_kb = read_output_metrics(efficient_out)

            records.append(
                {
                    "file": input_path.name,
                    "problem_size": problem_size,
                    "basic_time_ms": basic_time_ms,
                    "efficient_time_ms": efficient_time_ms,
                    "basic_memory_kb": basic_mem_kb,
                    "efficient_memory_kb": efficient_mem_kb,
                }
            )

        records.sort(key=lambda r: (r["problem_size"], r["file"]))

        with results_csv.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "file",
                    "problem_size",
                    "basic_time_ms",
                    "efficient_time_ms",
                    "basic_memory_kb",
                    "efficient_memory_kb",
                ],
            )
            writer.writeheader()
            writer.writerows(records)
    else:
        if not results_csv.exists():
            raise SystemExit(f"results.csv not found in {output_dir}. Remove --skip-run or generate results first.")
        records = []
        with results_csv.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(
                    {
                        "file": row["file"],
                        "problem_size": int(float(row["problem_size"])),
                        "basic_time_ms": float(row["basic_time_ms"]),
                        "efficient_time_ms": float(row["efficient_time_ms"]),
                        "basic_memory_kb": float(row["basic_memory_kb"]),
                        "efficient_memory_kb": float(row["efficient_memory_kb"]),
                    }
                )

    # Sort for plotting
    records.sort(key=lambda r: (r["problem_size"], r["file"]))
    x_values = [r["problem_size"] for r in records]
    basic_time = [r["basic_time_ms"] for r in records]
    efficient_time = [r["efficient_time_ms"] for r in records]
    basic_mem = [r["basic_memory_kb"] for r in records]
    efficient_mem = [r["efficient_memory_kb"] for r in records]

    # Save a clean table for Summary.pdf
    table_path = output_dir / "datapoints_table.csv"
    with table_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["M+N", "Time in MS (Basic)", "Time in MS (Efficient)", "Memory in KB (Basic)", "Memory in KB (Efficient)"])
        for r in records:
            writer.writerow([
                r["problem_size"],
                f'{r["basic_time_ms"]:.4f}',
                f'{r["efficient_time_ms"]:.4f}',
                f'{r["basic_memory_kb"]:.4f}',
                f'{r["efficient_memory_kb"]:.4f}',
            ])

    go = ensure_plotly()
    time_fig = build_line_plot(go, "Time vs Problem Size", "Time (ms)", x_values, basic_time, efficient_time)
    mem_fig = build_line_plot(go, "Memory vs Problem Size", "Memory (KB)", x_values, basic_mem, efficient_mem)

    time_html = output_dir / "time_vs_problem_size.html"
    mem_html = output_dir / "memory_vs_problem_size.html"
    time_fig.write_html(str(time_html), include_plotlyjs="cdn")
    mem_fig.write_html(str(mem_html), include_plotlyjs="cdn")

    time_png = output_dir / "time_vs_problem_size.png"
    mem_png = output_dir / "memory_vs_problem_size.png"
    time_png_ok = try_write_png(time_fig, time_png)
    mem_png_ok = try_write_png(mem_fig, mem_png)

    print(f"Wrote: {results_csv}")
    print(f"Wrote: {table_path}")
    print(f"Wrote: {time_html}")
    print(f"Wrote: {mem_html}")
    if time_png_ok:
        print(f"Wrote: {time_png}")
    else:
        print("PNG export for time plot skipped (kaleido not installed).")
    if mem_png_ok:
        print(f"Wrote: {mem_png}")
    else:
        print("PNG export for memory plot skipped (kaleido not installed).")


if __name__ == "__main__":
    main()
