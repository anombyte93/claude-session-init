"""Unit tests for contract model, verifier, AtlasCoin client, and draft criteria.

Covers Tasks 5, 6, 7 of the test plan:
  Task 5: Contract model and verifier (30 tests)
  Task 6: AtlasCoin HTTP client mocked with respx (9 tests)
  Task 7: Draft criteria helpers (8 tests)
"""

import json
import subprocess
from unittest.mock import patch

import httpx
import pytest
import respx

from atlas_session.contract.model import Contract, Criterion, CriterionType
from atlas_session.contract.verifier import _evaluate_pass_when, run_tests
from atlas_session.contract import atlascoin
from atlas_session.contract.tools import (
    _guess_build_command,
    _guess_lint_command,
    _guess_test_command,
)
from atlas_session.common.config import ATLASCOIN_URL


# =========================================================================
# Task 5 — Contract Model and Verifier
# =========================================================================


class TestCriterionModel:
    """Tests for Criterion dataclass and from_dict/to_dict."""

    def test_from_dict_shell(self):
        """Shell criterion round-trips through from_dict correctly."""
        data = {
            "name": "tests_pass",
            "type": "shell",
            "command": "pytest",
            "pass_when": "exit_code == 0",
            "weight": 2.0,
        }
        c = Criterion.from_dict(data)
        assert c.name == "tests_pass"
        assert c.type == CriterionType.SHELL
        assert c.command == "pytest"
        assert c.pass_when == "exit_code == 0"
        assert c.weight == 2.0

    def test_round_trip(self):
        """to_dict -> from_dict produces equivalent Criterion."""
        original = Criterion(
            name="test_lint",
            type=CriterionType.SHELL,
            pass_when="exit_code == 0",
            command="ruff check .",
            weight=1.5,
        )
        restored = Criterion.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.type == original.type
        assert restored.command == original.command
        assert restored.pass_when == original.pass_when
        assert restored.weight == original.weight

    def test_invalid_type_raises(self):
        """from_dict raises ValueError for unknown criterion type."""
        data = {
            "name": "bad",
            "type": "unknown_type",
            "pass_when": "exit_code == 0",
            "weight": 1.0,
        }
        with pytest.raises(ValueError):
            Criterion.from_dict(data)


class TestContractModel:
    """Tests for Contract dataclass, persistence, and status lifecycle."""

    def test_save_and_load(self, project_with_session):
        """Contract saves to contract.json and loads back identically."""
        contract = Contract(
            soul_purpose="Build widget factory",
            escrow=200,
            criteria=[
                Criterion(
                    name="tests_pass",
                    type=CriterionType.SHELL,
                    pass_when="exit_code == 0",
                    command="echo ok",
                    weight=2.0,
                ),
            ],
            bounty_id="abc-123",
            status="active",
        )
        contract.save(str(project_with_session))

        loaded = Contract.load(str(project_with_session))
        assert loaded is not None
        assert loaded.soul_purpose == "Build widget factory"
        assert loaded.escrow == 200
        assert loaded.bounty_id == "abc-123"
        assert loaded.status == "active"
        assert len(loaded.criteria) == 1
        assert loaded.criteria[0].name == "tests_pass"
        assert loaded.criteria[0].type == CriterionType.SHELL

    def test_load_returns_none_when_missing(self, project_with_session):
        """Contract.load returns None when no contract.json exists."""
        result = Contract.load(str(project_with_session))
        assert result is None

    def test_load_returns_none_on_corrupt_json(self, project_with_session):
        """Contract.load returns None when contract.json is malformed."""
        contract_path = project_with_session / "session-context" / "contract.json"
        contract_path.write_text("{not valid json}")
        result = Contract.load(str(project_with_session))
        assert result is None

    def test_status_lifecycle(self, project_with_session):
        """Contract status progresses through expected lifecycle states."""
        contract = Contract(
            soul_purpose="Test lifecycle",
            escrow=50,
        )
        assert contract.status == "draft"

        contract.status = "active"
        contract.save(str(project_with_session))
        loaded = Contract.load(str(project_with_session))
        assert loaded.status == "active"

        contract.status = "submitted"
        contract.save(str(project_with_session))
        loaded = Contract.load(str(project_with_session))
        assert loaded.status == "submitted"

        contract.status = "verified"
        contract.save(str(project_with_session))
        loaded = Contract.load(str(project_with_session))
        assert loaded.status == "verified"

        contract.status = "settled"
        contract.save(str(project_with_session))
        loaded = Contract.load(str(project_with_session))
        assert loaded.status == "settled"

    def test_to_dict_serializable(self):
        """Contract.to_dict returns JSON-serializable dictionary."""
        contract = Contract(
            soul_purpose="Serialize test",
            escrow=100,
            criteria=[
                Criterion(
                    name="check",
                    type=CriterionType.FILE_EXISTS,
                    pass_when="not_empty",
                    path="README.md",
                    weight=0.5,
                ),
            ],
            bounty_id="xyz",
            status="active",
        )
        d = contract.to_dict()
        # Should be JSON-serializable without error
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        # Verify structure
        assert d["soul_purpose"] == "Serialize test"
        assert d["escrow"] == 100
        assert len(d["criteria"]) == 1
        assert d["criteria"][0]["type"] == "file_exists"

    def test_from_dict_with_sample(self, sample_contract_dict):
        """Contract.from_dict parses the sample contract fixture correctly."""
        contract = Contract.from_dict(sample_contract_dict)
        assert contract.soul_purpose == "Build a widget factory"
        assert contract.escrow == 100
        assert len(contract.criteria) == 2
        assert contract.criteria[0].type == CriterionType.SHELL
        assert contract.criteria[1].type == CriterionType.FILE_EXISTS

    def test_from_dict_empty_criteria(self):
        """Contract.from_dict handles missing criteria list gracefully."""
        data = {
            "soul_purpose": "Test",
            "escrow": 50,
            "bounty_id": "",
            "status": "draft",
        }
        contract = Contract.from_dict(data)
        assert contract.criteria == []


class TestEvaluatePassWhen:
    """Tests for the _evaluate_pass_when() expression evaluator."""

    def test_exit_code_equals_zero_passes(self):
        """'exit_code == 0' passes when exit_code is 0."""
        assert _evaluate_pass_when("exit_code == 0", exit_code=0) is True

    def test_exit_code_equals_zero_fails(self):
        """'exit_code == 0' fails when exit_code is 1."""
        assert _evaluate_pass_when("exit_code == 0", exit_code=1) is False

    def test_exit_code_not_equals_zero(self):
        """'exit_code != 0' passes when exit_code is non-zero."""
        assert _evaluate_pass_when("exit_code != 0", exit_code=1) is True
        assert _evaluate_pass_when("exit_code != 0", exit_code=0) is False

    def test_exit_code_none_returns_false(self):
        """'exit_code == 0' returns False when exit_code is None."""
        assert _evaluate_pass_when("exit_code == 0", exit_code=None) is False

    def test_shorthand_equals_zero(self):
        """'== 0' shorthand works with exit_code as fallback."""
        assert _evaluate_pass_when("== 0", exit_code=0) is True
        assert _evaluate_pass_when("== 0", exit_code=1) is False

    def test_shorthand_greater_than_zero(self):
        """> 0' passes when value is positive."""
        assert _evaluate_pass_when("> 0", value=5) is True
        assert _evaluate_pass_when("> 0", value=0) is False

    def test_shorthand_less_than(self):
        """'< 10' passes when value is less than 10."""
        assert _evaluate_pass_when("< 10", value=5) is True
        assert _evaluate_pass_when("< 10", value=10) is False

    def test_not_empty_string(self):
        """'not_empty' passes for non-empty string value."""
        assert _evaluate_pass_when("not_empty", value="hello") is True
        assert _evaluate_pass_when("not_empty", value="") is False

    def test_not_empty_list(self):
        """'not_empty' passes for non-empty list, fails for empty list."""
        assert _evaluate_pass_when("not_empty", value=["a", "b"]) is True
        assert _evaluate_pass_when("not_empty", value=[]) is False

    def test_not_empty_dict(self):
        """'not_empty' passes for non-empty dict, fails for empty dict."""
        assert _evaluate_pass_when("not_empty", value={"k": "v"}) is True
        assert _evaluate_pass_when("not_empty", value={}) is False

    def test_not_empty_output_fallback(self):
        """'not_empty' falls back to output when value is None."""
        assert _evaluate_pass_when("not_empty", output="some output") is True
        assert _evaluate_pass_when("not_empty", output="") is False

    def test_contains_text_in_output(self):
        """'contains:text' checks for substring in output."""
        assert (
            _evaluate_pass_when("contains:SUCCESS", output="Test SUCCESS done") is True
        )
        assert _evaluate_pass_when("contains:FAIL", output="Test SUCCESS done") is False

    def test_contains_text_in_value(self):
        """'contains:text' checks for substring in value when no output."""
        assert (
            _evaluate_pass_when("contains:widget", value="build widget factory") is True
        )
        assert (
            _evaluate_pass_when("contains:missing", value="build widget factory")
            is False
        )

    def test_contains_returns_false_when_no_string(self):
        """'contains:text' returns False when neither output nor string value."""
        assert _evaluate_pass_when("contains:text", value=42) is False
        assert _evaluate_pass_when("contains:text") is False

    def test_list_uses_length_for_shorthand(self):
        """Shorthand numeric comparison uses len() for list values."""
        assert _evaluate_pass_when("== 0", value=[]) is True
        assert _evaluate_pass_when("> 0", value=["a"]) is True
        assert _evaluate_pass_when("== 3", value=[1, 2, 3]) is True

    def test_shorthand_greater_equal(self):
        """>= 2' passes when value is at least 2."""
        assert _evaluate_pass_when(">= 2", value=2) is True
        assert _evaluate_pass_when(">= 2", value=1) is False

    def test_shorthand_less_equal(self):
        """'<= 5' passes when value is at most 5."""
        assert _evaluate_pass_when("<= 5", value=5) is True
        assert _evaluate_pass_when("<= 5", value=6) is False

    def test_shorthand_not_equals(self):
        """'!= 0' passes when value is non-zero."""
        assert _evaluate_pass_when("!= 0", value=1) is True
        assert _evaluate_pass_when("!= 0", value=0) is False

    def test_unrecognized_expression_returns_false(self):
        """Unrecognized pass_when expressions return False."""
        assert _evaluate_pass_when("garbage expression") is False


class TestRunTests:
    """Tests for the run_tests() function."""

    def test_shell_passes(self, project_with_session):
        """Shell criterion passes when command succeeds."""
        contract = Contract(
            soul_purpose="Test shell",
            escrow=50,
            criteria=[
                Criterion(
                    name="echo_test",
                    type=CriterionType.SHELL,
                    command="echo hello",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True
        assert result["results"][0]["passed"] is True
        assert result["score"] == 100.0

    def test_shell_fails(self, project_with_session):
        """Shell criterion fails when command returns non-zero."""
        contract = Contract(
            soul_purpose="Test shell fail",
            escrow=50,
            criteria=[
                Criterion(
                    name="false_cmd",
                    type=CriterionType.SHELL,
                    command="false",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False

    def test_file_exists_passes(self, project_with_session):
        """File exists criterion passes when file is present and non-empty."""
        contract = Contract(
            soul_purpose="Test file",
            escrow=50,
            criteria=[
                Criterion(
                    name="active_ctx",
                    type=CriterionType.FILE_EXISTS,
                    path="session-context/CLAUDE-activeContext.md",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True
        assert result["results"][0]["passed"] is True

    def test_file_missing_fails(self, project_with_session):
        """File exists criterion fails when file is missing."""
        contract = Contract(
            soul_purpose="Test file missing",
            escrow=50,
            criteria=[
                Criterion(
                    name="nonexistent",
                    type=CriterionType.FILE_EXISTS,
                    path="does-not-exist.txt",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False
        assert "missing" in result["results"][0]["output"]

    def test_weighted_scoring(self, project_with_session):
        """Score respects criterion weights: passing criteria earn their weight."""
        contract = Contract(
            soul_purpose="Test weights",
            escrow=50,
            criteria=[
                Criterion(
                    name="passes",
                    type=CriterionType.SHELL,
                    command="true",
                    pass_when="exit_code == 0",
                    weight=3.0,
                ),
                Criterion(
                    name="fails",
                    type=CriterionType.SHELL,
                    command="false",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        # 3.0 out of 4.0 total weight = 75%
        assert result["score"] == 75.0

    def test_summary_format(self, project_with_session):
        """Summary contains 'N/M criteria passed (P%)'."""
        contract = Contract(
            soul_purpose="Test summary",
            escrow=50,
            criteria=[
                Criterion(
                    name="passes",
                    type=CriterionType.SHELL,
                    command="true",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
                Criterion(
                    name="also_passes",
                    type=CriterionType.SHELL,
                    command="true",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert "2/2 criteria passed" in result["summary"]
        assert "100%" in result["summary"]

    def test_context_check_criterion(self, project_with_soul_purpose):
        """Context check criterion evaluates read_context field correctly."""
        contract = Contract(
            soul_purpose="Test context",
            escrow=50,
            criteria=[
                Criterion(
                    name="has_purpose",
                    type=CriterionType.CONTEXT_CHECK,
                    field="soul_purpose",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_soul_purpose), contract)
        assert result["all_passed"] is True
        assert result["results"][0]["passed"] is True
        assert "soul_purpose" in result["results"][0]["output"]

    def test_context_check_missing_field(self, project_with_session):
        """Context check returns false when field is not found."""
        contract = Contract(
            soul_purpose="Test missing field",
            escrow=50,
            criteria=[
                Criterion(
                    name="check_fake",
                    type=CriterionType.CONTEXT_CHECK,
                    field="nonexistent_field",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert "not found" in result["results"][0]["output"]

    def test_git_check_in_git_repo(self, project_with_git):
        """Git check criterion uses shell runner on git commands."""
        contract = Contract(
            soul_purpose="Test git",
            escrow=50,
            criteria=[
                Criterion(
                    name="has_commits",
                    type=CriterionType.GIT_CHECK,
                    command="git log --oneline -1",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_git), contract)
        assert result["all_passed"] is True
        assert result["results"][0]["passed"] is True

    def test_git_check_fails_in_non_git(self, project_with_session):
        """Git check criterion fails in a non-git directory."""
        contract = Contract(
            soul_purpose="Test git fail",
            escrow=50,
            criteria=[
                Criterion(
                    name="has_commits",
                    type=CriterionType.GIT_CHECK,
                    command="git log --oneline -1",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False

    def test_shell_no_command_fails(self, project_with_session):
        """Shell criterion with empty command fails with descriptive output."""
        contract = Contract(
            soul_purpose="Test no cmd",
            escrow=50,
            criteria=[
                Criterion(
                    name="empty_cmd",
                    type=CriterionType.SHELL,
                    command="",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert "No command" in result["results"][0]["output"]

    def test_empty_criteria_list(self, project_with_session):
        """Contract with no criteria returns all_passed=True and score=0."""
        contract = Contract(
            soul_purpose="Test empty",
            escrow=50,
            criteria=[],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True
        assert result["score"] == 0
        assert result["results"] == []

    def test_file_exists_directory_not_empty(self, project_with_session):
        """File exists with not_empty checks directory has contents."""
        contract = Contract(
            soul_purpose="Test dir",
            escrow=50,
            criteria=[
                Criterion(
                    name="session_dir_notempty",
                    type=CriterionType.FILE_EXISTS,
                    path="session-context",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True

    def test_file_exists_simple_exists_check(self, project_with_session):
        """File exists with non-not_empty pass_when only checks existence."""
        # Create a file
        (project_with_session / "test_file.txt").write_text("")
        contract = Contract(
            soul_purpose="Test exists",
            escrow=50,
            criteria=[
                Criterion(
                    name="file_present",
                    type=CriterionType.FILE_EXISTS,
                    path="test_file.txt",
                    pass_when="exit_code == 0",  # not 'not_empty', so just checks exists
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True


# =========================================================================
# Task 6 — AtlasCoin HTTP Client (mocked with respx)
# =========================================================================


class TestAtlasCoinHealth:
    """Tests for atlascoin.health() with mocked HTTP."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthy_200(self):
        """Returns healthy=True on 200 with JSON content-type."""
        respx.get(f"{ATLASCOIN_URL}/health").mock(
            return_value=httpx.Response(
                200,
                json={"status": "ok"},
                headers={"content-type": "application/json"},
            )
        )
        result = await atlascoin.health()
        assert result["healthy"] is True
        assert result["url"] == ATLASCOIN_URL
        assert result["data"] == {"status": "ok"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_unhealthy_500(self):
        """Returns healthy=False on 500 status."""
        respx.get(f"{ATLASCOIN_URL}/health").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        result = await atlascoin.health()
        assert result["healthy"] is False
        assert result["status_code"] == 500

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_refused(self):
        """Returns healthy=False with error on connection failure."""
        respx.get(f"{ATLASCOIN_URL}/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await atlascoin.health()
        assert result["healthy"] is False
        assert "error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthy_non_json_content_type(self):
        """Returns empty data dict when content-type is not JSON."""
        respx.get(f"{ATLASCOIN_URL}/health").mock(
            return_value=httpx.Response(
                200,
                text="OK",
                headers={"content-type": "text/plain"},
            )
        )
        result = await atlascoin.health()
        assert result["healthy"] is True
        assert result["data"] == {}


class TestAtlasCoinCreateBounty:
    """Tests for atlascoin.create_bounty() with mocked HTTP."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_201(self):
        """Returns status=ok with data on 201."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties").mock(
            return_value=httpx.Response(
                201,
                json={"id": "bounty-123", "escrowAmount": 100},
            )
        )
        result = await atlascoin.create_bounty("Build a thing", 100)
        assert result["status"] == "ok"
        assert result["data"]["id"] == "bounty-123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error_400(self):
        """Returns status=error on 400 with body text."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties").mock(
            return_value=httpx.Response(400, text="Bad Request: invalid escrow")
        )
        result = await atlascoin.create_bounty("Build a thing", -1)
        assert result["status"] == "error"
        assert result["status_code"] == 400
        assert "Bad Request" in result["body"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Returns status=error with error string on connection failure."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await atlascoin.create_bounty("Build a thing", 100)
        assert result["status"] == "error"
        assert "error" in result


class TestAtlasCoinSubmitSolution:
    """Tests for atlascoin.submit_solution() with mocked HTTP."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_200(self):
        """Returns status=ok on successful submission."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties/bounty-123/submit").mock(
            return_value=httpx.Response(
                200,
                json={"submitted": True, "claimId": "claim-456"},
            )
        )
        result = await atlascoin.submit_solution(
            "bounty-123", 10, {"soul_purpose": "test"}
        )
        assert result["status"] == "ok"
        assert result["data"]["submitted"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_error(self):
        """Returns status=error on non-success status code."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties/bounty-123/submit").mock(
            return_value=httpx.Response(422, text="Unprocessable Entity")
        )
        result = await atlascoin.submit_solution(
            "bounty-123", 10, {"soul_purpose": "test"}
        )
        assert result["status"] == "error"
        assert result["status_code"] == 422


class TestAtlasCoinVerify:
    """Tests for atlascoin.verify_bounty() with mocked HTTP."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_200(self):
        """Returns status=ok on successful verification."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties/bounty-123/verify").mock(
            return_value=httpx.Response(
                200,
                json={"verified": True},
            )
        )
        result = await atlascoin.verify_bounty(
            "bounty-123", {"passed": True, "score": 100}
        )
        assert result["status"] == "ok"
        assert result["data"]["verified"] is True


class TestAtlasCoinSettle:
    """Tests for atlascoin.settle_bounty() with mocked HTTP."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_200(self):
        """Returns status=ok on successful settlement."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties/bounty-123/settle").mock(
            return_value=httpx.Response(
                200,
                json={"settled": True, "tokens": 100},
            )
        )
        result = await atlascoin.settle_bounty("bounty-123")
        assert result["status"] == "ok"
        assert result["data"]["settled"] is True
        assert result["data"]["tokens"] == 100

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_404(self):
        """Returns status=error on 404 (bounty not found)."""
        respx.post(f"{ATLASCOIN_URL}/api/bounties/nonexistent/settle").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        result = await atlascoin.settle_bounty("nonexistent")
        assert result["status"] == "error"
        assert result["status_code"] == 404
        assert "Not Found" in result["body"]


class TestAtlasCoinGetBounty:
    """Tests for atlascoin.get_bounty() with mocked HTTP."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_200(self):
        """Returns status=ok with bounty data on 200."""
        respx.get(f"{ATLASCOIN_URL}/api/bounties/bounty-123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "bounty-123", "status": "active"},
            )
        )
        result = await atlascoin.get_bounty("bounty-123")
        assert result["status"] == "ok"
        assert result["data"]["id"] == "bounty-123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_not_found_404(self):
        """Returns status=error on 404."""
        respx.get(f"{ATLASCOIN_URL}/api/bounties/missing").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        result = await atlascoin.get_bounty("missing")
        assert result["status"] == "error"
        assert result["status_code"] == 404


# =========================================================================
# Hostile Tests — try to break contract model, verifier, and draft criteria
# =========================================================================


class TestCriterionModelHostile:
    """Hostile edge cases that try to break Criterion creation."""

    def test_from_dict_missing_required_field(self):
        """from_dict with missing 'name' raises TypeError — no graceful fallback."""
        data = {
            "type": "shell",
            "command": "echo ok",
            "pass_when": "exit_code == 0",
            "weight": 1.0,
            # 'name' is missing
        }
        with pytest.raises(TypeError):
            Criterion.from_dict(data)

    def test_from_dict_extra_fields_raises(self):
        """from_dict with unknown fields raises TypeError due to **kwargs in dataclass."""
        data = {
            "name": "test",
            "type": "shell",
            "command": "echo ok",
            "pass_when": "exit_code == 0",
            "weight": 1.0,
            "surprise_field": "gotcha",
            "another_one": True,
        }
        with pytest.raises(TypeError):
            Criterion.from_dict(data)

    def test_contract_from_dict_with_one_invalid_criterion(self):
        """One bad criterion type blows up the entire Contract.from_dict call."""
        data = {
            "soul_purpose": "Test",
            "escrow": 50,
            "bounty_id": "",
            "status": "draft",
            "criteria": [
                {
                    "name": "good",
                    "type": "shell",
                    "command": "echo ok",
                    "pass_when": "exit_code == 0",
                    "weight": 1.0,
                },
                {
                    "name": "bad",
                    "type": "BOGUS_TYPE",
                    "command": "echo fail",
                    "pass_when": "exit_code == 0",
                    "weight": 1.0,
                },
            ],
        }
        with pytest.raises(ValueError, match="BOGUS_TYPE"):
            Contract.from_dict(data)


class TestVerifierHostile:
    """Hostile edge cases targeting the verifier's shell execution."""

    def test_shell_command_injection_is_blocked(self, project_with_session):
        """shlex.split means semicolons are NOT interpreted by the shell.

        After the fix, 'false; echo INJECTED' is passed as a single
        argument to 'false', which fails. The injection does not execute.
        """
        contract = Contract(
            soul_purpose="Test injection",
            escrow=50,
            criteria=[
                Criterion(
                    name="injected",
                    type=CriterionType.SHELL,
                    command="false; echo INJECTED",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        # shlex.split treats this as: ['false;', 'echo', 'INJECTED']
        # 'false;' is not a valid command, so it fails
        assert result["all_passed"] is False

    def test_legitimate_command_still_works(self, project_with_session):
        """Normal commands like 'echo hello' work correctly with shlex.split."""
        contract = Contract(
            soul_purpose="Test normal",
            escrow=50,
            criteria=[
                Criterion(
                    name="normal",
                    type=CriterionType.SHELL,
                    command="echo hello",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True
        assert "hello" in result["results"][0]["output"]

    def test_shell_timeout_fires_on_slow_command(self, project_with_session):
        """Command that sleeps past the 120s timeout should fail gracefully.

        We use a short sleep and mock the timeout to avoid waiting 120s.
        """
        contract = Contract(
            soul_purpose="Test timeout",
            escrow=50,
            criteria=[
                Criterion(
                    name="slow",
                    type=CriterionType.SHELL,
                    command="sleep 200",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        # Mock subprocess.run to raise TimeoutExpired immediately
        with patch(
            "atlas_session.contract.verifier.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="sleep 200", timeout=120),
        ):
            result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False
        assert "timed out" in result["results"][0]["output"].lower()

    def test_shell_massive_output_truncated(self, project_with_session):
        """Command producing massive output gets truncated to 500 chars.

        Generates ~50000 chars of output to stress the truncation boundary.
        """
        contract = Contract(
            soul_purpose="Test massive output",
            escrow=50,
            criteria=[
                Criterion(
                    name="massive",
                    type=CriterionType.SHELL,
                    command="python3 -c \"print('X' * 50000)\"",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True
        output = result["results"][0]["output"]
        assert len(output) <= 500
        # Should be exactly 500 chars (truncated from 50000)
        assert len(output) == 500

    def test_evaluate_string_value_with_numeric_comparison(self):
        """Non-numeric string value with '== 0' returns False, not crash.

        float('not_a_number') raises ValueError, caught by except clause.
        """
        result = _evaluate_pass_when("== 0", value="not_a_number")
        assert result is False

        result = _evaluate_pass_when("> 5", value="hello")
        assert result is False

    def test_file_exists_broken_symlink(self, project_with_session):
        """Broken symlink target: Path.exists() returns False, so criterion fails."""
        import os

        link_path = project_with_session / "broken_link.txt"
        os.symlink("/nonexistent/target/file.txt", str(link_path))
        contract = Contract(
            soul_purpose="Test broken symlink",
            escrow=50,
            criteria=[
                Criterion(
                    name="broken_link",
                    type=CriterionType.FILE_EXISTS,
                    path="broken_link.txt",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False

    def test_context_check_with_list_field_uses_length(self, project_with_session):
        """List-valued field uses len() for shorthand numeric comparison.

        The template active context has 3 open tasks ([ ] placeholders),
        so open_tasks is a list of 3 items, and len(3) != 0.
        '== 0' on a 3-element list should fail. '> 0' should pass.
        """
        # Template has 3 "[ ]" items, so open_tasks has len 3
        fail_contract = Contract(
            soul_purpose="Test list context fail",
            escrow=50,
            criteria=[
                Criterion(
                    name="no_open_tasks",
                    type=CriterionType.CONTEXT_CHECK,
                    field="open_tasks",
                    pass_when="== 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), fail_contract)
        # len([task1, task2, task3]) == 3, not 0 → fails
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False

        pass_contract = Contract(
            soul_purpose="Test list context pass",
            escrow=50,
            criteria=[
                Criterion(
                    name="has_open_tasks",
                    type=CriterionType.CONTEXT_CHECK,
                    field="open_tasks",
                    pass_when="> 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), pass_contract)
        # len([task1, task2, task3]) == 3 > 0 → passes
        assert result["all_passed"] is True
        assert result["results"][0]["passed"] is True


class TestDraftCriteriaHostile:
    """Hostile tests for draft criteria helper priority resolution."""

    def test_multiple_stacks_first_match_wins(self):
        """When detected_stack has multiple entries, the first matching if-branch wins.

        The lookup functions check in order: node, python, rust, go.
        """
        signals = {"detected_stack": ["node", "python"]}
        # 'node' comes first in the if/elif chain, so node commands win
        assert _guess_test_command(signals) == "npm test"
        assert _guess_build_command(signals) == "npm run build"
        assert _guess_lint_command(signals) == "npm run lint"

        # Reverse order: still 'node' wins because if-chain checks node first
        signals_reversed = {"detected_stack": ["python", "node"]}
        assert _guess_test_command(signals_reversed) == "npm test"

    def test_contract_save_overwrites_existing(self, project_with_session):
        """Second save to same location overwrites the first completely."""
        contract_v1 = Contract(
            soul_purpose="Version 1",
            escrow=100,
            criteria=[],
            bounty_id="v1-id",
            status="active",
        )
        contract_v1.save(str(project_with_session))

        loaded = Contract.load(str(project_with_session))
        assert loaded.soul_purpose == "Version 1"
        assert loaded.bounty_id == "v1-id"

        contract_v2 = Contract(
            soul_purpose="Version 2",
            escrow=500,
            criteria=[
                Criterion(
                    name="new_check",
                    type=CriterionType.SHELL,
                    command="echo v2",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
            bounty_id="v2-id",
            status="draft",
        )
        contract_v2.save(str(project_with_session))

        loaded = Contract.load(str(project_with_session))
        assert loaded.soul_purpose == "Version 2"
        assert loaded.escrow == 500
        assert loaded.bounty_id == "v2-id"
        assert loaded.status == "draft"
        assert len(loaded.criteria) == 1
        assert loaded.criteria[0].name == "new_check"


# =========================================================================
# Edge Cases — verifier coverage gaps
# =========================================================================


class TestVerifierEdgeCases:
    """Edge cases in verifier and pass_when evaluator."""

    def test_run_tests_zero_total_weight(self, project_with_session):
        """All criteria with weight=0 should produce score=0, not a division error."""
        contract = Contract(
            soul_purpose="Test zero weight",
            escrow=50,
            criteria=[
                Criterion(
                    name="zero_a",
                    type=CriterionType.SHELL,
                    command="true",
                    pass_when="exit_code == 0",
                    weight=0.0,
                ),
                Criterion(
                    name="zero_b",
                    type=CriterionType.SHELL,
                    command="true",
                    pass_when="exit_code == 0",
                    weight=0.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["score"] == 0
        assert result["all_passed"] is True
        # Should not raise ZeroDivisionError

    def test_shell_output_truncation(self, project_with_session):
        """Shell command output > 500 chars is truncated to 500."""
        # Generate output well over 500 characters
        contract = Contract(
            soul_purpose="Test truncation",
            escrow=50,
            criteria=[
                Criterion(
                    name="long_output",
                    type=CriterionType.SHELL,
                    command="python3 -c \"print('A' * 1000)\"",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is True
        assert len(result["results"][0]["output"]) <= 500

    def test_evaluate_pass_when_malformed_exit_code_expression(self):
        """'exit_code ===== 0' (malformed) returns False gracefully."""
        assert _evaluate_pass_when("exit_code ===== 0", exit_code=0) is False

    def test_file_exists_non_not_empty_on_missing_file(self, project_with_session):
        """file_exists with pass_when != 'not_empty' on missing file fails."""
        contract = Contract(
            soul_purpose="Test missing exists",
            escrow=50,
            criteria=[
                Criterion(
                    name="missing_file",
                    type=CriterionType.FILE_EXISTS,
                    path="totally-missing.txt",
                    pass_when="exit_code == 0",  # not 'not_empty'
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False
        assert "missing" in result["results"][0]["output"]

    def test_file_exists_empty_dir_not_empty(self, project_with_session):
        """file_exists on empty directory with not_empty fails."""
        empty_dir = project_with_session / "empty_dir"
        empty_dir.mkdir()
        contract = Contract(
            soul_purpose="Test empty dir",
            escrow=50,
            criteria=[
                Criterion(
                    name="empty_dir_check",
                    type=CriterionType.FILE_EXISTS,
                    path="empty_dir",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False

    def test_context_check_missing_field(self, project_with_session):
        """context_check with a field not in read_context returns passed=False with 'not found'."""
        contract = Contract(
            soul_purpose="Test missing field edge",
            escrow=50,
            criteria=[
                Criterion(
                    name="check_nonexistent",
                    type=CriterionType.CONTEXT_CHECK,
                    field="completely_fake_field",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        result = run_tests(str(project_with_session), contract)
        assert result["all_passed"] is False
        assert result["results"][0]["passed"] is False
        assert "not found" in result["results"][0]["output"]

    def test_contains_no_matching_text(self):
        """'contains:' with no matching text in output returns False."""
        assert (
            _evaluate_pass_when("contains:NEEDLE", output="haystack without match")
            is False
        )
        assert (
            _evaluate_pass_when("contains:NEEDLE", value="haystack without match")
            is False
        )
        assert _evaluate_pass_when("contains:NEEDLE", output="", value="") is False
