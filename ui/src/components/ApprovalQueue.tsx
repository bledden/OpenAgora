import { useOnAction } from "@thesysai/genui-sdk";
import {
  AlertCircle,
  CheckCircle,
  XCircle,
  DollarSign,
  Bot,
  Briefcase,
  Clock,
} from "lucide-react";
import type { ApprovalQueueProps } from "../schemas/marketplace-components";

export function ApprovalQueue({ pending_approvals }: ApprovalQueueProps) {
  const onAction = useOnAction();

  const handleApprove = (bidId: string, jobTitle: string, price: number) => {
    onAction(
      "Approve Bid",
      `User approves bid ${bidId} for job "${jobTitle}" at $${price}`
    );
  };

  const handleReject = (bidId: string, jobTitle: string) => {
    onAction(
      "Reject Bid",
      `User rejects bid ${bidId} for job "${jobTitle}"`
    );
  };

  const handleViewDetails = (bidId: string, jobId: string) => {
    onAction(
      "View Bid Details",
      `User wants to view full details for bid ${bidId} on job ${jobId}`
    );
  };

  if (pending_approvals.length === 0) {
    return (
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-8 border border-slate-700/50 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-8 h-8 text-emerald-400" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">All Caught Up!</h3>
        <p className="text-slate-400">No pending approvals at this time.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500/20 flex items-center justify-center">
            <AlertCircle className="w-5 h-5 text-orange-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Pending Approvals</h2>
            <p className="text-sm text-slate-400">
              {pending_approvals.length} transaction{pending_approvals.length !== 1 ? "s" : ""} awaiting your approval
            </p>
          </div>
        </div>
        <span className="px-3 py-1.5 bg-orange-500/20 text-orange-400 rounded-full text-sm font-semibold">
          {pending_approvals.length} Pending
        </span>
      </div>

      {/* Approval Cards */}
      <div className="space-y-3">
        {pending_approvals.map((approval) => (
          <div
            key={approval.bid_id}
            className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-orange-500/30 hover:border-orange-500/50 transition-all"
          >
            <div className="flex items-start gap-4">
              {/* Left: Info */}
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">{approval.agent_name}</h3>
                    <p className="text-xs text-slate-500">Agent #{approval.agent_id.slice(-6)}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-3">
                  <Briefcase className="w-4 h-4 text-slate-500" />
                  <span className="text-sm text-slate-300">{approval.job_title}</span>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <DollarSign className="w-4 h-4 text-emerald-400" />
                    <span className="text-lg font-bold text-emerald-400">
                      {approval.price_usd.toFixed(2)}
                    </span>
                  </div>
                  <span className="px-2 py-1 bg-orange-500/10 text-orange-400 rounded-lg text-xs">
                    {approval.approval_reason}
                  </span>
                </div>
              </div>

              {/* Right: Actions */}
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => handleApprove(approval.bid_id, approval.job_title, approval.price_usd)}
                  className="px-4 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-medium rounded-xl transition-all shadow-lg hover:shadow-emerald-500/25 flex items-center gap-2"
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve
                </button>
                <button
                  onClick={() => handleReject(approval.bid_id, approval.job_title)}
                  className="px-4 py-2.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium rounded-xl transition-all flex items-center gap-2"
                >
                  <XCircle className="w-4 h-4" />
                  Reject
                </button>
                <button
                  onClick={() => handleViewDetails(approval.bid_id, approval.job_id)}
                  className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium rounded-xl transition-all text-sm"
                >
                  View Details
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Info Note */}
      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
        <div className="flex items-start gap-3">
          <Clock className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-slate-300">
              Transactions over $10 require human approval as a safety measure.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Review each transaction carefully before approving. Approved transactions will proceed with x402 payment processing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
