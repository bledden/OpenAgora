import { useOnAction } from "@thesysai/genui-sdk";
import {
  Bot,
  Clock,
  DollarSign,
  TrendingUp,
  MessageSquare,
  CheckCircle,
  XCircle,
  AlertCircle,
  Handshake,
} from "lucide-react";
import type { BidCardProps } from "../schemas/marketplace-components";

const statusConfig: Record<string, { color: string; icon: typeof CheckCircle; label: string }> = {
  pending: { color: "bg-blue-500/20 text-blue-400 border-blue-500/30", icon: Clock, label: "Pending" },
  counter_offered: { color: "bg-amber-500/20 text-amber-400 border-amber-500/30", icon: MessageSquare, label: "Counter Offered" },
  counter_accepted: { color: "bg-purple-500/20 text-purple-400 border-purple-500/30", icon: Handshake, label: "Counter Accepted" },
  awaiting_approval: { color: "bg-orange-500/20 text-orange-400 border-orange-500/30", icon: AlertCircle, label: "Awaiting Approval" },
  accepted: { color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30", icon: CheckCircle, label: "Accepted" },
  rejected: { color: "bg-red-500/20 text-red-400 border-red-500/30", icon: XCircle, label: "Rejected" },
  withdrawn: { color: "bg-slate-500/20 text-slate-400 border-slate-500/30", icon: XCircle, label: "Withdrawn" },
};

export function BidCard({
  bid_id,
  job_id: _job_id,
  agent_id,
  agent_name,
  price_usd,
  estimated_time_seconds,
  confidence,
  approach,
  status,
  counter_offers,
  requires_approval,
  final_price_usd,
}: BidCardProps) {
  const onAction = useOnAction();

  const config = statusConfig[status] || statusConfig.pending;
  const StatusIcon = config.icon;
  const displayPrice = final_price_usd ?? price_usd;
  const hasNegotiation = counter_offers && counter_offers.length > 0;

  const handleViewAgent = () => {
    onAction(
      "View Agent",
      `User wants to view details for agent ${agent_id} (${agent_name})`
    );
  };

  const handleNegotiate = () => {
    onAction(
      "Negotiate Bid",
      `User wants to negotiate bid ${bid_id} from agent ${agent_name} currently at $${displayPrice}`
    );
  };

  const handleAccept = () => {
    onAction(
      "Accept Bid",
      `User wants to accept bid ${bid_id} from agent ${agent_name} at $${displayPrice}`
    );
  };

  const handleReject = () => {
    onAction(
      "Reject Bid",
      `User wants to reject bid ${bid_id} from agent ${agent_name}`
    );
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-slate-700/50 hover:border-purple-500/50 transition-all duration-300">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <button
              onClick={handleViewAgent}
              className="text-lg font-semibold text-white hover:text-purple-400 transition-colors"
            >
              {agent_name}
            </button>
            <p className="text-xs text-slate-500">Bid #{bid_id.slice(-6)}</p>
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${config.color}`}>
          <StatusIcon className="w-3 h-3" />
          {config.label}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-800/50 rounded-xl p-3 text-center">
          <div className="flex items-center justify-center gap-1 text-emerald-400 mb-1">
            <DollarSign className="w-4 h-4" />
            <span className="font-bold">{displayPrice.toFixed(2)}</span>
          </div>
          <span className="text-xs text-slate-500">
            {final_price_usd ? "Final" : "Bid"} Price
          </span>
        </div>
        {confidence !== undefined && (
          <div className="bg-slate-800/50 rounded-xl p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-cyan-400 mb-1">
              <TrendingUp className="w-4 h-4" />
              <span className="font-bold">{(confidence * 100).toFixed(0)}%</span>
            </div>
            <span className="text-xs text-slate-500">Confidence</span>
          </div>
        )}
        {estimated_time_seconds !== undefined && (
          <div className="bg-slate-800/50 rounded-xl p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-amber-400 mb-1">
              <Clock className="w-4 h-4" />
              <span className="font-bold">{formatTime(estimated_time_seconds)}</span>
            </div>
            <span className="text-xs text-slate-500">Est. Time</span>
          </div>
        )}
      </div>

      {/* Approach */}
      {approach && (
        <div className="mb-4">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Approach</p>
          <p className="text-sm text-slate-300 line-clamp-2">{approach}</p>
        </div>
      )}

      {/* Negotiation History */}
      {hasNegotiation && (
        <div className="mb-4 p-3 bg-slate-800/30 rounded-xl border border-slate-700/50">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <MessageSquare className="w-3 h-3" />
            Negotiation ({counter_offers!.length} rounds)
          </p>
          <div className="space-y-2">
            {counter_offers!.slice(-2).map((offer, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <span className={offer.by === "poster" ? "text-blue-400" : "text-purple-400"}>
                  {offer.by === "poster" ? "You" : agent_name}
                </span>
                <span className="text-slate-300">${offer.price_usd.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Approval Warning */}
      {requires_approval && status === "awaiting_approval" && (
        <div className="mb-4 p-3 bg-orange-500/10 rounded-xl border border-orange-500/30">
          <p className="text-xs text-orange-400 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            Requires human approval (amount &gt; $10)
          </p>
        </div>
      )}

      {/* Actions */}
      {status === "pending" && (
        <div className="flex gap-2">
          <button
            onClick={handleNegotiate}
            className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-xl transition-all text-sm"
          >
            Counter Offer
          </button>
          <button
            onClick={handleAccept}
            className="flex-1 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-medium rounded-xl transition-all text-sm"
          >
            Accept
          </button>
          <button
            onClick={handleReject}
            className="px-4 py-2.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium rounded-xl transition-all text-sm"
          >
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {status === "counter_offered" && (
        <div className="flex gap-2">
          <button
            onClick={handleNegotiate}
            className="flex-1 py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-medium rounded-xl transition-all text-sm"
          >
            View Negotiation
          </button>
        </div>
      )}
    </div>
  );
}
