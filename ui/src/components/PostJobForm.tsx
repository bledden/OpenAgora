import { useState } from "react";
import { useOnAction } from "@thesysai/genui-sdk";
import {
  Briefcase,
  DollarSign,
  Tag,
  FileText,
  Bot,
  Send,
  X,
} from "lucide-react";
import type { PostJobFormProps } from "../schemas/marketplace-components";

const AVAILABLE_CAPABILITIES = [
  "summarization",
  "sentiment_analysis",
  "data_extraction",
  "pattern_recognition",
  "code_review",
  "aggregation",
  "classification",
  "anomaly_detection",
];

export function PostJobForm({
  initial_title,
  initial_description,
  suggested_capabilities,
  suggested_budget,
  preselected_agent_id,
  preselected_agent_name,
}: PostJobFormProps) {
  const onAction = useOnAction();

  const [title, setTitle] = useState(initial_title || "");
  const [description, setDescription] = useState(initial_description || "");
  const [budget, setBudget] = useState(suggested_budget?.toString() || "5.00");
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>(
    suggested_capabilities || []
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim() || !description.trim()) return;

    const jobData = {
      title: title.trim(),
      description: description.trim(),
      budget_usd: parseFloat(budget),
      required_capabilities: selectedCapabilities,
      preselected_agent_id,
    };

    onAction(
      "Submit Job",
      `User posts new job: "${title}" with budget $${budget}, capabilities: [${selectedCapabilities.join(", ")}]${
        preselected_agent_id ? `, pre-assigned to agent ${preselected_agent_id}` : ""
      }. Job data: ${JSON.stringify(jobData)}`
    );
  };

  const handleCancel = () => {
    onAction("Cancel Post Job", "User cancels job posting and returns to previous page");
  };

  const toggleCapability = (cap: string) => {
    setSelectedCapabilities((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap]
    );
  };

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl border border-slate-700/50 overflow-hidden max-w-2xl mx-auto">
      {/* Header */}
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <Briefcase className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Post a New Job</h2>
              <p className="text-sm text-slate-400">
                Describe your task and let AI agents bid on it
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Pre-selected Agent Banner */}
        {preselected_agent_id && preselected_agent_name && (
          <div className="mt-4 p-3 bg-purple-500/10 rounded-xl border border-purple-500/30 flex items-center gap-3">
            <Bot className="w-5 h-5 text-purple-400" />
            <div>
              <p className="text-sm text-purple-300">
                Hiring <span className="font-semibold">{preselected_agent_name}</span>
              </p>
              <p className="text-xs text-slate-500">
                This job will be offered directly to this agent
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="p-5 space-y-5">
        {/* Title */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
            <FileText className="w-4 h-4 text-slate-500" />
            Job Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-4 py-3 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
            placeholder="e.g., Analyze customer feedback data"
            required
          />
        </div>

        {/* Description */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
            <FileText className="w-4 h-4 text-slate-500" />
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-4 py-3 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all resize-none"
            rows={4}
            placeholder="Describe what you need done, including any specific requirements or data sources..."
            required
          />
        </div>

        {/* Budget */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
            <DollarSign className="w-4 h-4 text-slate-500" />
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
              className="w-full pl-9 pr-4 py-3 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
              placeholder="5.00"
              required
            />
          </div>
          {parseFloat(budget) > 10 && (
            <p className="text-xs text-orange-400 mt-1 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-400" />
              Amounts over $10 require human approval before execution
            </p>
          )}
        </div>

        {/* Capabilities */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
            <Tag className="w-4 h-4 text-slate-500" />
            Required Capabilities
          </label>
          <div className="flex flex-wrap gap-2">
            {AVAILABLE_CAPABILITIES.map((cap) => {
              const isSelected = selectedCapabilities.includes(cap);
              return (
                <button
                  key={cap}
                  type="button"
                  onClick={() => toggleCapability(cap)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    isSelected
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50"
                      : "bg-slate-800/50 text-slate-400 border border-slate-600 hover:border-slate-500"
                  }`}
                >
                  {cap.replace("_", " ")}
                </button>
              );
            })}
          </div>
          {selectedCapabilities.length === 0 && (
            <p className="text-xs text-slate-500 mt-2">
              Select at least one capability to help match your job with the right agents
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <button
            type="button"
            onClick={handleCancel}
            className="flex-1 px-6 py-3 bg-slate-700 hover:bg-slate-600 text-slate-300 font-semibold rounded-xl transition-all"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim() || !description.trim() || selectedCapabilities.length === 0}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-emerald-500/25 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
            Post Job
          </button>
        </div>
      </form>

      {/* Info */}
      <div className="px-5 pb-5">
        <div className="p-4 bg-slate-800/30 rounded-xl border border-slate-700/50">
          <p className="text-sm text-slate-400">
            After posting, qualified AI agents will submit bids. You can review bids, negotiate prices, and select the best agent for your job.
          </p>
        </div>
      </div>
    </div>
  );
}
