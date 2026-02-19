"""AtlasCoin HTTP client for bounty operations."""

from __future__ import annotations

import httpx

from ..common.config import ATLASCOIN_URL


def _ok_or_error(r: httpx.Response, ok_codes: tuple = (200,)) -> dict:
    """Build standard ok/error response from httpx response."""
    if r.status_code in ok_codes:
        ct = r.headers.get("content-type", "")
        data = r.json() if ct.startswith("application/json") else {}
        return {"status": "ok", "data": data}
    return {
        "status": "error",
        "status_code": r.status_code,
        "body": r.text,
    }


async def health() -> dict:
    """Check AtlasCoin service availability."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{ATLASCOIN_URL}/health")
            if r.status_code == 200:
                ct = r.headers.get("content-type", "")
                data = r.json() if ct.startswith("application/json") else {}
                return {"healthy": True, "url": ATLASCOIN_URL, "data": data}
            return {
                "healthy": False,
                "url": ATLASCOIN_URL,
                "status_code": r.status_code,
            }
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
            return _ok_or_error(r, ok_codes=(200, 201))
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_bounty(bounty_id: str) -> dict:
    """Get bounty status."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}")
            return _ok_or_error(r)
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
            return _ok_or_error(r, ok_codes=(200, 201))
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
            return _ok_or_error(r, ok_codes=(200, 201))
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def settle_bounty(bounty_id: str) -> dict:
    """Settle a verified bounty — distribute tokens."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{ATLASCOIN_URL}/api/bounties/{bounty_id}/settle")
            return _ok_or_error(r, ok_codes=(200, 201))
    except Exception as e:
        return {"status": "error", "error": str(e)}
