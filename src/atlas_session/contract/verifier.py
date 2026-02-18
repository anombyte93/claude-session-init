"""Deterministic test runner for contract criteria.

Runs each criterion and returns pass/fail results — no AI judgment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..session.operations import read_context
from .model import Contract, CriterionType


def run_tests(project_dir: str, contract: Contract) -> dict:
    """Execute all criteria deterministically. Returns structured results."""
    results: list[dict] = []
    total_weight = 0.0
    passed_weight = 0.0

    for criterion in contract.criteria:
        result = _run_one(project_dir, criterion, contract)
        results.append(result)
        total_weight += criterion.weight
        if result["passed"]:
            passed_weight += criterion.weight

    all_passed = all(r["passed"] for r in results)
    score = (passed_weight / total_weight * 100) if total_weight > 0 else 0

    return {
        "results": results,
        "all_passed": all_passed,
        "score": round(score, 1),
        "summary": f"{sum(1 for r in results if r['passed'])}/{len(results)} criteria passed ({score:.0f}%)",
    }


def _run_one(project_dir: str, criterion, contract: Contract) -> dict:
    """Run a single criterion and return result dict."""
    name = criterion.name
    ctype = criterion.type
    pass_when = criterion.pass_when

    try:
        if ctype == CriterionType.SHELL:
            return _run_shell(project_dir, name, criterion.command or "", pass_when, criterion.weight)
        elif ctype == CriterionType.CONTEXT_CHECK:
            return _run_context_check(project_dir, name, criterion.field or "", pass_when, criterion.weight)
        elif ctype == CriterionType.FILE_EXISTS:
            return _run_file_exists(project_dir, name, criterion.path or "", pass_when, criterion.weight)
        elif ctype == CriterionType.GIT_CHECK:
            return _run_shell(project_dir, name, criterion.command or "", pass_when, criterion.weight)
        else:
            return {"name": name, "passed": False, "output": f"Unknown type: {ctype}", "weight": criterion.weight}
    except Exception as e:
        return {"name": name, "passed": False, "output": str(e), "weight": criterion.weight}


def _run_shell(project_dir: str, name: str, command: str, pass_when: str, weight: float) -> dict:
    """Run a shell command, evaluate pass_when against exit code."""
    if not command:
        return {"name": name, "passed": False, "output": "No command specified", "weight": weight}

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (proc.stdout + proc.stderr).strip()[:500]
        passed = _evaluate_pass_when(pass_when, exit_code=proc.returncode, output=output)
    except subprocess.TimeoutExpired:
        output = "Command timed out after 120s"
        passed = False
    except Exception as e:
        output = str(e)
        passed = False

    return {"name": name, "passed": passed, "output": output, "weight": weight}


def _run_context_check(project_dir: str, name: str, field_name: str, pass_when: str, weight: float) -> dict:
    """Check a field from read_context output."""
    ctx = read_context(project_dir)
    value = ctx.get(field_name)

    if value is None:
        return {"name": name, "passed": False, "output": f"Field '{field_name}' not found", "weight": weight}

    passed = _evaluate_pass_when(pass_when, value=value)
    return {"name": name, "passed": passed, "output": f"{field_name} = {value}", "weight": weight}


def _run_file_exists(project_dir: str, name: str, path: str, pass_when: str, weight: float) -> dict:
    """Check if a file or directory exists."""
    full_path = Path(project_dir) / path
    exists = full_path.exists()

    if pass_when == "not_empty":
        if full_path.is_dir():
            passed = exists and any(full_path.iterdir())
        elif full_path.is_file():
            passed = exists and full_path.stat().st_size > 0
        else:
            passed = False
    else:
        passed = exists

    return {"name": name, "passed": passed, "output": f"{'exists' if exists else 'missing'}: {path}", "weight": weight}


def _evaluate_pass_when(
    pass_when: str,
    exit_code: int | None = None,
    value=None,
    output: str = "",
) -> bool:
    """Evaluate a pass_when expression.

    Supported expressions:
    - "exit_code == 0"
    - "== 0" (shorthand for numeric/count comparison)
    - "> 0"
    - "not_empty"
    - "contains:<text>"
    """
    pw = pass_when.strip()

    if pw == "not_empty":
        if value is not None:
            if isinstance(value, (list, dict)):
                return len(value) > 0
            return bool(value)
        return bool(output)

    if pw.startswith("contains:"):
        text = pw[len("contains:"):]
        if output:
            return text in output
        if isinstance(value, str):
            return text in value
        return False

    if "exit_code" in pw:
        if exit_code is None:
            return False
        # "exit_code == 0"
        try:
            op_val = pw.split("exit_code")[1].strip()
            if op_val.startswith("=="):
                return exit_code == int(op_val[2:].strip())
            elif op_val.startswith("!="):
                return exit_code != int(op_val[2:].strip())
        except (ValueError, IndexError):
            return False

    # Shorthand numeric comparison: "== 0", "> 0", etc.
    if pw.startswith("==") or pw.startswith("!=") or pw.startswith(">") or pw.startswith("<"):
        compare_val = value
        if compare_val is None and exit_code is not None:
            compare_val = exit_code
        if isinstance(compare_val, list):
            compare_val = len(compare_val)
        try:
            num = float(compare_val) if compare_val is not None else 0
            if pw.startswith("=="):
                return num == float(pw[2:].strip())
            elif pw.startswith("!="):
                return num != float(pw[2:].strip())
            elif pw.startswith(">="):
                return num >= float(pw[2:].strip())
            elif pw.startswith("<="):
                return num <= float(pw[2:].strip())
            elif pw.startswith(">"):
                return num > float(pw[1:].strip())
            elif pw.startswith("<"):
                return num < float(pw[1:].strip())
        except (ValueError, TypeError):
            return False

    return False
