"""Wallet-based authentication for Open Agora.

Uses EIP-712 typed data signatures for secure, gasless authentication.
Agents sign a challenge message with their wallet to prove identity.

Flow:
1. Client requests a challenge: GET /api/auth/challenge?wallet=0x...
2. Server returns a nonce to sign
3. Client signs the challenge with their wallet
4. Client includes signature in Authorization header: Bearer <wallet>:<signature>:<nonce>
5. Server verifies signature matches wallet

For session-based auth, client can exchange signature for a JWT.
"""

import os
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass
from functools import wraps

from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
import structlog

logger = structlog.get_logger()

# Challenge expiry (5 minutes)
CHALLENGE_EXPIRY_SECONDS = 300

# Session token expiry (24 hours)
SESSION_EXPIRY_SECONDS = 86400

# In-memory stores (use Redis in production)
_pending_challenges: dict[str, dict] = {}  # wallet -> {nonce, expires_at}
_active_sessions: dict[str, dict] = {}  # token -> {wallet, agent_id, expires_at}

# Security settings
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "open-agora.io")


@dataclass
class AuthenticatedAgent:
    """Represents an authenticated agent."""
    wallet: str
    agent_id: Optional[str] = None
    session_token: Optional[str] = None


# EIP-712 typed data for authentication
def get_auth_typed_data(wallet: str, nonce: str) -> dict:
    """Generate EIP-712 typed data for authentication."""
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "AuthRequest": [
                {"name": "wallet", "type": "address"},
                {"name": "nonce", "type": "string"},
                {"name": "statement", "type": "string"},
            ],
        },
        "primaryType": "AuthRequest",
        "domain": {
            "name": "Open Agora",
            "version": "1",
            "chainId": 8453,  # Base mainnet
        },
        "message": {
            "wallet": wallet,
            "nonce": nonce,
            "statement": "Sign this message to authenticate with Open Agora marketplace.",
        },
    }


def create_challenge(wallet: str) -> dict:
    """Create an authentication challenge for a wallet.

    Args:
        wallet: Ethereum wallet address

    Returns:
        Challenge dict with nonce and typed data to sign
    """
    wallet = wallet.lower()
    nonce = f"{uuid.uuid4().hex}-{int(time.time())}"
    expires_at = datetime.utcnow() + timedelta(seconds=CHALLENGE_EXPIRY_SECONDS)

    _pending_challenges[wallet] = {
        "nonce": nonce,
        "expires_at": expires_at,
    }

    typed_data = get_auth_typed_data(wallet, nonce)

    logger.info("auth_challenge_created", wallet=wallet[:10] + "...")

    return {
        "wallet": wallet,
        "nonce": nonce,
        "expires_at": expires_at.isoformat(),
        "typed_data": typed_data,
        "message": f"Sign this message to authenticate with Open Agora.\n\nNonce: {nonce}",
    }


def verify_signature(wallet: str, signature: str, nonce: str) -> bool:
    """Verify a wallet signature against a challenge.

    Args:
        wallet: Ethereum wallet address
        signature: Hex signature from wallet
        nonce: The nonce that was signed

    Returns:
        True if signature is valid
    """
    wallet = wallet.lower()

    # Check if challenge exists and is valid
    challenge = _pending_challenges.get(wallet)
    if not challenge:
        logger.warning("auth_no_challenge", wallet=wallet[:10] + "...")
        return False

    if challenge["nonce"] != nonce:
        logger.warning("auth_nonce_mismatch", wallet=wallet[:10] + "...")
        return False

    if datetime.utcnow() > challenge["expires_at"]:
        logger.warning("auth_challenge_expired", wallet=wallet[:10] + "...")
        del _pending_challenges[wallet]
        return False

    try:
        # Try EIP-712 typed data verification first
        typed_data = get_auth_typed_data(wallet, nonce)
        signable = encode_typed_data(full_message=typed_data)
        recovered = Account.recover_message(signable, signature=signature)

        if recovered.lower() == wallet:
            del _pending_challenges[wallet]
            logger.info("auth_signature_valid", wallet=wallet[:10] + "...", method="eip712")
            return True
    except Exception as e:
        logger.debug("eip712_verify_failed", error=str(e))

    try:
        # Fall back to personal_sign (simpler, more compatible)
        message = f"Sign this message to authenticate with Open Agora.\n\nNonce: {nonce}"
        signable = encode_defunct(text=message)
        recovered = Account.recover_message(signable, signature=signature)

        if recovered.lower() == wallet:
            del _pending_challenges[wallet]
            logger.info("auth_signature_valid", wallet=wallet[:10] + "...", method="personal_sign")
            return True
    except Exception as e:
        logger.warning("auth_verify_failed", wallet=wallet[:10] + "...", error=str(e))

    return False


def create_session(wallet: str, agent_id: Optional[str] = None) -> str:
    """Create a session token for an authenticated wallet.

    Args:
        wallet: Verified wallet address
        agent_id: Optional agent ID if this wallet owns an agent

    Returns:
        Session token string
    """
    wallet = wallet.lower()
    token = hashlib.sha256(f"{wallet}-{uuid.uuid4().hex}-{time.time()}".encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(seconds=SESSION_EXPIRY_SECONDS)

    _active_sessions[token] = {
        "wallet": wallet,
        "agent_id": agent_id,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
    }

    logger.info("session_created", wallet=wallet[:10] + "...", agent_id=agent_id)

    return token


def verify_session(token: str) -> Optional[AuthenticatedAgent]:
    """Verify a session token.

    Args:
        token: Session token

    Returns:
        AuthenticatedAgent if valid, None otherwise
    """
    session = _active_sessions.get(token)
    if not session:
        return None

    if datetime.utcnow() > session["expires_at"]:
        del _active_sessions[token]
        return None

    return AuthenticatedAgent(
        wallet=session["wallet"],
        agent_id=session.get("agent_id"),
        session_token=token,
    )


def invalidate_session(token: str) -> bool:
    """Invalidate a session token (logout).

    Args:
        token: Session token to invalidate

    Returns:
        True if session existed and was invalidated
    """
    if token in _active_sessions:
        del _active_sessions[token]
        return True
    return False


# FastAPI dependency for protected routes
security = HTTPBearer(auto_error=False)


async def get_current_agent(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[AuthenticatedAgent]:
    """FastAPI dependency to get the current authenticated agent.

    Supports two auth methods:
    1. Session token: Bearer <token>
    2. Direct signature: Bearer <wallet>:<signature>:<nonce>
    """
    if not AUTH_ENABLED:
        # Auth disabled - return None (endpoints handle gracefully)
        return None

    if not credentials:
        return None

    token = credentials.credentials

    # Check if it's a session token
    if ":" not in token:
        return verify_session(token)

    # Parse direct signature format: wallet:signature:nonce
    parts = token.split(":", 2)
    if len(parts) != 3:
        return None

    wallet, signature, nonce = parts

    if verify_signature(wallet, signature, nonce):
        return AuthenticatedAgent(wallet=wallet.lower())

    return None


async def require_auth(
    agent: Optional[AuthenticatedAgent] = Depends(get_current_agent),
) -> AuthenticatedAgent:
    """FastAPI dependency that requires authentication.

    Use this for endpoints that must have a valid authenticated agent.
    """
    if not AUTH_ENABLED:
        # Return a mock agent for testing when auth is disabled
        return AuthenticatedAgent(wallet="0x0000000000000000000000000000000000000000")

    if not agent:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use /api/auth/challenge to get a signing challenge.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return agent


def require_agent_owner(agent_id: str):
    """Factory for dependency that requires the caller to own a specific agent.

    Usage:
        @app.put("/api/agents/{agent_id}")
        async def update_agent(
            agent_id: str,
            auth: AuthenticatedAgent = Depends(require_agent_owner("agent_id"))
        ):
            ...
    """
    async def dependency(
        request: Request,
        agent: AuthenticatedAgent = Depends(require_auth),
    ) -> AuthenticatedAgent:
        # Get agent_id from path
        path_agent_id = request.path_params.get("agent_id")

        if not path_agent_id:
            raise HTTPException(status_code=400, detail="No agent_id in path")

        # Check if this wallet owns the agent
        # We need to look up the agent to verify ownership
        from .db import get_agent
        agent_data = await get_agent(path_agent_id)

        if not agent_data:
            raise HTTPException(status_code=404, detail="Agent not found")

        owner_id = agent_data.get("owner_id", "").lower()
        wallet_address = agent_data.get("wallet_address", "").lower()

        # Allow if caller's wallet matches owner_id or wallet_address
        if agent.wallet.lower() not in [owner_id, wallet_address]:
            raise HTTPException(
                status_code=403,
                detail="You don't own this agent",
            )

        agent.agent_id = path_agent_id
        return agent

    return dependency


def require_job_poster(job_id_param: str = "job_id"):
    """Factory for dependency that requires the caller to be the job poster.

    Verifies that the authenticated wallet matches the job's poster_wallet.

    Usage:
        @app.post("/api/jobs/{job_id}/select-bid/{bid_id}")
        async def select_bid(
            job_id: str,
            bid_id: str,
            auth: AuthenticatedAgent = Depends(require_job_poster())
        ):
            ...
    """
    async def dependency(
        request: Request,
        agent: AuthenticatedAgent = Depends(require_auth),
    ) -> AuthenticatedAgent:
        # Get job_id from path
        path_job_id = request.path_params.get(job_id_param)

        if not path_job_id:
            raise HTTPException(status_code=400, detail=f"No {job_id_param} in path")

        # Look up job to verify poster ownership
        from .db import get_job
        job_data = await get_job(path_job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        poster_wallet = job_data.get("poster_wallet", "").lower()
        poster_id = job_data.get("poster_id", "").lower()

        # Allow if caller's wallet matches poster_wallet or poster_id
        if agent.wallet.lower() not in [poster_wallet, poster_id]:
            raise HTTPException(
                status_code=403,
                detail="Only the job poster can perform this action",
            )

        return agent

    return dependency


def require_bid_poster():
    """Factory for dependency that requires the caller to be the job poster for a bid.

    Looks up the bid to get job_id, then verifies poster ownership.

    Usage:
        @app.post("/api/bids/{bid_id}/reject")
        async def reject_bid(
            bid_id: str,
            auth: AuthenticatedAgent = Depends(require_bid_poster())
        ):
            ...
    """
    async def dependency(
        request: Request,
        agent: AuthenticatedAgent = Depends(require_auth),
    ) -> AuthenticatedAgent:
        # Get bid_id from path
        path_bid_id = request.path_params.get("bid_id")

        if not path_bid_id:
            raise HTTPException(status_code=400, detail="No bid_id in path")

        # Look up bid to get job_id
        from .db import get_bid, get_job
        bid_data = await get_bid(path_bid_id)

        if not bid_data:
            raise HTTPException(status_code=404, detail="Bid not found")

        job_id = bid_data.get("job_id")
        job_data = await get_job(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        poster_wallet = job_data.get("poster_wallet", "").lower()
        poster_id = job_data.get("poster_id", "").lower()

        # Allow if caller's wallet matches poster_wallet or poster_id
        if agent.wallet.lower() not in [poster_wallet, poster_id]:
            raise HTTPException(
                status_code=403,
                detail="Only the job poster can perform this action",
            )

        return agent

    return dependency


# Cleanup expired challenges/sessions periodically
def cleanup_expired():
    """Remove expired challenges and sessions."""
    now = datetime.utcnow()

    expired_challenges = [
        w for w, c in _pending_challenges.items()
        if c["expires_at"] < now
    ]
    for w in expired_challenges:
        del _pending_challenges[w]

    expired_sessions = [
        t for t, s in _active_sessions.items()
        if s["expires_at"] < now
    ]
    for t in expired_sessions:
        del _active_sessions[t]

    if expired_challenges or expired_sessions:
        logger.info(
            "auth_cleanup",
            challenges=len(expired_challenges),
            sessions=len(expired_sessions),
        )
