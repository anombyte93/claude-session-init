"""Integration tests: contract lifecycle state transitions.

Tests the contract state machine from draft through active, verification,
and settlement, including deterministic test runner behavior.
"""

import httpx
import pytest
import respx

from atlas_session.contract.model import Contract, Criterion, CriterionType
from atlas_session.contract.verifier import run_tests
from atlas_session.contract import atlascoin
from atlas_session.common.config import ATLASCOIN_URL


# ---------------------------------------------------------------------------
# TestContractStateTransitions
# ---------------------------------------------------------------------------


class TestContractStateTransitions:
    """Test contract state machine: draft -> active -> verified -> settled."""

    def test_draft_to_active_local(self, project_with_session):
        """Create a draft Contract, set to active, save, reload, verify."""
        pd = str(project_with_session)

        # Create contract in draft state
        contract = Contract(
            soul_purpose="Build a widget factory",
            escrow=100,
            criteria=[
                Criterion(
                    name="tests_pass",
                    type=CriterionType.SHELL,
                    command="echo ok",
                    pass_when="exit_code == 0",
                    weight=2.0,
                ),
                Criterion(
                    name="session_exists",
                    type=CriterionType.FILE_EXISTS,
                    path="session-context/CLAUDE-activeContext.md",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
        )
        assert contract.status == "draft"

        # Transition to active
        contract.status = "active"

        # Save to disk
        saved_path = contract.save(pd)
        assert saved_path.is_file()
        assert saved_path.name == "contract.json"

        # Reload from disk
        reloaded = Contract.load(pd)
        assert reloaded is not None
        assert reloaded.status == "active"
        assert reloaded.soul_purpose == "Build a widget factory"
        assert reloaded.escrow == 100
        assert len(reloaded.criteria) == 2
        assert reloaded.criteria[0].name == "tests_pass"
        assert reloaded.criteria[0].type == CriterionType.SHELL
        assert reloaded.criteria[1].name == "session_exists"
        assert reloaded.criteria[1].type == CriterionType.FILE_EXISTS

    def test_run_tests_on_active_contract(self, project_with_session):
        """Create active contract with passing criteria, run_tests, verify all_passed."""
        pd = str(project_with_session)

        contract = Contract(
            soul_purpose="Test contract",
            escrow=50,
            criteria=[
                Criterion(
                    name="echo_test",
                    type=CriterionType.SHELL,
                    command="echo hello",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
                Criterion(
                    name="session_context_exists",
                    type=CriterionType.FILE_EXISTS,
                    path="session-context/CLAUDE-activeContext.md",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
            status="active",
        )

        results = run_tests(pd, contract)
        assert results["all_passed"] is True
        assert results["score"] == 100.0
        assert len(results["results"]) == 2
        assert all(r["passed"] for r in results["results"])
        assert "2/2" in results["summary"]

    def test_partial_pass(self, project_with_session):
        """One passing + one failing criterion: verify score and all_passed=False."""
        pd = str(project_with_session)

        contract = Contract(
            soul_purpose="Partial test",
            escrow=50,
            criteria=[
                Criterion(
                    name="passes",
                    type=CriterionType.SHELL,
                    command="echo ok",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
                Criterion(
                    name="fails",
                    type=CriterionType.FILE_EXISTS,
                    path="nonexistent/file.txt",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
            status="active",
        )

        results = run_tests(pd, contract)
        assert results["all_passed"] is False
        assert results["score"] == 50.0
        assert results["results"][0]["passed"] is True
        assert results["results"][1]["passed"] is False
        assert "1/2" in results["summary"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_full_lifecycle_with_mocked_api(self, project_with_session):
        """Full lifecycle: create_bounty -> Contract -> run_tests ->
        submit_solution -> verify_bounty -> settle_bounty -> verify settled."""
        pd = str(project_with_session)
        bounty_id = "bounty-test-123"

        # 1. Mock create_bounty
        respx.post(f"{ATLASCOIN_URL}/api/bounties").mock(
            return_value=httpx.Response(
                201,
                json={"id": bounty_id, "status": "active", "escrow": 100},
            )
        )

        create_result = await atlascoin.create_bounty("Build widgets", 100)
        assert create_result["status"] == "ok"
        assert create_result["data"]["id"] == bounty_id

        # 2. Create local Contract with the bounty_id
        contract = Contract(
            soul_purpose="Build widgets",
            escrow=100,
            criteria=[
                Criterion(
                    name="echo_test",
                    type=CriterionType.SHELL,
                    command="echo ok",
                    pass_when="exit_code == 0",
                    weight=1.0,
                ),
                Criterion(
                    name="context_exists",
                    type=CriterionType.FILE_EXISTS,
                    path="session-context/CLAUDE-activeContext.md",
                    pass_when="not_empty",
                    weight=1.0,
                ),
            ],
            bounty_id=bounty_id,
            status="active",
        )
        contract.save(pd)

        # 3. Run tests locally
        test_results = run_tests(pd, contract)
        assert test_results["all_passed"] is True
        assert test_results["score"] == 100.0

        # 4. Mock submit_solution
        respx.post(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/submit").mock(
            return_value=httpx.Response(
                200,
                json={"status": "submitted", "bountyId": bounty_id},
            )
        )

        submit_result = await atlascoin.submit_solution(
            bounty_id,
            stake=10,
            evidence={"test_results": test_results},
        )
        assert submit_result["status"] == "ok"
        contract.status = "submitted"
        contract.save(pd)

        # 5. Mock verify_bounty
        respx.post(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/verify").mock(
            return_value=httpx.Response(
                200,
                json={"verified": True, "bountyId": bounty_id},
            )
        )

        verify_result = await atlascoin.verify_bounty(
            bounty_id,
            evidence={"passed": True, "score": 100.0},
        )
        assert verify_result["status"] == "ok"
        contract.status = "verified"
        contract.save(pd)

        # 6. Mock settle_bounty
        respx.post(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/settle").mock(
            return_value=httpx.Response(
                200,
                json={"settled": True, "bountyId": bounty_id, "tokens": 100},
            )
        )

        settle_result = await atlascoin.settle_bounty(bounty_id)
        assert settle_result["status"] == "ok"
        contract.status = "settled"
        contract.save(pd)

        # 7. Verify final state on disk
        final = Contract.load(pd)
        assert final is not None
        assert final.status == "settled"
        assert final.bounty_id == bounty_id
        assert final.escrow == 100
        assert len(final.criteria) == 2
