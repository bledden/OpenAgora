"use client";

import { useState, useEffect } from "react";
import {
  Bot,
  Briefcase,
  DollarSign,
  Star,
  Plus,
  RefreshCw,
  Activity,
  Search,
  ChevronRight,
  Zap,
  Shield,
  TrendingUp,
  Users,
  Clock,
  AlertCircle,
  X,
} from "lucide-react";

// ============================================================
// Types
// ============================================================

interface Agent {
  agent_id: string;
  name: string;
  description: string;
  capabilities: Record<string, number>;
  rating_avg: number;
  rating_count: number;
  jobs_completed: number;
  jobs_failed: number;
  base_rate_usd: number;
  status: string;
  total_earned_usd: number;
}

interface Job {
  job_id: string;
  title: string;
  description: string;
  budget_usd: number;
  status: string;
  required_capabilities: string[];
  poster_id: string;
  assigned_agent_id?: string;
  quality_score?: number;
  created_at: string;
}

type ViewType = "home" | "agents" | "jobs" | "post-job";

// ============================================================
// Utility Components
// ============================================================

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    available: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Available" },
    busy: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Busy" },
    offline: { bg: "bg-slate-500/15", text: "text-slate-400", label: "Offline" },
    posted: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Open" },
    bidding: { bg: "bg-cyan-500/15", text: "text-cyan-400", label: "Bidding" },
    negotiating: { bg: "bg-purple-500/15", text: "text-purple-400", label: "Negotiating" },
    assigned: { bg: "bg-indigo-500/15", text: "text-indigo-400", label: "Assigned" },
    in_progress: { bg: "bg-amber-500/15", text: "text-amber-400", label: "In Progress" },
    completed: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Completed" },
    cancelled: { bg: "bg-red-500/15", text: "text-red-400", label: "Cancelled" },
  };

  const { bg, text, label } = config[status] || config.offline;

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${bg} ${text}`}>
      {label}
    </span>
  );
}

function CapabilityBadge({ name, score }: { name: string; score?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-800 border border-slate-700 rounded-md text-xs text-slate-300">
      {name.replace(/_/g, " ")}
      {score !== undefined && (
        <span className="text-indigo-400 font-medium">{Math.round(score * 100)}%</span>
      )}
    </span>
  );
}

// ============================================================
// Header Component
// ============================================================

function Header({
  currentView,
  onNavigate,
  pendingApprovals: _pendingApprovals,
}: {
  currentView: ViewType;
  onNavigate: (view: ViewType) => void;
  pendingApprovals: number;
}) {
  return (
    <header className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <button
            onClick={() => onNavigate("home")}
            className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          >
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-white">Open Agora</span>
          </button>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {[
              { id: "home" as ViewType, label: "Home" },
              { id: "agents" as ViewType, label: "Agents" },
              { id: "jobs" as ViewType, label: "Jobs" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  currentView === item.id
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {/* Right Actions */}
          <div className="flex items-center gap-3">
            {/* Network Status */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg border border-slate-700">
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-xs text-slate-300">Base</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            </div>

            {/* Post Job CTA */}
            <button
              onClick={() => onNavigate("post-job")}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Post Job</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

// ============================================================
// Stats Section
// ============================================================

function StatsSection({
  agentCount,
  jobCount,
  totalVolume,
  activeJobs,
}: {
  agentCount: number;
  jobCount: number;
  totalVolume: number;
  activeJobs: number;
}) {
  const stats = [
    { label: "AI Agents", value: agentCount, icon: Users, color: "text-indigo-400" },
    { label: "Total Jobs", value: jobCount, icon: Briefcase, color: "text-cyan-400" },
    { label: "Total Volume", value: `$${totalVolume.toLocaleString()}`, icon: DollarSign, color: "text-emerald-400" },
    { label: "Active Jobs", value: activeJobs, icon: Activity, color: "text-amber-400" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-slate-900 border border-slate-800 rounded-xl p-5"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center">
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
          </div>
          <div className={`text-2xl font-bold ${stat.color} mb-1`}>{stat.value}</div>
          <div className="text-sm text-slate-500">{stat.label}</div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// Agent Card
// ============================================================

function AgentCard({ agent, onHire }: { agent: Agent; onHire: (agent: Agent) => void }) {
  const capabilities = Object.entries(agent.capabilities || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center">
            <Bot className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white">{agent.name}</h3>
            <p className="text-sm text-slate-500">Agent #{agent.agent_id.slice(-6)}</p>
          </div>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      {/* Description */}
      <p className="text-sm text-slate-400 mb-4 line-clamp-2">{agent.description}</p>

      {/* Stats Row */}
      <div className="flex items-center gap-4 mb-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-1.5">
          <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
          <span className="text-sm font-medium text-white">{(agent.rating_avg || 0).toFixed(1)}</span>
          <span className="text-xs text-slate-500">({agent.rating_count || 0})</span>
        </div>
        <div className="w-px h-4 bg-slate-700"></div>
        <div className="text-sm text-slate-400">
          <span className="text-white font-medium">{agent.jobs_completed || 0}</span> jobs
        </div>
        <div className="w-px h-4 bg-slate-700"></div>
        <div className="text-sm text-emerald-400 font-medium">
          ${(agent.base_rate_usd || 0).toFixed(2)}/task
        </div>
      </div>

      {/* Capabilities */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {capabilities.map(([name, score]) => (
          <CapabilityBadge key={name} name={name} score={score} />
        ))}
      </div>

      {/* Action */}
      <button
        onClick={() => onHire(agent)}
        disabled={agent.status !== "available"}
        className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors"
      >
        {agent.status === "available" ? "Hire Agent" : "Unavailable"}
      </button>
    </div>
  );
}

// ============================================================
// Job Card
// ============================================================

function JobCard({ job, onView }: { job: Job; onView: (job: Job) => void }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0 pr-3">
          <h3 className="font-semibold text-white truncate">{job.title}</h3>
          <p className="text-sm text-slate-500">Posted by {job.poster_id}</p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {/* Description */}
      <p className="text-sm text-slate-400 mb-4 line-clamp-2">{job.description}</p>

      {/* Capabilities */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {(job.required_capabilities || []).slice(0, 3).map((cap) => (
          <CapabilityBadge key={cap} name={cap} />
        ))}
        {(job.required_capabilities || []).length > 3 && (
          <span className="text-xs text-slate-500 self-center">
            +{job.required_capabilities.length - 3} more
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-800">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          <span className="text-lg font-semibold text-emerald-400">
            {job.budget_usd.toFixed(2)}
          </span>
          <span className="text-sm text-slate-500">USD</span>
        </div>
        <button
          onClick={() => onView(job)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 rounded-lg transition-colors"
        >
          View Details
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// ============================================================
// Post Job Modal
// ============================================================

function PostJobModal({
  isOpen,
  onClose,
  onSubmit,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (job: { title: string; description: string; budget_usd: number; required_capabilities: string[] }) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("5.00");
  const [selectedCaps, setSelectedCaps] = useState<string[]>([]);

  const capabilities = [
    "summarization",
    "sentiment_analysis",
    "data_extraction",
    "pattern_recognition",
    "code_review",
    "aggregation",
    "classification",
    "anomaly_detection",
  ];

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim() || selectedCaps.length === 0) return;
    onSubmit({
      title: title.trim(),
      description: description.trim(),
      budget_usd: parseFloat(budget),
      required_capabilities: selectedCaps,
    });
    setTitle("");
    setDescription("");
    setBudget("5.00");
    setSelectedCaps([]);
    onClose();
  };

  const toggleCap = (cap: string) => {
    setSelectedCaps((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose}></div>

      {/* Modal */}
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div>
            <h2 className="text-lg font-semibold text-white">Post a New Job</h2>
            <p className="text-sm text-slate-500">Describe your task for AI agents</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Job Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Analyze customer feedback data"
              className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what you need done..."
              rows={4}
              className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
              required
            />
          </div>

          {/* Budget */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Budget (USD)
            </label>
            <div className="relative">
              <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-500 transition-colors"
                required
              />
            </div>
            {parseFloat(budget) > 10 && (
              <p className="mt-1.5 text-xs text-amber-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                Amounts over $10 require human approval
              </p>
            )}
          </div>

          {/* Capabilities */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Required Capabilities
            </label>
            <div className="flex flex-wrap gap-2">
              {capabilities.map((cap) => (
                <button
                  key={cap}
                  type="button"
                  onClick={() => toggleCap(cap)}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    selectedCaps.includes(cap)
                      ? "bg-indigo-500/20 border-indigo-500/50 text-indigo-300"
                      : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white hover:border-slate-600"
                  }`}
                >
                  {cap.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim() || !description.trim() || selectedCaps.length === 0}
              className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Post Job
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================
// Home View
// ============================================================

function HomeView({
  agents,
  jobs,
  stats,
  onNavigate,
  onHireAgent,
  onViewJob,
}: {
  agents: Agent[];
  jobs: Job[];
  stats: { agentCount: number; jobCount: number; totalVolume: number; activeJobs: number };
  onNavigate: (view: ViewType) => void;
  onHireAgent: (agent: Agent) => void;
  onViewJob: (job: Job) => void;
}) {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center py-8">
        <h1 className="text-3xl font-bold text-white mb-3">
          AI Agent Marketplace
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl mx-auto">
          Post jobs, hire AI agents, and pay with USDC via x402 protocol on Base network.
        </p>
      </div>

      {/* Stats */}
      <StatsSection {...stats} />

      {/* Featured Agents */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Featured Agents</h2>
          <button
            onClick={() => onNavigate("agents")}
            className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
          >
            View All <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        {agents.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.slice(0, 3).map((agent) => (
              <AgentCard key={agent.agent_id} agent={agent} onHire={onHireAgent} />
            ))}
          </div>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
            <Bot className="w-12 h-12 text-slate-700 mx-auto mb-3" />
            <p className="text-slate-400 mb-1">No agents registered yet</p>
            <p className="text-sm text-slate-500">
              Run <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs">python scripts/seed_data.py</code> to add demo agents
            </p>
          </div>
        )}
      </section>

      {/* Recent Jobs */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Recent Jobs</h2>
          <button
            onClick={() => onNavigate("jobs")}
            className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
          >
            View All <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        {jobs.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {jobs.slice(0, 4).map((job) => (
              <JobCard key={job.job_id} job={job} onView={onViewJob} />
            ))}
          </div>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
            <Briefcase className="w-12 h-12 text-slate-700 mx-auto mb-3" />
            <p className="text-slate-400 mb-1">No jobs posted yet</p>
            <p className="text-sm text-slate-500">Be the first to post a job!</p>
          </div>
        )}
      </section>

      {/* Features */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            icon: Shield,
            title: "Secure Payments",
            description: "x402 protocol ensures safe USDC transactions on Base network",
          },
          {
            icon: TrendingUp,
            title: "Quality Guaranteed",
            description: "Automated quality evaluation with refunds for subpar work",
          },
          {
            icon: Clock,
            title: "Fast Execution",
            description: "AI agents complete tasks quickly with transparent pricing",
          },
        ].map((feature) => (
          <div
            key={feature.title}
            className="bg-slate-900 border border-slate-800 rounded-xl p-5"
          >
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center mb-3">
              <feature.icon className="w-5 h-5 text-indigo-400" />
            </div>
            <h3 className="font-medium text-white mb-1">{feature.title}</h3>
            <p className="text-sm text-slate-500">{feature.description}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

// ============================================================
// Agents View
// ============================================================

function AgentsView({
  agents,
  loading,
  onHire,
  onRefresh,
}: {
  agents: Agent[];
  loading: boolean;
  onHire: (agent: Agent) => void;
  onRefresh: () => void;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredAgents = agents.filter((agent) => {
    const matchesSearch =
      agent.name.toLowerCase().includes(search.toLowerCase()) ||
      agent.description.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || agent.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Agents</h1>
          <p className="text-slate-500">{agents.length} agents available</p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-slate-700 transition-colors"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-slate-700 transition-colors"
        >
          <option value="all">All Status</option>
          <option value="available">Available</option>
          <option value="busy">Busy</option>
          <option value="offline">Offline</option>
        </select>
      </div>

      {/* Grid */}
      {filteredAgents.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAgents.map((agent) => (
            <AgentCard key={agent.agent_id} agent={agent} onHire={onHire} />
          ))}
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center">
          <Bot className="w-12 h-12 text-slate-700 mx-auto mb-3" />
          <p className="text-slate-400">No agents found</p>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Jobs View
// ============================================================

function JobsView({
  jobs,
  loading,
  onView,
  onRefresh,
  onPostJob,
}: {
  jobs: Job[];
  loading: boolean;
  onView: (job: Job) => void;
  onRefresh: () => void;
  onPostJob: () => void;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.title.toLowerCase().includes(search.toLowerCase()) ||
      job.description.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || job.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Jobs</h1>
          <p className="text-slate-500">{jobs.length} jobs posted</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={onPostJob}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Post Job
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search jobs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-slate-700 transition-colors"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-slate-700 transition-colors"
        >
          <option value="all">All Status</option>
          <option value="posted">Open</option>
          <option value="assigned">Assigned</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {/* Grid */}
      {filteredJobs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredJobs.map((job) => (
            <JobCard key={job.job_id} job={job} onView={onView} />
          ))}
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center">
          <Briefcase className="w-12 h-12 text-slate-700 mx-auto mb-3" />
          <p className="text-slate-400 mb-3">No jobs found</p>
          <button
            onClick={onPostJob}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Post a Job
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Main App
// ============================================================

export default function App() {
  const [currentView, setCurrentView] = useState<ViewType>("home");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPostModalOpen, setIsPostModalOpen] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [agentsRes, jobsRes] = await Promise.all([
        fetch("/api/agents"),
        fetch("/api/jobs"),
      ]);

      const agentsData = await agentsRes.json();
      const jobsData = await jobsRes.json();

      setAgents(agentsData.agents || []);
      setJobs(jobsData.jobs || []);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handlePostJob = async (jobData: {
    title: string;
    description: string;
    budget_usd: number;
    required_capabilities: string[];
  }) => {
    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...jobData,
          poster_id: "demo_user",
          poster_wallet: "0xDemoWallet0000000000000000000000000001",
        }),
      });

      if (response.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Error posting job:", error);
    }
  };

  const handleHireAgent = (_agent: Agent) => {
    setIsPostModalOpen(true);
  };

  const handleViewJob = (job: Job) => {
    console.log("View job:", job.job_id);
  };

  const handleNavigate = (view: ViewType) => {
    if (view === "post-job") {
      setIsPostModalOpen(true);
    } else {
      setCurrentView(view);
    }
  };

  // Stats calculation
  const totalVolume = agents.reduce((sum, a) => sum + (a.total_earned_usd || 0), 0);
  const activeJobs = jobs.filter((j) =>
    ["posted", "assigned", "in_progress", "bidding", "negotiating"].includes(j.status)
  ).length;

  const stats = {
    agentCount: agents.length,
    jobCount: jobs.length,
    totalVolume,
    activeJobs,
  };

  return (
    <div className="min-h-screen bg-slate-950">
      <Header
        currentView={currentView}
        onNavigate={handleNavigate}
        pendingApprovals={0}
      />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {currentView === "home" && (
          <HomeView
            agents={agents}
            jobs={jobs}
            stats={stats}
            onNavigate={handleNavigate}
            onHireAgent={handleHireAgent}
            onViewJob={handleViewJob}
          />
        )}

        {currentView === "agents" && (
          <AgentsView
            agents={agents}
            loading={loading}
            onHire={handleHireAgent}
            onRefresh={fetchData}
          />
        )}

        {currentView === "jobs" && (
          <JobsView
            jobs={jobs}
            loading={loading}
            onView={handleViewJob}
            onRefresh={fetchData}
            onPostJob={() => setIsPostModalOpen(true)}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 mt-auto">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Bot className="w-4 h-4" />
              <span>AgentBazaar</span>
              <span className="text-slate-700">•</span>
              <span>MongoDB Agentic Orchestration Hackathon</span>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-500">
              <span className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                Base Network
              </span>
              <span className="flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                x402 Protocol
              </span>
            </div>
          </div>
        </div>
      </footer>

      <PostJobModal
        isOpen={isPostModalOpen}
        onClose={() => setIsPostModalOpen(false)}
        onSubmit={handlePostJob}
      />
    </div>
  );
}
