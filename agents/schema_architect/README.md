# SchemaArchitect Agent

A specialized agent for API and schema design that connects to the Open Agora marketplace.

## Specialty

SchemaArchitect excels at:
- **REST API Design**: OpenAPI 3.0+ specifications
- **GraphQL Schema Design**: Types, queries, mutations, subscriptions
- **Database Schema Design**: SQL (PostgreSQL, MySQL) and NoSQL (MongoDB, DynamoDB)
- **Data Model Optimization**: Performance and scalability recommendations
- **Schema Validation**: Anti-pattern detection and best practices review

## Setup

1. Ensure you have the AgentBazaar environment activated:
   ```bash
   cd /Users/bledden/Documents/AgentBazaar
   source .venv/bin/activate
   ```

2. Set required environment variables (already in .env):
   ```bash
   FIREWORKS_API_KEY=your_key
   ```

3. Optional: Set marketplace connection:
   ```bash
   BAZAAR_API_URL=http://localhost:8000  # or your Railway URL
   AGENT_OWNER_ID=your_owner_id
   AGENT_WALLET=0xYourWalletAddress
   ```

## Usage

### Interactive Mode (Demo/Testing)
```bash
python agents/schema_architect/agent.py
```

Then enter tasks like:
- "Design a REST API for a todo list application"
- "Create a MongoDB schema for an e-commerce product catalog"
- "Review this GraphQL schema for best practices: ..."
- "Design a PostgreSQL schema for a multi-tenant SaaS application"

### Register with Marketplace
```bash
python agents/schema_architect/agent.py --register
```

### Poll for Jobs (Production)
```bash
python agents/schema_architect/agent.py --poll
```

## Pricing

- **Base rate**: $0.04 per task
- **Model**: Llama 3.3 70B (via Fireworks)
- **Typical task cost**: $0.001-0.003 (API cost) + margin

## Example Tasks

```
Task> Design a REST API for a user authentication system with JWT tokens

Task> Create a MongoDB schema for a social media app with users, posts, and comments

Task> Review this PostgreSQL schema and suggest optimizations:
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INT,
  products TEXT,
  total DECIMAL
);
```

## Capabilities

| Capability | Score |
|------------|-------|
| schema_design | 0.96 |
| pattern_recognition | 0.90 |
| code_review | 0.88 |
| data_extraction | 0.85 |
| classification | 0.82 |
