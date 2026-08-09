#!/usr/bin/env python3
"""Memory-efficient (Hirschberg) sequence alignment (CSCI 570 Summer 2026).

Falls back to full basic DP when m + n <= BASE_CASE_THRESHOLD.
"""

import resource
import sys
import time

DELTA = 30
ALPHA = {
    ("A", "A"): 0,
    ("A", "C"): 110,
    ("A", "G"): 48,
    ("A", "T"): 94,
    ("C", "A"): 110,
    ("C", "C"): 0,
    ("C", "G"): 118,
    ("C", "T"): 48,
    ("G", "A"): 48,
    ("G", "C"): 118,
    ("G", "G"): 0,
    ("G", "T"): 110,
    ("T", "A"): 94,
    ("T", "C"): 48,
    ("T", "G"): 110,
    ("T", "T"): 0,
}

# Switch from divide-and-conquer to full DP below this problem size (m + n).
BASE_CASE_THRESHOLD = 2000


def _grow(base, indices):
    """Repeatedly double `base` by inserting a copy of the current string
    right after each 0-indexed position in `indices`, in order."""
    s = base
    for n in indices:
        s = s[: n + 1] + s + s[n + 1 :]
    return s


def parse_and_generate(path):
    """Read the generator input file and produce the two strings to align.

    Format: s0, then s's insertion indices (one per line, until a
    non-digit line is hit), then t0, then t's insertion indices (rest of
    the file). Returns (X, Y) = (_grow(s0, s_indices), _grow(t0, t_indices)).
    """
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    i = 0
    s0 = lines[i]
    i += 1

    s_indices = []
    while i < len(lines) and lines[i].isdigit():
        s_indices.append(int(lines[i]))
        i += 1

    t0 = lines[i]
    i += 1
    t_indices = [int(x) for x in lines[i:]]

    return _grow(s0, s_indices), _grow(t0, t_indices)


def mismatch(a, b):
    return ALPHA[(a, b)]


def basic_align(X, Y):
    """Full DP + traceback. Returns (cost, aligned_X, aligned_Y)."""
    m, n = len(X), len(Y)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        dp[i][0] = i * DELTA
    for j in range(1, n + 1):
        dp[0][j] = j * DELTA

    for i in range(1, m + 1):
        xi = X[i - 1]
        row = dp[i]
        prev = dp[i - 1]
        for j in range(1, n + 1):
            row[j] = min(
                prev[j - 1] + mismatch(xi, Y[j - 1]),
                prev[j] + DELTA,
                row[j - 1] + DELTA,
            )

    ax, ay = [], []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + mismatch(X[i - 1], Y[j - 1]):
            ax.append(X[i - 1])
            ay.append(Y[j - 1])
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + DELTA:
            ax.append(X[i - 1])
            ay.append("_")
            i -= 1
        else:
            ax.append("_")
            ay.append(Y[j - 1])
            j -= 1

    ax.reverse()
    ay.reverse()
    return dp[m][n], "".join(ax), "".join(ay)


def nw_score(X, Y):
    """Linear-space forward scores: S[i] = OPT(X[:i], Y)."""
    m, n = len(X), len(Y)
    prev = [i * DELTA for i in range(m + 1)]
    for j in range(1, n + 1):
        curr = [0] * (m + 1)
        curr[0] = j * DELTA
        yj = Y[j - 1]
        for i in range(1, m + 1):
            curr[i] = min(
                prev[i - 1] + mismatch(X[i - 1], yj),
                prev[i] + DELTA,
                curr[i - 1] + DELTA,
            )
        prev = curr
    return prev


def efficient_align(X, Y):
    """Hirschberg divide-and-conquer. Returns (cost, aligned_X, aligned_Y)."""
    m, n = len(X), len(Y)

    if m == 0:
        return n * DELTA, "_" * n, Y
    if n == 0:
        return m * DELTA, X, "_" * m
    if m + n <= BASE_CASE_THRESHOLD:
        return basic_align(X, Y)

    mid = n // 2
    fwd = nw_score(X, Y[:mid])
    bwd = nw_score(X[::-1], Y[mid:][::-1])

    split = 0
    best = fwd[0] + bwd[m]
    for i in range(1, m + 1):
        cost = fwd[i] + bwd[m - i]
        if cost < best:
            best = cost
            split = i

    left_cost, left_x, left_y = efficient_align(X[:split], Y[:mid])
    right_cost, right_x, right_y = efficient_align(X[split:], Y[mid:])
    return left_cost + right_cost, left_x + right_x, left_y + right_y


def process_memory_kb():
    """Peak RSS in KB (ru_maxrss is KB on Linux, bytes on macOS)."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / 1024.0
    return float(usage)


def main():
    input_path = sys.argv[1]
    output_path = sys.argv[2]

    X, Y = parse_and_generate(input_path)

    start = time.time()
    cost, align_x, align_y = efficient_align(X, Y)
    elapsed_ms = (time.time() - start) * 1000.0
    mem_kb = process_memory_kb()

    with open(output_path, "w") as f:
        f.write(f"{cost}\n")
        f.write(f"{align_x}\n")
        f.write(f"{align_y}\n")
        f.write(f"{elapsed_ms}\n")
        f.write(f"{mem_kb}\n")


if __name__ == "__main__":
    main()
