"""JSON Schema definitions for Thesys C1 custom components.

These schemas tell the C1 model about available custom components
and their expected props structure.
"""

from typing import Dict, Any


def get_component_schemas() -> Dict[str, Any]:
    """Return JSON Schema definitions for all custom components."""
    return {
        "AgentCard": {
            "type": "object",
            "description": "Displays an AI agent with capabilities, rating, and hire button",
            "properties": {
                "agent_id": {"type": "string", "description": "Unique agent identifier"},
                "name": {"type": "string", "description": "Agent display name"},
                "description": {"type": "string", "description": "Agent description"},
                "capabilities": {
                    "type": "array",
                    "description": "Agent capabilities with scores",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "score": {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "required": ["name", "score"]
                    }
                },
                "rating": {"type": "number", "minimum": 0, "maximum": 5, "description": "Average rating"},
                "jobs_completed": {"type": "integer", "description": "Total jobs completed"},
                "base_rate": {"type": "number", "description": "Base rate per task in USD"},
                "status": {
                    "type": "string",
                    "enum": ["available", "busy", "offline"],
                    "description": "Current agent status"
                },
                "total_earned": {"type": "number", "description": "Total USD earned"}
            },
            "required": ["agent_id", "name", "status"]
        },

        "JobCard": {
            "type": "object",
            "description": "Displays a job listing with budget, status, and action buttons",
            "properties": {
                "job_id": {"type": "string", "description": "Unique job identifier"},
                "title": {"type": "string", "description": "Job title"},
                "description": {"type": "string", "description": "Job description"},
                "budget": {"type": "number", "description": "Budget in USD"},
                "status": {
                    "type": "string",
                    "enum": ["posted", "bidding", "negotiating", "awaiting_approval", "assigned", "in_progress", "completed", "disputed", "cancelled"],
                    "description": "Current job status"
                },
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required capabilities"
                },
                "quality_score": {"type": "number", "minimum": 0, "maximum": 1, "description": "Quality score if completed"},
                "assigned_agent": {"type": "string", "description": "Assigned agent name"},
                "assigned_agent_id": {"type": "string", "description": "Assigned agent ID"}
            },
            "required": ["job_id", "title", "status", "budget"]
        },

        "BidCard": {
            "type": "object",
            "description": "Displays a bid from an agent with negotiation status and actions",
            "properties": {
                "bid_id": {"type": "string", "description": "Unique bid identifier"},
                "job_id": {"type": "string", "description": "Associated job ID"},
                "agent_id": {"type": "string", "description": "Bidding agent ID"},
                "agent_name": {"type": "string", "description": "Bidding agent name"},
                "price_usd": {"type": "number", "description": "Bid price in USD"},
                "estimated_time_seconds": {"type": "integer", "description": "Estimated completion time"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "Agent confidence score"},
                "approach": {"type": "string", "description": "Agent's approach summary"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "counter_offered", "counter_accepted", "awaiting_approval", "accepted", "rejected", "withdrawn"],
                    "description": "Current bid status"
                },
                "counter_offers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "price_usd": {"type": "number"},
                            "message": {"type": "string"},
                            "by": {"type": "string", "enum": ["poster", "agent"]}
                        }
                    },
                    "description": "Negotiation history"
                },
                "requires_approval": {"type": "boolean", "description": "Whether human approval is required"},
                "final_price_usd": {"type": "number", "description": "Final negotiated price"}
            },
            "required": ["bid_id", "job_id", "agent_id", "agent_name", "price_usd", "status"]
        },

        "NegotiationPanel": {
            "type": "object",
            "description": "Full negotiation interface with counter-offer form and history",
            "properties": {
                "bid": {"$ref": "#/definitions/BidCard", "description": "The bid being negotiated"},
                "job_title": {"type": "string", "description": "Title of the job"},
                "original_budget": {"type": "number", "description": "Original job budget"},
                "negotiation_history": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "price_usd": {"type": "number"},
                            "message": {"type": "string"},
                            "by": {"type": "string", "enum": ["poster", "agent"]},
                            "created_at": {"type": "string"}
                        }
                    },
                    "description": "Full negotiation history"
                },
                "can_counter": {"type": "boolean", "description": "Whether user can make counter-offer"},
                "can_approve": {"type": "boolean", "description": "Whether user can approve the bid"},
                "can_accept": {"type": "boolean", "description": "Whether user can accept current offer"}
            },
            "required": ["bid", "job_title", "original_budget", "negotiation_history", "can_counter", "can_approve", "can_accept"]
        },

        "ApprovalQueue": {
            "type": "object",
            "description": "Dashboard showing pending human-in-the-loop approvals",
            "properties": {
                "pending_approvals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bid_id": {"type": "string"},
                            "job_id": {"type": "string"},
                            "job_title": {"type": "string"},
                            "agent_id": {"type": "string"},
                            "agent_name": {"type": "string"},
                            "price_usd": {"type": "number"},
                            "approval_reason": {"type": "string"}
                        },
                        "required": ["bid_id", "job_id", "job_title", "agent_name", "price_usd", "approval_reason"]
                    },
                    "description": "List of pending approvals"
                }
            },
            "required": ["pending_approvals"]
        },

        "TransactionDetails": {
            "type": "object",
            "description": "Displays x402 payment transaction details with flow visualization",
            "properties": {
                "txn_id": {"type": "string", "description": "Transaction identifier"},
                "txn_type": {
                    "type": "string",
                    "enum": ["escrow", "release", "refund"],
                    "description": "Type of transaction"
                },
                "job_id": {"type": "string", "description": "Associated job ID"},
                "amount_usd": {"type": "number", "description": "Amount in USD"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "escrowed", "released", "refunded", "failed"],
                    "description": "Transaction status"
                },
                "payer_wallet": {"type": "string", "description": "Payer wallet address"},
                "payee_wallet": {"type": "string", "description": "Payee wallet address"},
                "x402_payment_id": {"type": "string", "description": "x402 payment hash"},
                "created_at": {"type": "string", "description": "ISO timestamp"}
            },
            "required": ["txn_id", "txn_type", "job_id", "amount_usd", "status", "payer_wallet"]
        },

        "PostJobForm": {
            "type": "object",
            "description": "Form for creating a new job posting",
            "properties": {
                "initial_title": {"type": "string", "description": "Pre-filled title"},
                "initial_description": {"type": "string", "description": "Pre-filled description"},
                "suggested_capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggested capabilities"
                },
                "suggested_budget": {"type": "number", "description": "Suggested budget"},
                "preselected_agent_id": {"type": "string", "description": "Pre-selected agent ID if hiring specific agent"},
                "preselected_agent_name": {"type": "string", "description": "Pre-selected agent name"}
            }
        },

        "CounterOfferForm": {
            "type": "object",
            "description": "Compact form for making a counter-offer on a bid",
            "properties": {
                "bid_id": {"type": "string", "description": "Bid to counter"},
                "current_price": {"type": "number", "description": "Current offer price"},
                "min_price": {"type": "number", "description": "Minimum acceptable price hint"},
                "max_price": {"type": "number", "description": "Maximum price hint"},
                "job_title": {"type": "string", "description": "Job title for context"}
            },
            "required": ["bid_id", "current_price"]
        },

        "PageLayout": {
            "type": "object",
            "description": "Wrapper component for full-page layouts",
            "properties": {
                "page_type": {
                    "type": "string",
                    "enum": ["home", "agents_list", "jobs_list", "agent_detail", "job_detail", "post_job", "negotiations", "approvals", "transaction_history"],
                    "description": "Type of page being displayed"
                },
                "title": {"type": "string", "description": "Page title"},
                "subtitle": {"type": "string", "description": "Page subtitle"},
                "show_stats": {"type": "boolean", "default": True, "description": "Whether to show marketplace stats"},
                "show_navigation": {"type": "boolean", "default": True, "description": "Whether to show navigation header"}
            },
            "required": ["page_type", "title"]
        },

        "NavigationHeader": {
            "type": "object",
            "description": "Navigation bar with marketplace branding and action buttons",
            "properties": {
                "current_page": {
                    "type": "string",
                    "enum": ["home", "agents_list", "jobs_list", "agent_detail", "job_detail", "post_job", "negotiations", "approvals", "transaction_history"],
                    "description": "Currently active page"
                },
                "show_post_job_button": {"type": "boolean", "default": True, "description": "Show post job CTA"},
                "pending_approvals_count": {"type": "integer", "default": 0, "description": "Badge count for approvals"}
            },
            "required": ["current_page"]
        },

        "MarketplaceStats": {
            "type": "object",
            "description": "Dashboard statistics grid showing marketplace metrics",
            "properties": {
                "total_agents": {"type": "integer", "description": "Total registered agents"},
                "total_jobs": {"type": "integer", "description": "Total jobs"},
                "total_volume": {"type": "number", "description": "Total USD volume"},
                "active_jobs": {"type": "integer", "description": "Currently active jobs"},
                "available_agents": {"type": "integer", "description": "Available agents"}
            },
            "required": ["total_agents", "total_jobs", "total_volume", "active_jobs"]
        }
    }
