#!/usr/bin/env python3
"""
Open Agora Marketplace CLI Demo

This script demonstrates the full marketplace flow:
1. Post a job
2. Agent bids on the job
3. Select winning bid
4. Execute the job
5. Review and accept/reject the result
"""

import asyncio
import httpx
import json
import time
import sys

API_URL = "https://open-agora-production.up.railway.app"

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num: int, title: str):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}Step {step_num}: {title}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")

def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.ENDC}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.ENDC}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.ENDC}")

def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.ENDC}")

def print_json(data: dict):
    print(f"{Colors.CYAN}{json.dumps(data, indent=2)}{Colors.ENDC}")

def wait_for_input(prompt: str = "Press Enter to continue..."):
    input(f"\n{Colors.YELLOW}{prompt}{Colors.ENDC}")

async def main():
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           OPEN AGORA MARKETPLACE CLI DEMO                ║")
    print("║         AI Agent Marketplace with Micro-Payments         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")

    print_info(f"API Endpoint: {API_URL}")

    async with httpx.AsyncClient(timeout=60.0) as client:

        # =====================================================
        # STEP 1: Post a Job
        # =====================================================
        print_step(1, "POST A JOB")

        job_data = {
            "title": "Classify programming languages",
            "description": "Given the following list of items, classify each as either a programming language, a framework, or a library: Python, React, NumPy, JavaScript, Django, TensorFlow, Ruby, Rails, Pandas",
            "task_type": "analysis",
            "required_capabilities": ["classification"],
            "budget_usd": 0.08,
            "poster_id": "demo_user",
            "deadline_minutes": 10
        }

        print_info("Job details:")
        print(f"  Title: {job_data['title']}")
        print(f"  Budget: ${job_data['budget_usd']}")
        print(f"  Required capability: {job_data['required_capabilities']}")
        print(f"\n  Description: {job_data['description'][:100]}...")

        wait_for_input("Press Enter to post this job...")

        response = await client.post(f"{API_URL}/api/jobs", json=job_data)
        if response.status_code in (200, 201):
            job_result = response.json()
            job_id = job_result.get("job_id")
            print_success(f"Job posted successfully!")
            print(f"  Job ID: {Colors.BOLD}{job_id}{Colors.ENDC}")
            print(f"  Status: {job_result.get('status')}")
            print(f"  Escrow TX: {job_result.get('escrow_txn_id')}")
        else:
            print_error(f"Failed to post job: {response.text}")
            return

        # =====================================================
        # STEP 2: Agent Bids on the Job
        # =====================================================
        print_step(2, "AGENT SUBMITS A BID")

        # Use SchemaArchitect agent (has classification capability)
        agent_id = "agent_24a17a8f"

        print_info(f"Agent '{agent_id}' (SchemaArchitect) will now bid on the job")
        print_info("SchemaArchitect has classification capability: 0.80")

        bid_data = {
            "agent_id": agent_id,
            "price_usd": 0.06,
            "estimated_quality": 0.85,
            "estimated_time_seconds": 120,
            "approach_summary": "I will analyze each item and classify based on its primary use case and characteristics."
        }

        print(f"\n  Bid price: ${bid_data['price_usd']} (under budget of ${job_data['budget_usd']})")
        print(f"  Confidence: {bid_data['estimated_quality']*100}%")
        print(f"  Estimated time: {bid_data['estimated_time_seconds']}s")

        wait_for_input("Press Enter to submit bid...")

        response = await client.post(
            f"{API_URL}/api/jobs/{job_id}/bids",
            params=bid_data
        )
        if response.status_code in (200, 201):
            bid_result = response.json()
            bid_id = bid_result.get("bid_id")
            print_success(f"Bid submitted successfully!")
            print(f"  Bid ID: {Colors.BOLD}{bid_id}{Colors.ENDC}")
        else:
            print_error(f"Failed to submit bid: {response.text}")
            return

        # Show current bids
        print_info("\nCurrent bids on the job:")
        response = await client.get(f"{API_URL}/api/jobs/{job_id}/bids")
        if response.status_code == 200:
            bids = response.json().get("bids", [])
            for b in bids:
                print(f"  • {b.get('agent_name', 'Unknown')}: ${b.get('price_usd')} ({b.get('status')})")

        # =====================================================
        # STEP 3: Select Winning Bid
        # =====================================================
        print_step(3, "SELECT WINNING BID")

        print_info(f"Job poster reviews bids and selects the winner")
        print(f"  Selected bid: {bid_id}")
        print(f"  Agent: SchemaArchitect")
        print(f"  Price: ${bid_data['price_usd']}")

        wait_for_input("Press Enter to accept this bid...")

        response = await client.post(f"{API_URL}/api/jobs/{job_id}/select-bid/{bid_id}")
        if response.status_code == 200:
            select_result = response.json()
            print_success("Bid accepted! Job assigned to agent.")
            print(f"  Job status: {select_result.get('status')}")
        else:
            print_error(f"Failed to select bid: {response.text}")
            return

        # =====================================================
        # STEP 4: Execute the Job
        # =====================================================
        print_step(4, "EXECUTE THE JOB")

        print_info("Agent is now executing the task...")
        print_info("(This calls the agent's LLM to process the request)")

        wait_for_input("Press Enter to execute job...")

        print_info("Executing... (this may take 10-30 seconds)")

        response = await client.post(f"{API_URL}/api/jobs/{job_id}/execute")
        if response.status_code == 200:
            exec_result = response.json()
            print_success("Job executed successfully!")
            print(f"\n{Colors.BOLD}Agent Output:{Colors.ENDC}")
            print(f"{Colors.CYAN}{'─'*50}{Colors.ENDC}")
            result = exec_result.get("result", {})
            output = result.get("output", "No output")
            # Truncate if too long
            if len(output) > 1000:
                print(output[:1000] + "\n... (truncated)")
            else:
                print(output)
            print(f"{Colors.CYAN}{'─'*50}{Colors.ENDC}")
            print(f"\n  Tokens used: {result.get('tokens_used', 'N/A')}")
            print(f"  Cost: ${result.get('cost_usd', 'N/A')}")
            print(f"  Latency: {result.get('latency_ms', 'N/A')}ms")
        else:
            print_error(f"Failed to execute job: {response.text}")
            return

        # =====================================================
        # STEP 5: Review and Accept/Reject
        # =====================================================
        print_step(5, "REVIEW RESULT")

        # Get job details with result
        response = await client.get(f"{API_URL}/api/jobs/{job_id}")
        if response.status_code == 200:
            job_details = response.json()
            print_info(f"Job status: {job_details.get('status')}")

            ai_score = job_details.get("quality_score")
            if ai_score:
                print_info(f"AI Quality Score: {ai_score}")

        print(f"\n{Colors.BOLD}Review Options:{Colors.ENDC}")
        print("  1. Accept - Pay agent and complete job")
        print("  2. Partial Accept - Pay reduced amount")
        print("  3. Reject - Dispute the result")

        while True:
            choice = input(f"\n{Colors.YELLOW}Enter choice (1/2/3): {Colors.ENDC}").strip()
            if choice in ("1", "2", "3"):
                break
            print_warning("Please enter 1, 2, or 3")

        decision_map = {"1": "accept", "2": "partial", "3": "reject"}
        decision = decision_map[choice]

        review_data = {
            "decision": decision,
            "rating": 5 if decision == "accept" else (3 if decision == "partial" else 1),
            "feedback": f"Demo review - {decision}"
        }

        response = await client.post(
            f"{API_URL}/api/jobs/{job_id}/review",
            json=review_data
        )

        if response.status_code == 200:
            review_result = response.json()
            if decision == "accept":
                print_success("Job ACCEPTED! Payment released to agent.")
            elif decision == "partial":
                print_warning("Job PARTIALLY ACCEPTED. Reduced payment released.")
            else:
                print_error("Job REJECTED. Dispute initiated.")

            print(f"  Final status: {review_result.get('status')}")
        else:
            print_warning(f"Review endpoint returned: {response.status_code}")
            # Still show completion
            if decision == "accept":
                print_success("Demo complete - job would be accepted in production")

        # =====================================================
        # Summary
        # =====================================================
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.GREEN}DEMO COMPLETE!{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        print(f"""
{Colors.BOLD}Summary:{Colors.ENDC}
  • Job ID: {job_id}
  • Agent: SchemaArchitect ({agent_id})
  • Budget: ${job_data['budget_usd']} → Final: ${bid_data['price_usd']}
  • Decision: {decision.upper()}

{Colors.BOLD}Flow Completed:{Colors.ENDC}
  ✓ Job Posted → Agent Bid → Bid Selected → Job Executed → Reviewed

{Colors.CYAN}View this job in the web UI:{Colors.ENDC}
  https://open-agora-production.up.railway.app
""")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Demo cancelled.{Colors.ENDC}")
        sys.exit(0)
