import { z } from "zod";

// ============================================================
// Agent Components
// ============================================================

export const CapabilitySchema = z.object({
  name: z.string().describe("Capability name like 'summarization', 'code_review'"),
  score: z.number().min(0).max(1).describe("Capability score from 0 to 1"),
});

export const AgentCardSchema = z.object({
  agent_id: z.string().describe("Unique agent identifier"),
  name: z.string().describe("Agent display name"),
  description: z.string().describe("Agent description"),
  capabilities: z.array(CapabilitySchema).describe("Agent capabilities with scores"),
  rating: z.number().min(0).max(5).describe("Average rating out of 5"),
  jobs_completed: z.number().describe("Total jobs completed"),
  base_rate: z.number().describe("Base rate per task in USD"),
  status: z.enum(["available", "busy", "offline"]).describe("Current agent status"),
  total_earned: z.number().optional().describe("Total USD earned"),
});

// ============================================================
// Job Components
// ============================================================

export const JobStatusSchema = z.enum([
  "open",  // Initial state
  "posted",  // Posted with escrow
  "bidding",
  "negotiating",
  "awaiting_approval",
  "assigned",
  "in_progress",
  "pending_review",  // Work done, awaiting human quality review
  "completed",
  "disputed",
  "cancelled",
]);

export const JobCardSchema = z.object({
  job_id: z.string().describe("Unique job identifier"),
  title: z.string().describe("Job title"),
  description: z.string().describe("Job description"),
  budget: z.number().describe("Budget in USD"),
  status: JobStatusSchema.describe("Current job status"),
  capabilities: z.array(z.string()).describe("Required capabilities"),
  quality_score: z.number().min(0).max(1).optional().describe("Quality score if completed"),
  assigned_agent: z.string().optional().describe("Assigned agent name if any"),
  assigned_agent_id: z.string().optional().describe("Assigned agent ID"),
  poster_id: z.string().optional().describe("Job poster ID"),
  created_at: z.string().optional().describe("ISO timestamp of creation"),
});

// ============================================================
// Bid Components
// ============================================================

export const BidStatusSchema = z.enum([
  "pending",
  "counter_offered",
  "counter_accepted",
  "awaiting_approval",
  "accepted",
  "rejected",
  "withdrawn",
]);

export const CounterOfferSchema = z.object({
  price_usd: z.number().describe("Counter-offer price in USD"),
  message: z.string().describe("Counter-offer message"),
  by: z.enum(["poster", "agent"]).describe("Who made the counter-offer"),
  created_at: z.string().optional().describe("ISO timestamp"),
});

export const BidCardSchema = z.object({
  bid_id: z.string().describe("Unique bid identifier"),
  job_id: z.string().describe("Associated job ID"),
  agent_id: z.string().describe("Bidding agent ID"),
  agent_name: z.string().describe("Bidding agent name"),
  price_usd: z.number().describe("Bid price in USD"),
  estimated_time_seconds: z.number().optional().describe("Estimated completion time"),
  confidence: z.number().min(0).max(1).optional().describe("Agent's confidence score"),
  approach: z.string().optional().describe("Agent's approach summary"),
  status: BidStatusSchema.describe("Current bid status"),
  counter_offers: z.array(CounterOfferSchema).optional().describe("Negotiation history"),
  requires_approval: z.boolean().optional().describe("Whether human approval is required"),
  final_price_usd: z.number().optional().describe("Final negotiated price"),
});

// ============================================================
// Negotiation Components
// ============================================================

export const NegotiationPanelSchema = z.object({
  bid: BidCardSchema.describe("The bid being negotiated"),
  job_title: z.string().describe("Title of the job"),
  original_budget: z.number().describe("Original job budget"),
  negotiation_history: z.array(CounterOfferSchema).describe("Full negotiation history"),
  can_counter: z.boolean().describe("Whether user can make counter-offer"),
  can_approve: z.boolean().describe("Whether user can approve the bid"),
  can_accept: z.boolean().describe("Whether user can accept current offer"),
});

// ============================================================
// Approval Components
// ============================================================

export const PendingApprovalSchema = z.object({
  bid_id: z.string().describe("Bid requiring approval"),
  job_id: z.string().describe("Associated job ID"),
  job_title: z.string().describe("Job title"),
  agent_id: z.string().describe("Agent ID"),
  agent_name: z.string().describe("Agent name"),
  price_usd: z.number().describe("Agreed price"),
  approval_reason: z.string().describe("Why approval is needed (e.g., 'Amount exceeds $10')"),
});

export const ApprovalQueueSchema = z.object({
  pending_approvals: z.array(PendingApprovalSchema).describe("List of pending approvals"),
});

// ============================================================
// Human Review Components (Quality Rating)
// ============================================================

export const AIQualitySuggestionSchema = z.object({
  scores: z.object({
    relevance: z.number().min(0).max(1).describe("Relevance score"),
    accuracy: z.number().min(0).max(1).describe("Accuracy score"),
    completeness: z.number().min(0).max(1).describe("Completeness score"),
    clarity: z.number().min(0).max(1).describe("Clarity score"),
    actionability: z.number().min(0).max(1).describe("Actionability score"),
  }).describe("Individual quality scores"),
  suggested_overall: z.number().min(0).max(1).describe("AI's suggested overall score"),
  recommendation: z.enum(["accept", "partial", "reject"]).describe("AI's recommendation"),
  feedback: z.string().describe("AI's detailed feedback for the reviewer"),
  strengths: z.array(z.string()).describe("What the agent did well"),
  improvements: z.array(z.string()).describe("What could be improved"),
  red_flags: z.array(z.string()).describe("Concerning issues (empty if none)"),
});

export const PendingReviewSchema = z.object({
  job_id: z.string().describe("Job ID awaiting review"),
  title: z.string().describe("Job title"),
  description: z.string().optional().describe("Job description"),
  agent_id: z.string().describe("Agent who completed the work"),
  agent_name: z.string().describe("Agent name"),
  budget_usd: z.number().describe("Job budget"),
  result: z.any().optional().describe("Agent's work result"),
  ai_quality_suggestion: AIQualitySuggestionSchema.optional().describe("AI's quality suggestion"),
});

export const ReviewQueueSchema = z.object({
  pending_reviews: z.array(PendingReviewSchema).describe("List of jobs awaiting human review"),
});

export const JobReviewPanelSchema = z.object({
  job_id: z.string().describe("Job being reviewed"),
  title: z.string().describe("Job title"),
  description: z.string().describe("Job description"),
  result: z.any().describe("Agent's work result"),
  agent_id: z.string().describe("Agent ID"),
  agent_name: z.string().describe("Agent name"),
  budget_usd: z.number().describe("Job budget"),
  ai_suggestion: AIQualitySuggestionSchema.describe("AI's quality suggestion to help reviewer"),
});

// ============================================================
// Transaction Components
// ============================================================

export const TransactionTypeSchema = z.enum(["escrow", "release", "refund"]);
export const TransactionStatusSchema = z.enum(["pending", "escrowed", "released", "refunded", "failed"]);

export const TransactionDetailsSchema = z.object({
  txn_id: z.string().describe("Transaction identifier"),
  txn_type: TransactionTypeSchema.describe("Type of transaction"),
  job_id: z.string().describe("Associated job ID"),
  amount_usd: z.number().describe("Amount in USD"),
  status: TransactionStatusSchema.describe("Transaction status"),
  payer_wallet: z.string().describe("Payer wallet address"),
  payee_wallet: z.string().optional().describe("Payee wallet address"),
  x402_payment_id: z.string().optional().describe("x402 payment hash"),
  created_at: z.string().optional().describe("ISO timestamp"),
});

// ============================================================
// Form Components
// ============================================================

export const PostJobFormSchema = z.object({
  initial_title: z.string().optional().describe("Pre-filled title"),
  initial_description: z.string().optional().describe("Pre-filled description"),
  suggested_capabilities: z.array(z.string()).optional().describe("Suggested capabilities"),
  suggested_budget: z.number().optional().describe("Suggested budget"),
  preselected_agent_id: z.string().optional().describe("Pre-selected agent if hiring specific agent"),
  preselected_agent_name: z.string().optional().describe("Pre-selected agent name"),
});

export const CounterOfferFormSchema = z.object({
  bid_id: z.string().describe("Bid to counter"),
  current_price: z.number().describe("Current offer price"),
  min_price: z.number().optional().describe("Minimum acceptable price hint"),
  max_price: z.number().optional().describe("Maximum price hint"),
  job_title: z.string().optional().describe("Job title for context"),
});

// ============================================================
// Layout Components
// ============================================================

export const PageTypeSchema = z.enum([
  "home",
  "agents_list",
  "jobs_list",
  "agent_detail",
  "job_detail",
  "post_job",
  "negotiations",
  "approvals",
  "reviews",  // Human quality review page
  "job_review",  // Single job review page
  "transaction_history",
]);

export const PageLayoutSchema = z.object({
  page_type: PageTypeSchema.describe("Type of page being displayed"),
  title: z.string().describe("Page title"),
  subtitle: z.string().optional().describe("Page subtitle"),
  show_stats: z.boolean().default(true).describe("Whether to show marketplace stats"),
  show_navigation: z.boolean().default(true).describe("Whether to show navigation header"),
});

export const NavigationHeaderSchema = z.object({
  current_page: PageTypeSchema.describe("Currently active page"),
  show_post_job_button: z.boolean().default(true).describe("Show post job CTA"),
  pending_approvals_count: z.number().default(0).describe("Badge count for approvals"),
});

export const MarketplaceStatsSchema = z.object({
  total_agents: z.number().describe("Total registered agents"),
  total_jobs: z.number().describe("Total jobs"),
  total_volume: z.number().describe("Total USD volume"),
  active_jobs: z.number().describe("Currently active jobs"),
  available_agents: z.number().optional().describe("Available agents"),
});

// ============================================================
// Export All Schemas
// ============================================================

export const componentSchemas = {
  AgentCard: AgentCardSchema,
  JobCard: JobCardSchema,
  BidCard: BidCardSchema,
  NegotiationPanel: NegotiationPanelSchema,
  ApprovalQueue: ApprovalQueueSchema,
  ReviewQueue: ReviewQueueSchema,
  JobReviewPanel: JobReviewPanelSchema,
  TransactionDetails: TransactionDetailsSchema,
  PostJobForm: PostJobFormSchema,
  CounterOfferForm: CounterOfferFormSchema,
  PageLayout: PageLayoutSchema,
  NavigationHeader: NavigationHeaderSchema,
  MarketplaceStats: MarketplaceStatsSchema,
};

// Type exports for components
export type AgentCardProps = z.infer<typeof AgentCardSchema>;
export type JobCardProps = z.infer<typeof JobCardSchema>;
export type BidCardProps = z.infer<typeof BidCardSchema>;
export type NegotiationPanelProps = z.infer<typeof NegotiationPanelSchema>;
export type ApprovalQueueProps = z.infer<typeof ApprovalQueueSchema>;
export type ReviewQueueProps = z.infer<typeof ReviewQueueSchema>;
export type JobReviewPanelProps = z.infer<typeof JobReviewPanelSchema>;
export type AIQualitySuggestionProps = z.infer<typeof AIQualitySuggestionSchema>;
export type PendingReviewProps = z.infer<typeof PendingReviewSchema>;
export type TransactionDetailsProps = z.infer<typeof TransactionDetailsSchema>;
export type PostJobFormProps = z.infer<typeof PostJobFormSchema>;
export type CounterOfferFormProps = z.infer<typeof CounterOfferFormSchema>;
export type PageLayoutProps = z.infer<typeof PageLayoutSchema>;
export type NavigationHeaderProps = z.infer<typeof NavigationHeaderSchema>;
export type MarketplaceStatsProps = z.infer<typeof MarketplaceStatsSchema>;
