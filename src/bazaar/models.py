"""Pydantic models for all AgentBazaar collections."""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    SUSPENDED = "suspended"


class JobStatus(str, Enum):
    OPEN = "open"
    POSTED = "posted"  # Posted with escrow
    BIDDING = "bidding"
    NEGOTIATING = "negotiating"  # Counter-bid in progress
    AWAITING_APPROVAL = "awaiting_approval"  # Human approval needed
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class BidStatus(str, Enum):
    PENDING = "pending"
    COUNTER_OFFERED = "counter_offered"  # Poster made counter-offer
    COUNTER_ACCEPTED = "counter_accepted"  # Agent accepted counter
    AWAITING_APPROVAL = "awaiting_approval"  # Needs human approval
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class TransactionType(str, Enum):
    ESCROW = "escrow"
    RELEASE = "release"
    REFUND = "refund"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    ESCROWED = "escrowed"
    RELEASED = "released"
    REFUNDED = "refunded"
    FAILED = "failed"


class PosterType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"


class Provider(str, Enum):
    FIREWORKS = "fireworks"
    NVIDIA = "nvidia"
    OPENAI = "openai"


# ============================================================
# Agent Models
# ============================================================

class AgentCapabilities(BaseModel):
    """Verified capability scores from benchmarking."""
    summarization: float = 0.0
    sentiment_analysis: float = 0.0
    data_extraction: float = 0.0
    pattern_recognition: float = 0.0
    code_review: float = 0.0
    aggregation: float = 0.0
    classification: float = 0.0
    anomaly_detection: float = 0.0


class BazaarAgent(BaseModel):
    """Registered AI agent with verified capabilities."""
    agent_id: str
    name: str
    description: str
    owner_id: str

    # LLM Configuration
    provider: Provider = Provider.FIREWORKS
    model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct"

    # Verified capabilities (from benchmark)
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    capability_embedding: list[float] = Field(default_factory=list)

    # Pricing
    base_rate_usd: float = 0.01
    rate_per_1k_tokens: float = 0.001

    # Reputation
    rating_avg: float = 0.0
    rating_count: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    total_earned_usd: float = 0.0
    dispute_rate: float = 0.0

    # Status
    status: AgentStatus = AgentStatus.AVAILABLE
    wallet_address: str = ""

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    last_benchmark: Optional[datetime] = None


# ============================================================
# Job Models
# ============================================================

class DataContext(BaseModel):
    """MongoDB data context for a job."""
    collection: str
    query: dict = Field(default_factory=dict)
    estimated_docs: Optional[int] = None
    sample_schema: Optional[dict] = None


class BazaarJob(BaseModel):
    """Posted task awaiting completion."""
    job_id: str
    poster_id: str
    poster_type: PosterType = PosterType.HUMAN

    # Task definition
    title: str
    description: str
    task_type: str = "analysis"

    # Required capabilities
    required_capabilities: list[str] = Field(default_factory=list)
    min_capability_score: float = 0.7
    job_embedding: list[float] = Field(default_factory=list)

    # Data context
    data_context: Optional[DataContext] = None

    # Budget & timeline
    budget_usd: float
    deadline_minutes: int = 10
    escrow_txn_id: Optional[str] = None

    # Status tracking
    status: JobStatus = JobStatus.OPEN
    bid_count: int = 0
    bid_deadline: Optional[datetime] = None
    winning_bid_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None

    # Results
    result: Optional[dict] = None
    quality_score: Optional[float] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================
# Bid Models
# ============================================================

class CounterOffer(BaseModel):
    """Counter-offer in a negotiation."""
    price_usd: float
    message: str
    by: str  # "poster" or "agent"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BazaarBid(BaseModel):
    """Agent bid on a job."""
    bid_id: str
    job_id: str
    agent_id: str

    # Bid details
    price_usd: float
    estimated_time_seconds: int
    confidence: float
    approach: str

    # Negotiation history
    counter_offers: list[CounterOffer] = Field(default_factory=list)
    final_price_usd: Optional[float] = None  # After negotiation

    # Human-in-the-loop
    requires_approval: bool = False
    approval_reason: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # Status
    status: BidStatus = BidStatus.PENDING

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None


# ============================================================
# Transaction Models
# ============================================================

class BazaarTransaction(BaseModel):
    """x402 payment record."""
    txn_id: str
    txn_type: TransactionType

    # References
    job_id: str
    bid_id: Optional[str] = None

    # Parties
    payer_id: str
    payer_wallet: str
    payee_id: Optional[str] = None
    payee_wallet: Optional[str] = None

    # Amount
    amount_usd: float
    amount_usdc: float

    # x402 details (simulated for demo)
    x402_payment_id: Optional[str] = None
    x402_escrow_id: Optional[str] = None

    # Status
    status: TransactionStatus = TransactionStatus.PENDING

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    released_at: Optional[datetime] = None


# ============================================================
# Rating Models
# ============================================================

class AgentRating(BaseModel):
    """Poster's rating of agent."""
    rater_id: str
    agent_id: str
    score: int  # 1-5 stars
    quality_score: float  # Galileo automated score
    speed_rating: str  # slow | average | fast
    accuracy_rating: str  # poor | fair | good | excellent
    comment: str = ""
    would_hire_again: bool = True


class PosterRating(BaseModel):
    """Agent's rating of poster."""
    rater_id: str
    poster_id: str
    score: int  # 1-5 stars
    task_clarity: str  # poor | fair | good | excellent
    payment_fairness: str  # unfair | fair | generous
    comment: str = ""


class BazaarRating(BaseModel):
    """Two-way rating for a completed job."""
    rating_id: str
    job_id: str

    agent_rating: Optional[AgentRating] = None
    poster_rating: Optional[PosterRating] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Benchmark Models
# ============================================================

class BenchmarkTestResult(BaseModel):
    """Result for a single capability test."""
    score: float
    test_cases: int
    passed: int
    avg_latency_ms: float
    sample_output: Optional[str] = None


class BazaarBenchmark(BaseModel):
    """Benchmark results for capability verification."""
    benchmark_id: str
    agent_id: str

    # Test results by capability
    tests: dict[str, BenchmarkTestResult] = Field(default_factory=dict)

    # Aggregate
    overall_score: float = 0.0
    total_tests: int = 0
    total_passed: int = 0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
