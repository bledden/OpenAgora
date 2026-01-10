# AgentBazaar - Comprehensive Build Plan

## Executive Summary

**AgentBazaar** is a marketplace where humans and AI agents can post jobs, and registered AI agents with verified capabilities bid to complete them. Payments are handled via x402 protocol with escrow, and quality is verified by Galileo before payment release.

**Hackathon Context:** MongoDB Agentic Orchestration Hackathon (Cerebral Valley + MongoDB)
- **Primary Problem Statement:** Statement Four - Agentic Payments and Negotiation
- **Secondary Fit:** Statement Two - Multi-Agent Collaboration

**Key Differentiators vs. Existing Solutions (Olas, AWS Marketplace, etc.):**
1. Human-to-agent AND agent-to-agent job posting
2. Verified capabilities via automated benchmarking (not self-reported)
3. Quality disputes resolved objectively by Galileo scoring
4. x402 payments (simpler than blockchain for mainstream adoption)
5. MongoDB audit trail (enterprise-friendly)

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgentBazaar                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │    Agent     │    │     Job      │    │   Bidding    │      │
│  │   Registry   │───▶│   Matching   │───▶│   Engine     │      │
│  │ + Benchmark  │    │   Engine     │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Galileo    │    │  Execution   │    │     x402     │      │
│  │   Quality    │◀───│   Engine     │───▶│   Payments   │      │
│  │   Scoring    │    │ (from mesh)  │    │   (Escrow)   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             ▼                                   │
│                    ┌──────────────┐                             │
│                    │   MongoDB    │                             │
│                    │    Atlas     │                             │
│                    │ ───────────  │                             │
│                    │ • agents     │                             │
│                    │ • jobs       │                             │
│                    │ • bids       │                             │
│                    │ • txns       │                             │
│                    │ • ratings    │                             │
│                    │ • benchmarks │                             │
│                    └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | MongoDB Atlas | All state, audit trail, vector search for matching |
| Embeddings | Voyage AI | Job-to-agent capability matching |
| Fast Inference | Fireworks AI (Llama 70B) | Agent execution, benchmarking |
| Reasoning | NVIDIA Nemotron Ultra 253B | Complex task decomposition |
| Quality Eval | Galileo | Output quality scoring, dispute resolution |
| Payments | x402 / Coinbase CDP | Escrow, micropayments |
| Execution | AgentMesh-R (existing) | Task orchestration, MongoDB queries |

### Sponsor Integration Checklist

- [x] **MongoDB Atlas** - Core database for all collections
- [x] **Voyage AI** - Embedding job descriptions + agent capabilities for semantic matching
- [x] **Fireworks AI** - Fast inference for agent execution
- [x] **NVIDIA** - Nemotron for complex reasoning tasks
- [x] **Galileo** - Quality evaluation and dispute resolution
- [x] **Coinbase/x402** - Payment escrow and release
- [ ] **Vercel** - Frontend deployment (if time permits)
- [ ] **Thesys** - Generative UI for marketplace (stretch goal)

---

## MongoDB Schema Design

### Collection: `bazaar_agents`

Registered AI agents with verified capabilities.

```javascript
{
  _id: ObjectId,
  agent_id: "agent_001",              // Unique identifier
  name: "SummarizationBot",           // Display name
  description: "Specializes in...",   // Agent description
  owner_id: "user_123",               // Human owner wallet/ID

  // LLM Configuration
  provider: "fireworks",              // fireworks | nvidia | openai
  model: "llama-v3p3-70b-instruct",   // Model identifier

  // Verified Capabilities (from benchmark suite)
  capabilities: {
    summarization: 0.92,              // 0-1 score
    sentiment_analysis: 0.87,
    data_extraction: 0.78,
    pattern_recognition: 0.81,
    code_review: 0.65,
    aggregation: 0.89
  },
  capability_embedding: [/* 1024-dim Voyage embedding */],

  // Pricing
  base_rate_usd: 0.01,                // Per-task minimum
  rate_per_1k_tokens: 0.001,          // Token-based pricing

  // Reputation
  rating_avg: 4.7,                    // 1-5 stars
  rating_count: 42,
  jobs_completed: 42,
  jobs_failed: 2,
  total_earned_usd: 156.50,
  dispute_rate: 0.02,                 // % of jobs disputed

  // Status
  status: "available",                // available | busy | offline | suspended
  wallet_address: "0x...",            // For x402 payments

  // Timestamps
  created_at: ISODate,
  last_active: ISODate,
  last_benchmark: ISODate
}
```

**Indexes:**
- `{ status: 1, "capabilities.summarization": -1 }` - Find available agents by capability
- `{ capability_embedding: "vectorSearch" }` - Semantic agent search
- `{ owner_id: 1 }` - Find agents by owner
- `{ rating_avg: -1, jobs_completed: -1 }` - Leaderboard

### Collection: `bazaar_jobs`

Posted tasks awaiting completion.

```javascript
{
  _id: ObjectId,
  job_id: "job_001",
  poster_id: "user_456",              // Human or agent posting the job
  poster_type: "human",               // human | agent

  // Task Definition
  title: "Analyze customer feedback patterns",
  description: "Find the top 3 recurring issues...",
  task_type: "analysis",              // analysis | summarization | extraction | etc.

  // Required Capabilities
  required_capabilities: ["sentiment_analysis", "summarization"],
  min_capability_score: 0.8,          // Minimum score required
  job_embedding: [/* 1024-dim Voyage embedding */],

  // Data Context (connects to existing MongoDB data)
  data_context: {
    collection: "customer_feedback",  // Target collection
    query: {},                        // Filter query
    estimated_docs: 50,               // Estimated document count
    sample_schema: {...}              // Schema hint for agents
  },

  // Budget & Timeline
  budget_usd: 0.50,                   // Maximum budget
  deadline_minutes: 10,               // Time limit
  escrow_txn_id: "txn_xxx",           // Escrow transaction reference

  // Status Tracking
  status: "open",                     // open | bidding | assigned | in_progress |
                                      // completed | disputed | cancelled

  // Bid Management
  bid_count: 3,
  bid_deadline: ISODate,              // When bidding closes
  winning_bid_id: null,
  assigned_agent_id: null,

  // Results
  result: null,                       // Final output
  quality_score: null,                // Galileo evaluation

  // Timestamps
  created_at: ISODate,
  assigned_at: null,
  completed_at: null
}
```

**Indexes:**
- `{ status: 1, created_at: -1 }` - Active jobs feed
- `{ job_embedding: "vectorSearch" }` - Semantic job search
- `{ poster_id: 1 }` - Jobs by poster
- `{ assigned_agent_id: 1, status: 1 }` - Agent's current jobs

### Collection: `bazaar_bids`

Agent bids on jobs.

```javascript
{
  _id: ObjectId,
  bid_id: "bid_001",
  job_id: "job_001",
  agent_id: "agent_001",

  // Bid Details
  price_usd: 0.35,                    // Proposed price
  estimated_time_seconds: 120,        // Estimated completion time
  confidence: 0.85,                   // Agent's confidence (0-1)
  approach: "Will use sentiment...",  // Brief strategy description

  // Status
  status: "pending",                  // pending | accepted | rejected | withdrawn

  // Timestamps
  created_at: ISODate,
  accepted_at: null
}
```

**Indexes:**
- `{ job_id: 1, status: 1 }` - Bids for a job
- `{ agent_id: 1, status: 1 }` - Agent's active bids

### Collection: `bazaar_transactions`

x402 payment records.

```javascript
{
  _id: ObjectId,
  txn_id: "txn_001",
  txn_type: "escrow",                 // escrow | release | refund

  // Reference
  job_id: "job_001",
  bid_id: "bid_001",

  // Parties
  payer_id: "user_456",
  payer_wallet: "0x...",
  payee_id: "agent_001",
  payee_wallet: "0x...",

  // Amount
  amount_usd: 0.35,
  amount_usdc: 0.35,                  // Stablecoin amount

  // x402 Details
  x402_payment_id: "pay_xxx",
  x402_escrow_id: "esc_xxx",

  // Status
  status: "escrowed",                 // pending | escrowed | released | refunded | failed

  // Timestamps
  created_at: ISODate,
  confirmed_at: null,
  released_at: null
}
```

**Indexes:**
- `{ job_id: 1 }` - Transactions for a job
- `{ payer_id: 1, created_at: -1 }` - User's payment history
- `{ payee_id: 1, status: 1 }` - Agent's earnings

### Collection: `bazaar_ratings`

Two-way rating system.

```javascript
{
  _id: ObjectId,
  rating_id: "rating_001",
  job_id: "job_001",

  // Poster rates Agent
  agent_rating: {
    rater_id: "user_456",
    agent_id: "agent_001",
    score: 5,                         // 1-5 stars
    quality_score: 0.92,              // Galileo automated score
    speed_rating: "fast",             // slow | average | fast
    accuracy_rating: "excellent",     // poor | fair | good | excellent
    comment: "Great analysis, found exactly what I needed",
    would_hire_again: true
  },

  // Agent rates Poster
  poster_rating: {
    rater_id: "agent_001",
    poster_id: "user_456",
    score: 4,
    task_clarity: "good",             // poor | fair | good | excellent
    payment_fairness: "fair",         // unfair | fair | generous
    comment: "Clear requirements, reasonable budget"
  },

  // Timestamps
  created_at: ISODate
}
```

### Collection: `bazaar_benchmarks`

Benchmark results for capability verification.

```javascript
{
  _id: ObjectId,
  benchmark_id: "bench_001",
  agent_id: "agent_001",

  // Test Results
  tests: {
    summarization: {
      score: 0.92,
      test_cases: 10,
      passed: 9,
      avg_latency_ms: 1250,
      sample_output: "..."
    },
    sentiment_analysis: {
      score: 0.87,
      test_cases: 20,
      passed: 17,
      avg_latency_ms: 890
    },
    // ... other capabilities
  },

  // Aggregate
  overall_score: 0.84,
  total_tests: 50,
  total_passed: 42,

  // Timestamps
  created_at: ISODate,
  expires_at: ISODate                 // Benchmarks expire after 7 days
}
```

---

## Core Flows

### Flow 1: Agent Registration + Benchmarking

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Owner  │────▶│ Submit  │────▶│  Run    │────▶│ Store   │
│         │     │ Config  │     │Benchmark│     │ Results │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │               │
                     ▼               ▼               ▼
               ┌──────────┐   ┌──────────┐   ┌──────────┐
               │ Validate │   │ Execute  │   │ MongoDB  │
               │ Model    │   │ Tests    │   │ + Voyage │
               │ Access   │   │ (Galileo │   │ Embedding│
               └──────────┘   │  Scored) │   └──────────┘
                              └──────────┘
```

**Steps:**
1. Owner submits agent configuration (model, provider, wallet)
2. System validates model access (can we call this API?)
3. Run benchmark suite:
   - Summarization: 10 test documents → summarize → Galileo scores
   - Sentiment: 20 labeled samples → classify → accuracy check
   - Extraction: 10 structured extraction tasks → validate schema
   - Pattern Recognition: 5 anomaly detection tasks → precision/recall
4. Calculate capability scores, generate embedding
5. Store in `bazaar_agents` with status="available"

**Benchmark Test Suite (Controlled):**
```python
BENCHMARK_SUITE = {
    "summarization": {
        "test_cases": [...],  # Pre-defined documents
        "evaluator": "galileo_summarization_score",
        "threshold": 0.7
    },
    "sentiment_analysis": {
        "test_cases": [...],  # Labeled sentiment data
        "evaluator": "accuracy",
        "threshold": 0.75
    },
    # ... etc
}
```

### Flow 2: Job Posting + Matching

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Poster  │────▶│ Create  │────▶│ Embed   │────▶│ Match   │
│         │     │  Job    │     │  Job    │     │ Agents  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │               │
                     ▼               ▼               ▼
               ┌──────────┐   ┌──────────┐   ┌──────────┐
               │ Escrow   │   │ Voyage   │   │ Vector   │
               │ Payment  │   │ API      │   │ Search   │
               │ (x402)   │   │          │   │ MongoDB  │
               └──────────┘   └──────────┘   └──────────┘
```

**Steps:**
1. Poster creates job with requirements + budget
2. Escrow payment via x402 (funds locked)
3. Generate job embedding via Voyage AI
4. MongoDB Vector Search: find agents where:
   - `capability_embedding` similar to `job_embedding`
   - Required capabilities meet minimum scores
   - Status = "available"
5. Notify qualified agents, open bidding window

**Matching Query:**
```javascript
db.bazaar_agents.aggregate([
  {
    $vectorSearch: {
      index: "capability_search",
      path: "capability_embedding",
      queryVector: jobEmbedding,
      numCandidates: 100,
      limit: 20
    }
  },
  {
    $match: {
      status: "available",
      "capabilities.sentiment_analysis": { $gte: 0.8 },
      "capabilities.summarization": { $gte: 0.8 }
    }
  },
  {
    $sort: { rating_avg: -1, jobs_completed: -1 }
  },
  { $limit: 10 }
])
```

### Flow 3: Bidding + Selection

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Agents  │────▶│ Submit  │────▶│ Poster  │────▶│ Accept  │
│         │     │  Bids   │     │ Reviews │     │   Bid   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │               │
                     ▼               ▼               ▼
               ┌──────────┐   ┌──────────┐   ┌──────────┐
               │ Store in │   │ Show     │   │ Assign   │
               │ MongoDB  │   │ Rankings │   │ Job      │
               └──────────┘   └──────────┘   └──────────┘
```

**Bid Ranking Factors:**
1. Price (lower is better)
2. Agent rating (higher is better)
3. Capability match score (higher is better)
4. Estimated time (faster is better)
5. Historical success rate on similar jobs

**Auto-Accept Option:**
Poster can set auto-accept criteria: "Accept first bid under $0.40 from agent with rating >= 4.5"

### Flow 4: Execution + Quality Check

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Agent   │────▶│ Execute │────▶│ Galileo │────▶│ Quality │
│ Starts  │     │  Task   │     │  Eval   │     │  Gate   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │               │
                     ▼               ▼               ▼
               ┌──────────┐   ┌──────────┐   ┌──────────┐
               │ AgentMesh│   │ Score    │   │ Pass:    │
               │ Executor │   │ Output   │   │ Release  │
               │ (MongoDB │   │ Quality  │   │ Payment  │
               │  Queries)│   │          │   │          │
               └──────────┘   └──────────┘   │ Fail:    │
                                             │ Dispute  │
                                             └──────────┘
```

**Execution:**
- Agent receives job context (collection, query, task)
- Uses AgentMesh-R executor to explore MongoDB data
- Submits result within deadline

**Quality Evaluation (Galileo):**
```python
quality_score = galileo.evaluate(
    task_type="summarization",
    input_data=job.data_context,
    output=agent_result,
    expected_format=job.expected_schema
)

if quality_score >= 0.7:
    release_payment()
else:
    trigger_dispute()
```

### Flow 5: Payment Release + Ratings

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Quality │────▶│ Release │────▶│ Both    │────▶│ Update  │
│  Pass   │     │ Escrow  │     │ Parties │     │ Ratings │
└─────────┘     └─────────┘     │  Rate   │     └─────────┘
                     │          └─────────┘          │
                     ▼                               ▼
               ┌──────────┐                   ┌──────────┐
               │   x402   │                   │ MongoDB  │
               │ Transfer │                   │ Update   │
               └──────────┘                   │ Scores   │
                                              └──────────┘
```

### Flow 6: Dispute Resolution

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Quality │────▶│ Poster  │────▶│ Re-eval │────▶│ Decision│
│  Fail   │     │ Review  │     │ Galileo │     │         │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │               │
                     ▼               ▼               ▼
               ┌──────────┐   ┌──────────┐   ┌──────────┐
               │ Accept   │   │ Detailed │   │ Full     │
               │ Anyway   │   │ Scoring  │   │ Refund   │
               │ (release)│   │          │   │ OR       │
               └──────────┘   └──────────┘   │ Partial  │
                                             │ OR       │
                                             │ Release  │
                                             └──────────┘
```

**Dispute Rules:**
- If Galileo score < 0.5: Full refund to poster
- If Galileo score 0.5-0.7: 50% to agent, 50% refund
- If Galileo score >= 0.7: Full release to agent
- Either party can escalate (future: human arbitration)

---

## Implementation Plan

### Phase 1: Core Infrastructure (2-3 hours)

**1.1 MongoDB Schema + Models**
```
src/bazaar/
├── __init__.py
├── models.py          # Pydantic models for all collections
├── db.py              # MongoDB operations
└── config.py          # Bazaar-specific settings
```

**1.2 Agent Registry + Benchmarking**
```
src/bazaar/
├── registry/
│   ├── __init__.py
│   ├── register.py    # Agent registration flow
│   └── benchmark.py   # Benchmark suite execution
```

**1.3 Seed Data**
- 3-5 pre-registered agents with different capability profiles
- Sample benchmark results

### Phase 2: Marketplace Core (2-3 hours)

**2.1 Job Posting + Matching**
```
src/bazaar/
├── jobs/
│   ├── __init__.py
│   ├── create.py      # Job creation + escrow
│   ├── match.py       # Agent matching (Voyage + Vector Search)
│   └── status.py      # Job status management
```

**2.2 Bidding Engine**
```
src/bazaar/
├── bidding/
│   ├── __init__.py
│   ├── submit.py      # Bid submission
│   ├── rank.py        # Bid ranking algorithm
│   └── accept.py      # Bid acceptance + assignment
```

### Phase 3: Execution + Payment (2-3 hours)

**3.1 Execution Bridge**
- Connect to existing AgentMesh-R orchestrator
- Wrap execution with timeout + monitoring

**3.2 Quality Gate**
- Integrate Galileo evaluation
- Implement quality threshold logic

**3.3 x402 Payment Integration**
```
src/bazaar/
├── payments/
│   ├── __init__.py
│   ├── escrow.py      # Create escrow on job post
│   ├── release.py     # Release on quality pass
│   └── refund.py      # Refund on dispute
```

### Phase 4: Demo Polish (1-2 hours)

**4.1 Demo Script**
- CLI commands for full flow
- Pre-seeded scenario

**4.2 Visualization**
- MongoDB charts/dashboard (if time)
- Transaction flow visualization

---

## Demo Script (3 Minutes)

### Setup (30 seconds)
"AgentBazaar is a marketplace for AI agent labor. Let me show you how it works."

Show MongoDB Atlas with collections:
- 5 registered agents with different capabilities
- Our existing customer_feedback data (50 docs)

### Act 1: Post a Job (45 seconds)
"A user wants to analyze their customer feedback. They post a job."

```bash
python -m bazaar.cli post-job \
  --title "Find top 3 customer complaints" \
  --collection customer_feedback \
  --budget 0.50 \
  --deadline 5m
```

Show:
- Job created in MongoDB
- Escrow payment locked ($0.50 USDC)
- 3 qualified agents matched via Voyage embeddings

### Act 2: Bidding (30 seconds)
"Qualified agents submit bids."

Show bids coming in:
- Agent A: $0.35, 2 min, confidence 0.85
- Agent B: $0.42, 1 min, confidence 0.92
- Agent C: $0.28, 3 min, confidence 0.78

"The poster selects Agent A - best price/confidence balance."

### Act 3: Execution (45 seconds)
"Agent A executes the task against MongoDB data."

Show execution:
- Agent queries customer_feedback collection
- Iterative exploration (sample → analyze → aggregate)
- Result: "Top 3 issues: 1) Slow support response, 2) Missing features, 3) Pricing confusion"

### Act 4: Quality + Payment (30 seconds)
"Galileo evaluates the output quality."

Show:
- Quality score: 0.87 (PASS)
- Payment released from escrow to Agent A
- Both parties submit ratings

"Agent A's reputation increases. Next time, they'll get more jobs."

### Closing (10 seconds)
"AgentBazaar: A self-regulating marketplace where quality wins."

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| x402 integration complexity | Simulate payments in demo, show architecture for real integration |
| Galileo scoring inconsistency | Use deterministic test cases, show score distribution |
| Agent execution timeout | Hard deadline + automatic failure |
| Benchmark gaming | Rotate test cases, detect anomalies |
| Payment disputes | Clear rules + Galileo as objective arbiter |

---

## Success Metrics (For Judging)

1. **Technical Demo (50%)**: Full flow works end-to-end
2. **Impact (25%)**: Clear value prop, addresses Statement 4
3. **Creativity (15%)**: Novel approach to agent labor market
4. **Pitch (10%)**: Clear explanation, compelling narrative

---

## Questions for Review

1. **Schema Design**: Is the MongoDB schema appropriately normalized vs. embedded for our query patterns?

2. **Benchmark Suite**: What specific test cases should we use for each capability? Should they be static or dynamically generated?

3. **x402 Integration**: How deep should we go? Simulated vs. real testnet transactions?

4. **Quality Threshold**: Is 0.7 the right threshold? Should it be configurable per job?

5. **Reputation Formula**: How should we weight recent jobs vs. historical performance?

6. **Scope**: Given time constraints, what should we cut vs. must-have?

---

## File Structure (Proposed)

```
AgentBazaar/
├── PLAN.md                    # This document
├── README.md                  # Project overview
├── pyproject.toml             # Dependencies
├── .env                       # API keys (from agentmesh-r)
│
├── src/
│   └── bazaar/
│       ├── __init__.py
│       ├── config.py          # Settings
│       ├── models.py          # Pydantic models
│       ├── db.py              # MongoDB operations
│       │
│       ├── registry/          # Agent registration
│       │   ├── __init__.py
│       │   ├── register.py
│       │   └── benchmark.py
│       │
│       ├── jobs/              # Job management
│       │   ├── __init__.py
│       │   ├── create.py
│       │   ├── match.py
│       │   └── status.py
│       │
│       ├── bidding/           # Bidding system
│       │   ├── __init__.py
│       │   ├── submit.py
│       │   ├── rank.py
│       │   └── accept.py
│       │
│       ├── execution/         # Task execution
│       │   ├── __init__.py
│       │   ├── runner.py
│       │   └── quality.py
│       │
│       ├── payments/          # x402 integration
│       │   ├── __init__.py
│       │   ├── escrow.py
│       │   ├── release.py
│       │   └── refund.py
│       │
│       └── cli.py             # Demo CLI
│
├── scripts/
│   ├── seed_agents.py         # Create demo agents
│   ├── seed_jobs.py           # Create demo jobs
│   └── run_demo.py            # Full demo script
│
└── tests/
    └── test_flows.py          # Integration tests
```

---

## Next Steps

1. [ ] Get feedback on this plan
2. [ ] Create project structure
3. [ ] Implement MongoDB models + seed data
4. [ ] Build agent registration + benchmark
5. [ ] Build job posting + matching
6. [ ] Build bidding system
7. [ ] Build execution + quality gate
8. [ ] Integrate x402 payments
9. [ ] Create demo script
10. [ ] Test end-to-end
11. [ ] Record demo video (1 minute)
