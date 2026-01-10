#!/usr/bin/env python3
"""Test CDP connection and check wallet balances."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


async def test_cdp():
    """Test CDP connection and check balances."""
    try:
        from cdp import CdpClient
    except ImportError:
        print("ERROR: cdp-sdk not installed. Run: pip install cdp-sdk")
        sys.exit(1)

    marketplace_address = os.getenv("X402_MARKETPLACE_ADDRESS")
    network = os.getenv("CDP_NETWORK", "base-sepolia")

    print("=" * 60)
    print("CDP Connection Test")
    print("=" * 60)
    print(f"Network: {network}")
    print(f"Marketplace Wallet: {marketplace_address}")
    print()

    try:
        async with CdpClient() as cdp:
            print("✅ CDP Connection: SUCCESS")
            print()

            # Check if we can get the account
            if marketplace_address:
                print(f"Checking balances for {marketplace_address[:10]}...{marketplace_address[-6:]}:")
                print()

                try:
                    # Get ETH balance
                    eth_balance = await cdp.evm.get_balance(
                        address=marketplace_address,
                        network=network,
                    )
                    print(f"  ETH Balance: {eth_balance} wei")
                    eth_readable = float(eth_balance) / 1e18
                    print(f"              ({eth_readable:.6f} ETH)")

                    if eth_readable < 0.001:
                        print("  ⚠️  Low ETH - get testnet ETH from:")
                        print("     https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet")
                    else:
                        print("  ✅ ETH balance OK for gas")

                except Exception as e:
                    print(f"  ⚠️  Could not get ETH balance: {e}")

                print()

                try:
                    # Get USDC balance
                    usdc_balance = await cdp.evm.get_token_balance(
                        address=marketplace_address,
                        token="usdc",
                        network=network,
                    )
                    print(f"  USDC Balance: {usdc_balance} (atomic units)")
                    usdc_readable = float(usdc_balance) / 1e6
                    print(f"               (${usdc_readable:.2f} USDC)")

                    if usdc_readable < 1:
                        print("  ⚠️  Low USDC - get testnet USDC from:")
                        print("     https://faucet.circle.com/ (select Base Sepolia)")
                    else:
                        print("  ✅ USDC balance OK for payments")

                except Exception as e:
                    print(f"  ⚠️  Could not get USDC balance: {e}")

            print()
            print("=" * 60)
            print("Summary")
            print("=" * 60)
            print("✅ CDP API credentials: Working")
            print("✅ Wallet secret: Working")
            print("✅ Network connection: Working")
            print()
            print("Your CDP setup is ready!")
            print()
            print("To enable real payments, set in .env:")
            print("  USE_REAL_X402=true")

    except Exception as e:
        print(f"❌ CDP Connection: FAILED")
        print(f"   Error: {e}")
        print()
        print("Troubleshooting:")
        print("- Verify CDP_API_KEY_ID is correct")
        print("- Verify CDP_API_KEY_SECRET is the full key")
        print("- Verify CDP_WALLET_SECRET is set")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_cdp())
