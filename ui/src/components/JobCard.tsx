import { useOnAction } from "@thesysai/genui-sdk";
import {
  Bot,
  DollarSign,
  TrendingUp,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Activity,
} from "lucide-react";
import type { JobCardProps } from "../schemas/marketplace-components";

const statusConfig: Record<string, { color: string; icon: typeof CheckCircle; label: string }> = {
  posted: { color: "bg-blue-500/20 text-blue-400", icon: AlertCircle, label: "Open for Bids" },
  bidding: { color: "bg-cyan-500/20 text-cyan-400", icon: Activity, label: "Bidding" },
  negotiating: { color: "bg-purple-500/20 text-purple-400", icon: Activity, label: "Negotiating" },
  awaiting_approval: { color: "bg-orange-500/20 text-orange-400", icon: AlertCircle, label: "Awaiting Approval" },
  assigned: { color: "bg-purple-500/20 text-purple-400", icon: Clock, label: "Assigned" },
  in_progress: { color: "bg-amber-500/20 text-amber-400", icon: Activity, label: "In Progress" },
  completed: { color: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle, label: "Completed" },
  disputed: { color: "bg-red-500/20 text-red-400", icon: AlertCircle, label: "Disputed" },
  cancelled: { color: "bg-red-500/20 text-red-400", icon: XCircle, label: "Cancelled" },
};

export function JobCard({
  job_id,
  title,
  description,
  budget,
  status,
  capabilities,
  quality_score,
  assigned_agent,
}: JobCardProps) {
  const onAction = useOnAction();

  const config = statusConfig[status] || statusConfig.posted;
  const StatusIcon = config.icon;

  const handleViewBids = () => {
    onAction("View Bids", `User wants to view bids for job ${job_id} "${title}"`);
  };

  const handleViewDetails = () => {
    onAction("View Job", `User wants to view details for job ${job_id} "${title}"`);
  };

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700/50 hover:border-cyan-500/50 transition-all duration-300 hover:shadow-xl hover:shadow-cyan-500/10">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-bold text-white mb-1">{title}</h3>
          <p className="text-sm text-slate-400 line-clamp-2">{description}</p>
        </div>
        <span className={`px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 ${config.color}`}>
          <StatusIcon className="w-3.5 h-3.5" />
          {config.label}
        </span>
      </div>

      <div className="flex items-center gap-6 mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <div className="text-lg font-bold text-emerald-400">${budget.toFixed(2)}</div>
            <div className="text-xs text-slate-500">Budget</div>
          </div>
        </div>

        {quality_score !== undefined && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <div className="text-lg font-bold text-amber-400">{(quality_score * 100).toFixed(0)}%</div>
              <div className="text-xs text-slate-500">Quality</div>
            </div>
          </div>
        )}

        {assigned_agent && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-purple-400">{assigned_agent}</div>
              <div className="text-xs text-slate-500">Agent</div>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {capabilities.map((cap) => (
          <span key={cap} className="px-3 py-1 bg-cyan-500/10 text-cyan-400 rounded-lg text-xs font-medium border border-cyan-500/20">
            {cap}
          </span>
        ))}
      </div>

      {status === "posted" || status === "bidding" ? (
        <button
          onClick={handleViewBids}
          className="w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-cyan-500/25"
        >
          View Bids
        </button>
      ) : (
        <button
          onClick={handleViewDetails}
          className="w-full py-3 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-xl transition-all duration-300"
        >
          View Details
        </button>
      )}
    </div>
  );
}
