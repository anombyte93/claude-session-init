"""Contract & bounty MCP tool definitions.

Deterministic bounty management — contracts define executable test
criteria at creation time, verification just runs them.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from . import atlascoin
from .model import Contract, Criterion, CriterionType
from .verifier import run_tests


def register(mcp: FastMCP) -> None:
    """Register all contract tools on the given server."""

    @mcp.tool
    async def contract_health() -> dict:
        """Check AtlasCoin service availability. Call before any bounty
        operations. Returns {healthy, url}."""
        return await atlascoin.health()

    @mcp.tool
    async def contract_create(
        project_dir: str,
        soul_purpose: str,
        escrow: int,
        criteria: list[dict],
    ) -> dict:
        """Create a bounty with executable test criteria.

        Each criterion dict needs: name, type (shell|context_check|
        file_exists|git_check), pass_when, and optionally command/field/path.

        Creates both an AtlasCoin bounty (if available) and a local
        contract.json in session-context/.
        """
        parsed = []
        for c in criteria:
            try:
                parsed.append(Criterion.from_dict(c))
            except Exception as e:
                return {"status": "error", "message": f"Invalid criterion '{c.get('name', '?')}': {e}"}

        contract = Contract(
            soul_purpose=soul_purpose,
            escrow=escrow,
            criteria=parsed,
        )

        # Try AtlasCoin
        api_result = await atlascoin.create_bounty(soul_purpose, escrow)
        if api_result.get("status") == "ok":
            bounty_data = api_result.get("data", {})
            bounty_id = str(bounty_data.get("id", bounty_data.get("bountyId", "")))
            contract.bounty_id = bounty_id
            contract.status = "active"

            # Write BOUNTY_ID.txt for backward compatibility
            bid_path = Path(project_dir) / "session-context" / "BOUNTY_ID.txt"
            bid_path.write_text(bounty_id)
        else:
            contract.status = "active_local"

        contract.save(project_dir)

        return {
            "status": "ok",
            "bounty_id": contract.bounty_id,
            "contract_status": contract.status,
            "criteria_count": len(parsed),
            "atlascoin": api_result.get("status") == "ok",
        }

    @mcp.tool
    async def contract_get_status(project_dir: str) -> dict:
        """Get current contract and bounty status."""
        contract = Contract.load(project_dir)
        if not contract:
            return {"status": "none", "message": "No contract found"}

        result = contract.to_dict()

        if contract.bounty_id:
            api_status = await atlascoin.get_bounty(contract.bounty_id)
            result["atlascoin_status"] = api_status

        return result

    @mcp.tool
    def contract_run_tests(project_dir: str) -> dict:
        """Execute all contract criteria deterministically.

        Runs each criterion (shell commands, context checks, file checks,
        git checks) and returns pass/fail results. No AI judgment involved.
        """
        contract = Contract.load(project_dir)
        if not contract:
            return {"status": "error", "message": "No contract found"}

        return run_tests(project_dir, contract)

    @mcp.tool
    async def contract_submit(project_dir: str, evidence: dict | None = None) -> dict:
        """Submit solution to AtlasCoin for the active contract.
        Optionally pass evidence dict; defaults to test run results."""
        contract = Contract.load(project_dir)
        if not contract or not contract.bounty_id:
            return {"status": "error", "message": "No active bounty"}

        if evidence is None:
            test_results = run_tests(project_dir, contract)
            evidence = {
                "soul_purpose": contract.soul_purpose,
                "test_results": test_results,
            }

        stake = int(contract.escrow * 0.1)
        result = await atlascoin.submit_solution(contract.bounty_id, stake, evidence)

        if result.get("status") == "ok":
            contract.status = "submitted"
            contract.save(project_dir)

        return result

    @mcp.tool
    async def contract_verify(project_dir: str) -> dict:
        """Run deterministic verification: execute all criteria tests,
        then submit pass/fail to AtlasCoin."""
        contract = Contract.load(project_dir)
        if not contract:
            return {"status": "error", "message": "No contract found"}

        # Run tests locally
        test_results = run_tests(project_dir, contract)

        verification = {
            "passed": test_results["all_passed"],
            "score": test_results["score"],
            "details": test_results["results"],
            "summary": test_results["summary"],
        }

        # Submit to AtlasCoin if bounty exists
        if contract.bounty_id:
            api_result = await atlascoin.verify_bounty(contract.bounty_id, verification)
            verification["atlascoin"] = api_result

        if test_results["all_passed"]:
            contract.status = "verified"
        else:
            contract.status = "failed_verification"
        contract.save(project_dir)

        return verification

    @mcp.tool
    async def contract_settle(project_dir: str) -> dict:
        """Settle a verified bounty — distribute tokens."""
        contract = Contract.load(project_dir)
        if not contract or not contract.bounty_id:
            return {"status": "error", "message": "No active bounty to settle"}

        result = await atlascoin.settle_bounty(contract.bounty_id)

        if result.get("status") == "ok":
            contract.status = "settled"
            contract.save(project_dir)

        return result

    @mcp.tool
    def contract_draft_criteria(
        soul_purpose: str,
        project_signals: dict | None = None,
    ) -> dict:
        """Suggest deterministic criteria based on soul purpose and project
        signals. Returns suggested criteria for AI to present to user.
        This is the only place AI judgment is involved in contracts."""
        suggestions: list[dict] = []

        # Always suggest: has commits
        suggestions.append({
            "name": "has_commits",
            "type": "git_check",
            "command": "git log --oneline -1",
            "pass_when": "exit_code == 0",
            "weight": 1.0,
        })

        # Always suggest: no open tasks
        suggestions.append({
            "name": "no_open_tasks",
            "type": "context_check",
            "field": "open_tasks",
            "pass_when": "== 0",
            "weight": 1.0,
        })

        # Detect test-related soul purposes
        test_keywords = {"test", "tests", "testing", "tdd", "coverage", "spec"}
        if any(kw in soul_purpose.lower() for kw in test_keywords):
            suggestions.append({
                "name": "tests_pass",
                "type": "shell",
                "command": _guess_test_command(project_signals),
                "pass_when": "exit_code == 0",
                "weight": 2.0,
            })

        # Detect build/deploy soul purposes
        build_keywords = {"build", "deploy", "compile", "bundle"}
        if any(kw in soul_purpose.lower() for kw in build_keywords):
            suggestions.append({
                "name": "build_succeeds",
                "type": "shell",
                "command": _guess_build_command(project_signals),
                "pass_when": "exit_code == 0",
                "weight": 2.0,
            })

        # If project has detected stack, suggest lint
        if project_signals and project_signals.get("detected_stack"):
            suggestions.append({
                "name": "lint_clean",
                "type": "shell",
                "command": _guess_lint_command(project_signals),
                "pass_when": "exit_code == 0",
                "weight": 0.5,
            })

        # Session context must exist
        suggestions.append({
            "name": "session_context_exists",
            "type": "file_exists",
            "path": "session-context/CLAUDE-activeContext.md",
            "pass_when": "not_empty",
            "weight": 0.5,
        })

        return {
            "suggested_criteria": suggestions,
            "soul_purpose": soul_purpose,
            "note": "Review and modify criteria before creating contract. Remove inapplicable criteria and adjust commands for your project.",
        }


def _guess_test_command(signals: dict | None) -> str:
    if not signals:
        return "echo 'No test command configured'"
    stack = signals.get("detected_stack", [])
    if "node" in stack:
        return "npm test"
    if "python" in stack:
        return "pytest"
    if "rust" in stack:
        return "cargo test"
    if "go" in stack:
        return "go test ./..."
    return "echo 'No test command configured'"


def _guess_build_command(signals: dict | None) -> str:
    if not signals:
        return "echo 'No build command configured'"
    stack = signals.get("detected_stack", [])
    if "node" in stack:
        return "npm run build"
    if "rust" in stack:
        return "cargo build"
    if "go" in stack:
        return "go build ./..."
    return "echo 'No build command configured'"


def _guess_lint_command(signals: dict | None) -> str:
    if not signals:
        return "echo 'No lint command configured'"
    stack = signals.get("detected_stack", [])
    if "node" in stack:
        return "npm run lint"
    if "python" in stack:
        return "ruff check ."
    if "rust" in stack:
        return "cargo clippy"
    if "go" in stack:
        return "go vet ./..."
    return "echo 'No lint command configured'"
