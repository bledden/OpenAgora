import { useOnAction } from "@thesysai/genui-sdk";
import {
  ClipboardCheck,
  CheckCircle,
  Bot,
  Briefcase,
  DollarSign,
  Star,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import type { ReviewQueueProps } from "../schemas/marketplace-components";

export function ReviewQueue({ pending_reviews }: ReviewQueueProps) {
  const onAction = useOnAction();

  const handleReviewJob = (jobId: string, jobTitle: string) => {
    onAction(
      "Review Job",
      `User wants to review the completed work for job ${jobId} "${jobTitle}"`
    );
  };

  const handleViewResult = (jobId: string) => {
    onAction(
      "View Result",
      `User wants to view the detailed result for job ${jobId}`
    );
  };

  if (pending_reviews.length === 0) {
    return (
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-8 border border-slate-700/50 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-8 h-8 text-emerald-400" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">All Reviewed!</h3>
        <p className="text-slate-400">No jobs pending quality review at this time.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
            <ClipboardCheck className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Pending Reviews</h2>
            <p className="text-sm text-slate-400">
              {pending_reviews.length} job{pending_reviews.length !== 1 ? "s" : ""} awaiting your quality review
            </p>
          </div>
        </div>
        <span className="px-3 py-1.5 bg-cyan-500/20 text-cyan-400 rounded-full text-sm font-semibold">
          {pending_reviews.length} Pending
        </span>
      </div>

      {/* Review Cards */}
      <div className="space-y-3">
        {pending_reviews.map((review) => {
          const aiSuggestion = review.ai_quality_suggestion;
          const suggestedScore = aiSuggestion?.suggested_overall ?? 0.5;
          const recommendation = aiSuggestion?.recommendation ?? "partial";
          const hasRedFlags = aiSuggestion?.red_flags && aiSuggestion.red_flags.length > 0;

          return (
            <div
              key={review.job_id}
              className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-cyan-500/30 hover:border-cyan-500/50 transition-all"
            >
              <div className="flex items-start gap-4">
                {/* Left: Info */}
                <div className="flex-1">
                  {/* Job Title */}
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                      <Briefcase className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">{review.title}</h3>
                      <p className="text-xs text-slate-500">Job #{review.job_id.slice(-6)}</p>
                    </div>
                  </div>

                  {/* Agent Info */}
                  <div className="flex items-center gap-2 mb-3">
                    <Bot className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-slate-300">Completed by {review.agent_name}</span>
                  </div>

                  {/* AI Suggestion Summary */}
                  {aiSuggestion && (
                    <div className="flex items-center gap-4 mb-3">
                      <div className="flex items-center gap-2">
                        <Star className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-slate-300">
                          AI suggests: <span className="font-semibold text-white">{(suggestedScore * 100).toFixed(0)}%</span>
                        </span>
                      </div>
                      <span className={`px-2 py-1 rounded-lg text-xs font-medium ${
                        recommendation === "accept"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : recommendation === "partial"
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-red-500/20 text-red-400"
                      }`}>
                        {recommendation === "accept" ? "Accept" : recommendation === "partial" ? "Partial" : "Reject"}
                      </span>
                      {hasRedFlags && (
                        <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded-lg text-xs flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          {aiSuggestion.red_flags!.length} flag{aiSuggestion.red_flags!.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Budget */}
                  <div className="flex items-center gap-1.5">
                    <DollarSign className="w-4 h-4 text-emerald-400" />
                    <span className="text-lg font-bold text-emerald-400">
                      {review.budget_usd.toFixed(2)}
                    </span>
                    <span className="text-sm text-slate-500">USD</span>
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => handleReviewJob(review.job_id, review.title)}
                    className="px-4 py-2.5 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-medium rounded-xl transition-all shadow-lg hover:shadow-cyan-500/25 flex items-center gap-2"
                  >
                    <ClipboardCheck className="w-4 h-4" />
                    Review Work
                    <ChevronRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleViewResult(review.job_id)}
                    className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium rounded-xl transition-all text-sm"
                  >
                    Preview Result
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Info Note */}
      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
        <div className="flex items-start gap-3">
          <ClipboardCheck className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-slate-300">
              Review completed work and decide on payment.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              AI provides quality suggestions, but you make the final decision on accepting work and rating quality.
              Your rating affects the agent's reputation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
