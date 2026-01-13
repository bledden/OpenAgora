"""MongoDB database operations for AgentBazaar."""

from typing import Optional, Any
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import structlog

from .config import get_settings

logger = structlog.get_logger()

# Global client
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                serialize_doc(v) if isinstance(v, dict)
                else str(v) if isinstance(v, ObjectId)
                else v.isoformat() if isinstance(v, datetime)
                else v
                for v in value
            ]
        else:
            result[key] = value
    return result


async def get_db() -> AsyncIOMotorDatabase:
    """Get database connection."""
    global _client, _db

    if _db is None:
        settings = get_settings()

        # MongoDB Atlas connection - TLS is enabled by default for mongodb+srv://
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        _db = _client[settings.mongodb_database]
        logger.info("mongodb_connected", database=settings.mongodb_database)

    return _db


async def get_collection(name: str) -> AsyncIOMotorCollection:
    """Get a collection by name."""
    db = await get_db()
    return db[name]


async def close_db():
    """Close database connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("mongodb_disconnected")


# ============================================================
# Collection Names
# ============================================================

AGENTS_COLLECTION = "bazaar_agents"
JOBS_COLLECTION = "bazaar_jobs"
BIDS_COLLECTION = "bazaar_bids"
TRANSACTIONS_COLLECTION = "bazaar_transactions"
RATINGS_COLLECTION = "bazaar_ratings"
BENCHMARKS_COLLECTION = "bazaar_benchmarks"


# ============================================================
# Agent Operations
# ============================================================

async def create_agent(agent_data: dict) -> str:
    """Create a new agent. Returns agent_id."""
    collection = await get_collection(AGENTS_COLLECTION)
    result = await collection.insert_one(agent_data)
    logger.info("agent_created", agent_id=agent_data["agent_id"])
    return agent_data["agent_id"]


async def get_agent(agent_id: str) -> Optional[dict]:
    """Get agent by ID."""
    collection = await get_collection(AGENTS_COLLECTION)
    doc = await collection.find_one({"agent_id": agent_id})
    return serialize_doc(doc) if doc else None


async def get_agent_by_wallet(wallet_address: str) -> Optional[dict]:
    """Get agent by wallet address (case-insensitive)."""
    collection = await get_collection(AGENTS_COLLECTION)
    doc = await collection.find_one({
        "wallet_address": {"$regex": f"^{wallet_address}$", "$options": "i"}
    })
    return serialize_doc(doc) if doc else None


async def update_agent(agent_id: str, updates: dict) -> bool:
    """Update agent fields."""
    collection = await get_collection(AGENTS_COLLECTION)
    result = await collection.update_one(
        {"agent_id": agent_id},
        {"$set": updates}
    )
    return result.modified_count > 0


async def delete_agent(agent_id: str) -> bool:
    """Delete an agent by ID."""
    collection = await get_collection(AGENTS_COLLECTION)
    result = await collection.delete_one({"agent_id": agent_id})
    if result.deleted_count > 0:
        logger.info("agent_deleted", agent_id=agent_id)
        return True
    return False


async def find_available_agents(
    required_capabilities: list[str],
    min_score: float = 0.7,
    limit: int = 10
) -> list[dict]:
    """Find available agents matching capability requirements."""
    collection = await get_collection(AGENTS_COLLECTION)

    # Build capability filter
    capability_filter = {"status": "available"}
    for cap in required_capabilities:
        capability_filter[f"capabilities.{cap}"] = {"$gte": min_score}

    cursor = collection.find(capability_filter).sort([
        ("rating_avg", -1),
        ("jobs_completed", -1)
    ]).limit(limit)

    agents = []
    async for doc in cursor:
        agents.append(serialize_doc(doc))

    return agents


async def vector_search_agents(
    job_embedding: list[float],
    required_capabilities: list[str],
    min_score: float = 0.7,
    limit: int = 10
) -> list[dict]:
    """Find agents using vector similarity search."""
    collection = await get_collection(AGENTS_COLLECTION)

    # Build capability filter for post-filtering
    capability_filter = {"status": "available"}
    for cap in required_capabilities:
        capability_filter[f"capabilities.{cap}"] = {"$gte": min_score}

    pipeline = [
        {
            "$vectorSearch": {
                "index": "capability_search",
                "path": "capability_embedding",
                "queryVector": job_embedding,
                "numCandidates": 100,
                "limit": 50
            }
        },
        {"$match": capability_filter},
        {
            "$addFields": {
                "search_score": {"$meta": "vectorSearchScore"}
            }
        },
        {"$sort": {"search_score": -1, "rating_avg": -1}},
        {"$limit": limit}
    ]

    try:
        agents = []
        async for doc in collection.aggregate(pipeline):
            agents.append(serialize_doc(doc))
        return agents
    except Exception as e:
        # Fallback to regular search if vector search not available
        logger.warning("vector_search_fallback", error=str(e))
        return await find_available_agents(required_capabilities, min_score, limit)


# ============================================================
# Job Operations
# ============================================================

async def create_job(job_data: dict) -> str:
    """Create a new job. Returns job_id."""
    collection = await get_collection(JOBS_COLLECTION)
    await collection.insert_one(job_data)
    logger.info("job_created", job_id=job_data["job_id"])
    return job_data["job_id"]


async def get_job(job_id: str) -> Optional[dict]:
    """Get job by ID."""
    collection = await get_collection(JOBS_COLLECTION)
    doc = await collection.find_one({"job_id": job_id})
    return serialize_doc(doc) if doc else None


async def update_job(job_id: str, updates: dict) -> bool:
    """Update job fields."""
    collection = await get_collection(JOBS_COLLECTION)
    result = await collection.update_one(
        {"job_id": job_id},
        {"$set": updates}
    )
    return result.modified_count > 0


async def delete_job(job_id: str) -> bool:
    """Delete a job by ID."""
    collection = await get_collection(JOBS_COLLECTION)
    result = await collection.delete_one({"job_id": job_id})
    if result.deleted_count > 0:
        logger.info("job_deleted", job_id=job_id)
        return True
    return False


async def delete_all_jobs() -> int:
    """Delete all jobs. Returns count of deleted jobs."""
    collection = await get_collection(JOBS_COLLECTION)
    result = await collection.delete_many({})
    logger.info("all_jobs_deleted", count=result.deleted_count)
    return result.deleted_count


async def find_open_jobs(limit: int = 20) -> list[dict]:
    """Find open jobs accepting bids."""
    collection = await get_collection(JOBS_COLLECTION)
    cursor = collection.find(
        {"status": {"$in": ["open", "bidding"]}}
    ).sort("created_at", -1).limit(limit)

    jobs = []
    async for doc in cursor:
        jobs.append(serialize_doc(doc))
    return jobs


# ============================================================
# Bid Operations
# ============================================================

async def create_bid(bid_data: dict) -> str:
    """Create a new bid. Returns bid_id."""
    collection = await get_collection(BIDS_COLLECTION)
    await collection.insert_one(bid_data)

    # Increment job bid count
    jobs_collection = await get_collection(JOBS_COLLECTION)
    await jobs_collection.update_one(
        {"job_id": bid_data["job_id"]},
        {"$inc": {"bid_count": 1}}
    )

    logger.info("bid_created", bid_id=bid_data["bid_id"], job_id=bid_data["job_id"])
    return bid_data["bid_id"]


async def get_bid(bid_id: str) -> Optional[dict]:
    """Get bid by ID."""
    collection = await get_collection(BIDS_COLLECTION)
    doc = await collection.find_one({"bid_id": bid_id})
    return serialize_doc(doc) if doc else None


async def get_bids_for_job(job_id: str) -> list[dict]:
    """Get all bids for a job."""
    collection = await get_collection(BIDS_COLLECTION)
    cursor = collection.find({"job_id": job_id}).sort("created_at", 1)

    bids = []
    async for doc in cursor:
        bids.append(serialize_doc(doc))
    return bids


async def update_bid(bid_id: str, updates: dict) -> bool:
    """Update bid fields."""
    collection = await get_collection(BIDS_COLLECTION)
    result = await collection.update_one(
        {"bid_id": bid_id},
        {"$set": updates}
    )
    return result.modified_count > 0


async def get_pending_bids_by_agent(agent_id: str) -> list[dict]:
    """Get all pending bids for an agent."""
    collection = await get_collection(BIDS_COLLECTION)
    cursor = collection.find({
        "agent_id": agent_id,
        "status": "pending"
    })
    bids = []
    async for doc in cursor:
        bids.append(serialize_doc(doc))
    return bids


async def cancel_pending_bids_by_agent(agent_id: str) -> int:
    """Cancel all pending bids for an agent. Returns count cancelled."""
    collection = await get_collection(BIDS_COLLECTION)
    result = await collection.update_many(
        {"agent_id": agent_id, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_reason": "agent_offline"}}
    )
    return result.modified_count


async def get_stale_agents(stale_minutes: int = 5) -> list[dict]:
    """Get agents that haven't sent a heartbeat in the specified minutes."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
    collection = await get_collection(AGENTS_COLLECTION)
    cursor = collection.find({
        "status": {"$in": ["available", "busy"]},
        "$or": [
            {"last_active": {"$lt": cutoff}},
            {"last_active": {"$exists": False}}
        ]
    })
    agents = []
    async for doc in cursor:
        agents.append(serialize_doc(doc))
    return agents


# ============================================================
# Transaction Operations
# ============================================================

async def create_transaction(txn_data: dict) -> str:
    """Create a new transaction. Returns txn_id."""
    collection = await get_collection(TRANSACTIONS_COLLECTION)
    await collection.insert_one(txn_data)
    logger.info("transaction_created", txn_id=txn_data["txn_id"], type=txn_data["txn_type"])
    return txn_data["txn_id"]


async def get_transaction(txn_id: str) -> Optional[dict]:
    """Get transaction by ID."""
    collection = await get_collection(TRANSACTIONS_COLLECTION)
    doc = await collection.find_one({"txn_id": txn_id})
    return serialize_doc(doc) if doc else None


async def update_transaction(txn_id: str, updates: dict) -> bool:
    """Update transaction fields."""
    collection = await get_collection(TRANSACTIONS_COLLECTION)
    result = await collection.update_one(
        {"txn_id": txn_id},
        {"$set": updates}
    )
    return result.modified_count > 0


# ============================================================
# Rating Operations
# ============================================================

async def create_rating(rating_data: dict) -> str:
    """Create a new rating. Returns rating_id."""
    collection = await get_collection(RATINGS_COLLECTION)
    await collection.insert_one(rating_data)
    logger.info("rating_created", rating_id=rating_data["rating_id"])
    return rating_data["rating_id"]


async def get_rating_for_job(job_id: str) -> Optional[dict]:
    """Get rating for a job."""
    collection = await get_collection(RATINGS_COLLECTION)
    doc = await collection.find_one({"job_id": job_id})
    return serialize_doc(doc) if doc else None


# ============================================================
# Benchmark Operations
# ============================================================

async def create_benchmark(benchmark_data: dict) -> str:
    """Create a new benchmark. Returns benchmark_id."""
    collection = await get_collection(BENCHMARKS_COLLECTION)
    await collection.insert_one(benchmark_data)
    logger.info("benchmark_created", benchmark_id=benchmark_data["benchmark_id"])
    return benchmark_data["benchmark_id"]


async def get_latest_benchmark(agent_id: str) -> Optional[dict]:
    """Get latest benchmark for an agent."""
    collection = await get_collection(BENCHMARKS_COLLECTION)
    doc = await collection.find_one(
        {"agent_id": agent_id},
        sort=[("created_at", -1)]
    )
    return serialize_doc(doc) if doc else None


# ============================================================
# Index Setup
# ============================================================

async def init_db():
    """Initialize database connection and create indexes."""
    try:
        await setup_indexes()
        logger.info("database_initialized")
    except Exception as e:
        # Index creation can fail with Python 3.14 SSL issues on MongoDB Atlas
        # The indexes likely already exist, so log and continue
        logger.warning("index_setup_failed", error=str(e), note="continuing without index creation")


async def get_all_agents(limit: int = 100) -> list[dict]:
    """Get all registered agents."""
    collection = await get_collection(AGENTS_COLLECTION)
    cursor = collection.find({}).sort([
        ("rating_avg", -1),
        ("jobs_completed", -1)
    ]).limit(limit)

    agents = []
    async for doc in cursor:
        agents.append(serialize_doc(doc))
    return agents


async def get_all_jobs(limit: int = 100) -> list[dict]:
    """Get all jobs."""
    collection = await get_collection(JOBS_COLLECTION)
    cursor = collection.find({}).sort("created_at", -1).limit(limit)

    jobs = []
    async for doc in cursor:
        jobs.append(serialize_doc(doc))
    return jobs


async def setup_indexes():
    """Create indexes for all collections."""
    db = await get_db()

    # Agents indexes
    agents = db[AGENTS_COLLECTION]
    await agents.create_index([("agent_id", 1)], unique=True)
    await agents.create_index([("status", 1), ("rating_avg", -1)])
    await agents.create_index([("owner_id", 1)])

    # Jobs indexes
    jobs = db[JOBS_COLLECTION]
    await jobs.create_index([("job_id", 1)], unique=True)
    await jobs.create_index([("status", 1), ("created_at", -1)])
    await jobs.create_index([("poster_id", 1)])
    await jobs.create_index([("assigned_agent_id", 1)])

    # Bids indexes
    bids = db[BIDS_COLLECTION]
    await bids.create_index([("bid_id", 1)], unique=True)
    await bids.create_index([("job_id", 1), ("status", 1)])
    await bids.create_index([("agent_id", 1)])

    # Transactions indexes
    txns = db[TRANSACTIONS_COLLECTION]
    await txns.create_index([("txn_id", 1)], unique=True)
    await txns.create_index([("job_id", 1)])
    await txns.create_index([("payer_id", 1)])

    # Ratings indexes
    ratings = db[RATINGS_COLLECTION]
    await ratings.create_index([("rating_id", 1)], unique=True)
    await ratings.create_index([("job_id", 1)])

    # Benchmarks indexes
    benchmarks = db[BENCHMARKS_COLLECTION]
    await benchmarks.create_index([("benchmark_id", 1)], unique=True)
    await benchmarks.create_index([("agent_id", 1), ("created_at", -1)])

    logger.info("indexes_created")
