#!/usr/bin/env python3
"""Create the marketplace escrow wallet for AgentBazaar."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


async def create_marketplace_wallet():
    """Create the marketplace escrow wallet using CDP SDK."""
    try:
        from cdp import CdpClient
    except ImportError:
        print("ERROR: cdp-sdk not installed. Run: pip install cdp-sdk")
        sys.exit(1)

    # Check for required env vars
    api_key_id = os.getenv("CDP_API_KEY_ID")
    api_key_secret = os.getenv("CDP_API_KEY_SECRET")
    wallet_secret = os.getenv("CDP_WALLET_SECRET")
    network = os.getenv("CDP_NETWORK", "base-sepolia")

    if not api_key_id:
        print("ERROR: CDP_API_KEY_ID not set in .env")
        sys.exit(1)
    if not api_key_secret:
        print("ERROR: CDP_API_KEY_SECRET not set in .env")
        sys.exit(1)
    if not wallet_secret:
        print("ERROR: CDP_WALLET_SECRET not set in .env")
        sys.exit(1)

    print("=" * 50)
    print("AgentBazaar Marketplace Wallet Setup")
    print("=" * 50)
    print(f"Network: {network}")
    print(f"API Key ID: {api_key_id[:20]}...")
    print()

    try:
        async with CdpClient() as cdp:
            print("✓ Connected to Coinbase CDP")

            # Create the marketplace escrow account
            print("Creating marketplace escrow wallet...")
            account = await cdp.evm.create_account()

            print()
            print("=" * 50)
            print("SUCCESS! Marketplace wallet created")
            print("=" * 50)
            print(f"Address: {account.address}")
            print()
            print("Add this to your .env file:")
            print(f"X402_MARKETPLACE_ADDRESS={account.address}")
            print()
            print(f"View on explorer: https://sepolia.basescan.org/address/{account.address}")
            print()
            print("Next steps:")
            print("1. Add the address to your .env")
            print("2. Fund with test ETH: https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet")
            print("3. Fund with test USDC: https://faucet.circle.com/ (select Base Sepolia)")
            print("4. Set USE_REAL_X402=true when ready")

            return account.address

    except Exception as e:
        print(f"ERROR: {e}")
        print()
        print("Troubleshooting:")
        print("- Check your CDP_API_KEY_ID is correct")
        print("- Check your CDP_API_KEY_SECRET is the full key")
        print("- Check your CDP_WALLET_SECRET is set")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(create_marketplace_wallet())
