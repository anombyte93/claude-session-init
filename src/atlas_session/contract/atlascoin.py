"""AtlasCoin HTTP client for bounty operations."""

from __future__ import annotations

import httpx

from ..common.config import ATLASCOIN_URL


async def health() -> dict:
    """Check AtlasCoin service availability."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{ATLASCOIN_URL}/health")
            if r.status_code == 200:
                return {"healthy": True, "url": ATLASCOIN_URL, "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else {}}
            return {"healthy": False, "url": ATLASCOIN_URL, "status_code": r.status_code}
    except Exception as e:
        return {"healthy": False, "url": ATLASCOIN_URL, "error": str(e)}


async def create_bounty(soul_purpose: str, escrow: int) -> dict:
    """Create a bounty on AtlasCoin."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{ATLASCOIN_URL}/api/bounties",
                json={
                    "poster": "session-lifecycle",
                    "template": soul_purpose,
                    "escrowAmount": escrow,
                },
            )
            return {"status": "ok", "data": r.json()} if r.status_code in (200, 201) else {"status": "error", "status_code": r.status_code, "body": r.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_bounty(bounty_id: str) -> dict:
    """Get bounty status."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}")
            return {"status": "ok", "data": r.json()} if r.status_code == 200 else {"status": "error", "status_code": r.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def submit_solution(bounty_id: str, stake: int, evidence: dict) -> dict:
    """Submit a solution for verification."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/submit",
                json={
                    "claimant": "session-agent",
                    "stakeAmount": stake,
                    "evidence": evidence,
                },
            )
            return {"status": "ok", "data": r.json()} if r.status_code in (200, 201) else {"status": "error", "status_code": r.status_code, "body": r.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def verify_bounty(bounty_id: str, evidence: dict) -> dict:
    """Submit verification evidence."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/verify",
                json={"evidence": evidence},
            )
            return {"status": "ok", "data": r.json()} if r.status_code in (200, 201) else {"status": "error", "status_code": r.status_code, "body": r.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def settle_bounty(bounty_id: str) -> dict:
    """Settle a verified bounty — distribute tokens."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/settle")
            return {"status": "ok", "data": r.json()} if r.status_code in (200, 201) else {"status": "error", "status_code": r.status_code, "body": r.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}
