#!/usr/bin/env python3
"""Offline evaluation harness for data-grounded enterprise agents.

Loads a JSONL eval set, runs a configurable suite of evaluators over every
case, prints a per-case and aggregate report, optionally writes JSON/CSV
artefacts, and exits non-zero when the aggregate score falls below a threshold
so it can be dropped straight into CI as a regression gate.

Usage
-----
::

    python3 evaluation/eval_framework.py --eval-set evaluation/sample_eval_set.jsonl
    python3 evaluation/eval_framework.py \\
        --eval-set evaluation/sample_eval_set.jsonl \\
        --out build/eval --fail-under 0.80

Eval-set format (one JSON object per line)::

    {
      "id": "eval-001",
      "question": "...",
      "expected_answer": "...",
      "expected_sources": ["C1"],
      "retrieved_context": [
        {"id": "C1", "source": "...", "dataset": "...", "certified": true,
         "as_of": "2026-08-09T22:00:00Z", "owner": "...", "content": "..."}
      ],
      "generated_answer": "...",
      "metadata": {"expected_behaviour": "answer", "as_of_tolerance_days": 2}
    }

Nothing in this module requires a model endpoint, an API key or a network
connection. pandas is optional and only used to prettify CSV output if present.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# Support both `python3 evaluation/eval_framework.py` (script mode, sibling
# import) and `python3 -m evaluation.eval_framework` (package mode).
try:  # pragma: no cover - trivial import shim
    from metrics import EvalCase, EvalResult, Evaluator, select_evaluators
except ImportError:  # pragma: no cover
    from evaluation.metrics import EvalCase, EvalResult, Evaluator, select_evaluators

LOGGER = logging.getLogger("eval_framework")

DEFAULT_FAIL_UNDER = 0.75


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------


@dataclass
class CaseReport:
    """All evaluator results for a single case, plus its weighted overall."""

    case_id: str
    question: str
    results: list[EvalResult] = field(default_factory=list)
    overall: float = 0.0

    def score_map(self) -> dict[str, float]:
        """Evaluator name -> score."""
        return {result.evaluator: result.score for result in self.results}

    def failures(self, threshold: float) -> list[EvalResult]:
        """Results scoring below ``threshold``, worst first."""
        return sorted(
            (r for r in self.results if r.score < threshold), key=lambda r: r.score
        )

    def as_dict(self) -> dict[str, Any]:
        """JSON-serialisable view."""
        return {
            "case_id": self.case_id,
            "question": self.question,
            "overall": round(self.overall, 4),
            "results": [result.as_dict() for result in self.results],
        }


@dataclass
class RunReport:
    """The whole run: per-case reports plus aggregates."""

    eval_set: str
    generated_at: str
    cases: list[CaseReport] = field(default_factory=list)
    aggregate: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """JSON-serialisable view."""
        return {
            "eval_set": self.eval_set,
            "generated_at": self.generated_at,
            "case_count": len(self.cases),
            "overall": round(self.overall, 4),
            "aggregate": {name: round(value, 4) for name, value in self.aggregate.items()},
            "cases": [case.as_dict() for case in self.cases],
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_eval_set(path: Path) -> list[EvalCase]:
    """Read a JSONL eval set into :class:`EvalCase` objects.

    Blank lines and ``#``-prefixed comment lines are ignored so eval sets stay
    reviewable in a pull request. A malformed line raises with its line number
    rather than failing silently.
    """
    if not path.exists():
        raise FileNotFoundError(f"Eval set not found: {path}")

    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON -- {exc}") from exc
            if not isinstance(raw, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            cases.append(EvalCase.from_dict(raw))

    if not cases:
        raise ValueError(f"Eval set {path} contained no cases")
    LOGGER.info("Loaded %d case(s) from %s", len(cases), path)
    return cases


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class EvalRunner:
    """Applies a suite of evaluators to a set of cases and aggregates scores."""

    def __init__(self, evaluators: Sequence[Evaluator], case_threshold: float = 0.7) -> None:
        if not evaluators:
            raise ValueError("At least one evaluator is required")
        self.evaluators = list(evaluators)
        self.case_threshold = case_threshold

    @property
    def evaluator_names(self) -> list[str]:
        """Report column order."""
        return [evaluator.name for evaluator in self.evaluators]

    def run_case(self, case: EvalCase) -> CaseReport:
        """Evaluate one case, isolating evaluator errors so one bug cannot abort a run."""
        results: list[EvalResult] = []
        for evaluator in self.evaluators:
            try:
                result = evaluator.evaluate(case)
            except Exception as exc:  # noqa: BLE001 - deliberate isolation boundary
                LOGGER.exception("Evaluator %s failed on case %s", evaluator.name, case.id)
                result = EvalResult(
                    evaluator.name, 0.0, f"evaluator raised {type(exc).__name__}: {exc}"
                )
            results.append(result)

        weights = [evaluator.weight for evaluator in self.evaluators]
        total_weight = sum(weights) or 1.0
        overall = sum(r.score * w for r, w in zip(results, weights)) / total_weight
        return CaseReport(case_id=case.id, question=case.question, results=results, overall=overall)

    def run(self, cases: Iterable[EvalCase], eval_set_name: str = "<memory>") -> RunReport:
        """Evaluate every case and compute per-evaluator and overall aggregates."""
        case_reports = [self.run_case(case) for case in cases]
        if not case_reports:
            raise ValueError("No cases to evaluate")

        aggregate: dict[str, float] = {}
        for name in self.evaluator_names:
            scores = [report.score_map().get(name, 0.0) for report in case_reports]
            aggregate[name] = sum(scores) / len(scores)

        overall = sum(report.overall for report in case_reports) / len(case_reports)
        return RunReport(
            eval_set=eval_set_name,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            cases=case_reports,
            aggregate=aggregate,
            overall=overall,
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Render a fixed-width ASCII table without third-party dependencies."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(char: str = "-") -> str:
        return "+" + "+".join(char * (width + 2) for width in widths) + "+"

    def format_row(cells: Sequence[str]) -> str:
        padded = [f" {cell.ljust(widths[i])} " for i, cell in enumerate(cells)]
        return "|" + "|".join(padded) + "|"

    out = [line("="), format_row(headers), line("=")]
    out.extend(format_row(row) for row in rows)
    out.append(line("="))
    return "\n".join(out)


def print_report(report: RunReport, runner: EvalRunner, threshold: float | None = None) -> None:
    """Print the per-case table, the aggregate table and a failure digest.

    ``threshold`` controls only which cases appear in the findings digest; it
    does not affect scoring. Defaults to the runner's own case threshold.
    """
    if threshold is None:
        threshold = runner.case_threshold
    names = runner.evaluator_names
    headers = ["case", *[e.short_name for e in runner.evaluators], "overall"]
    rows: list[list[str]] = []
    for case in report.cases:
        scores = case.score_map()
        rows.append(
            [
                case.case_id,
                *[f"{scores.get(name, 0.0):.2f}" for name in names],
                f"{case.overall:.2f}",
            ]
        )

    print()
    print("=" * 78)
    print(f"GROUNDED ANSWER EVALUATION  --  {report.eval_set}")
    print(f"run at {report.generated_at}  |  {len(report.cases)} case(s)")
    print("=" * 78)
    print()
    print("Per-case scores")
    print(render_table(headers, rows))

    print()
    print("Aggregate scores")
    agg_rows = [[name, f"{value:.3f}"] for name, value in report.aggregate.items()]
    agg_rows.append(["OVERALL (weighted)", f"{report.overall:.3f}"])
    print(render_table(["metric", "mean score"], agg_rows))

    failing = [case for case in report.cases if case.failures(threshold)]
    print()
    if not failing:
        print(f"No individual metric below {threshold:.2f}.")
        return

    print(f"Findings ({len(failing)} case(s) with at least one metric below {threshold:.2f})")
    print("-" * 78)
    for case in failing:
        print(f"  {case.case_id}  (overall {case.overall:.2f})")
        print(f"    Q: {case.question[:88]}")
        for result in case.failures(threshold):
            print(f"    [{result.score:.2f}] {result.evaluator}: {result.rationale}")
        print()


# ---------------------------------------------------------------------------
# Artefacts
# ---------------------------------------------------------------------------


def write_json(report: RunReport, path: Path) -> None:
    """Write the full report, including every rationale, as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    LOGGER.info("Wrote JSON report to %s", path)


def write_csv(report: RunReport, runner: EvalRunner, path: Path) -> None:
    """Write a flat per-case score matrix as CSV (one row per case)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    names = runner.evaluator_names
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", *names, "overall", "question"])
        for case in report.cases:
            scores = case.score_map()
            writer.writerow(
                [
                    case.case_id,
                    *[f"{scores.get(name, 0.0):.4f}" for name in names],
                    f"{case.overall:.4f}",
                    case.question,
                ]
            )
    LOGGER.info("Wrote CSV report to %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="eval_framework",
        description="Offline regression gate for data-grounded agent answers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  aggregate score >= --fail-under\n"
            "  1  aggregate score <  --fail-under (CI gate tripped)\n"
            "  2  usage / input error\n"
        ),
    )
    parser.add_argument(
        "--eval-set",
        type=Path,
        default=Path(__file__).with_name("sample_eval_set.jsonl"),
        help="Path to the JSONL eval set (default: bundled sample set).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Directory to write eval_report.json and eval_report.csv into.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=DEFAULT_FAIL_UNDER,
        help=f"Exit non-zero if the weighted aggregate is below this (default: {DEFAULT_FAIL_UNDER}).",
    )
    parser.add_argument(
        "--case-threshold",
        type=float,
        default=0.70,
        help="Per-metric score below which a case is listed in the findings digest.",
    )
    parser.add_argument(
        "--evaluators",
        default=None,
        help="Comma-separated subset of evaluator names to run (default: all).",
    )
    parser.add_argument(
        "--reference-date",
        default=None,
        help="ISO date/time used for staleness when a case does not pin its own.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    reference_time: datetime | None = None
    if args.reference_date:
        try:
            text = args.reference_date.replace("Z", "+00:00")
            reference_time = datetime.fromisoformat(text)
            if reference_time.tzinfo is None:
                reference_time = reference_time.replace(tzinfo=timezone.utc)
        except ValueError:
            LOGGER.error("Could not parse --reference-date %r", args.reference_date)
            return 2

    try:
        names = args.evaluators.split(",") if args.evaluators else None
        evaluators = select_evaluators(names, reference_time=reference_time)
        cases = load_eval_set(args.eval_set)
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 2

    runner = EvalRunner(evaluators, case_threshold=args.case_threshold)
    report = runner.run(cases, eval_set_name=str(args.eval_set))
    print_report(report, runner)

    if args.out:
        write_json(report, args.out / "eval_report.json")
        write_csv(report, runner, args.out / "eval_report.csv")

    passed = report.overall >= args.fail_under
    print()
    print(
        f"RESULT: weighted aggregate {report.overall:.3f} "
        f"{'>=' if passed else '<'} threshold {args.fail_under:.3f} -> {'PASS' if passed else 'FAIL'}"
    )
    print()
    return 0 if passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
