import { useState } from "react";
import { useOnAction } from "@thesysai/genui-sdk";
import {
  ClipboardCheck,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Bot,
  Briefcase,
  Star,
  TrendingUp,
  MessageSquare,
  ThumbsUp,
  Minus,
  Send,
} from "lucide-react";
import type { JobReviewPanelProps } from "../schemas/marketplace-components";

export function JobReviewPanel({
  job_id,
  title,
  description,
  result,
  agent_id,
  agent_name,
  budget_usd,
  ai_suggestion,
}: JobReviewPanelProps) {
  const onAction = useOnAction();

  const [decision, setDecision] = useState<"accept" | "partial" | "reject" | null>(null);
  const [rating, setRating] = useState(ai_suggestion.suggested_overall);
  const [feedback, setFeedback] = useState("");

  const handleSubmitReview = () => {
    if (!decision) return;

    onAction(
      "Submit Review",
      `User submits review for job ${job_id}: decision="${decision}", rating=${rating}, feedback="${feedback}"`
    );
  };

  const handleAcceptAISuggestion = () => {
    setDecision(ai_suggestion.recommendation);
    setRating(ai_suggestion.suggested_overall);
  };

  const scores = ai_suggestion.scores;
  const scoreEntries = [
    { name: "Relevance", value: scores.relevance, color: "from-blue-500 to-cyan-500" },
    { name: "Accuracy", value: scores.accuracy, color: "from-purple-500 to-pink-500" },
    { name: "Completeness", value: scores.completeness, color: "from-amber-500 to-orange-500" },
    { name: "Clarity", value: scores.clarity, color: "from-emerald-500 to-teal-500" },
    { name: "Actionability", value: scores.actionability, color: "from-indigo-500 to-violet-500" },
  ];

  const paymentAmount = decision === "accept" ? budget_usd : decision === "partial" ? budget_usd * 0.5 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700/50">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-teal-500/20 flex items-center justify-center">
              <ClipboardCheck className="w-7 h-7 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Review Work</h1>
              <p className="text-slate-400">{title}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-emerald-400">${budget_usd.toFixed(2)}</div>
            <div className="text-sm text-slate-500">Budget</div>
          </div>
        </div>

        {/* Agent Info */}
        <div className="flex items-center gap-3 p-3 bg-slate-800/50 rounded-xl">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
            <Bot className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-white">{agent_name}</p>
            <p className="text-xs text-slate-500">Agent #{agent_id.slice(-6)}</p>
          </div>
        </div>
      </div>

      {/* Task Description */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Briefcase className="w-4 h-4" />
          Task Description
        </h3>
        <p className="text-slate-300">{description}</p>
      </div>

      {/* Agent's Result */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <MessageSquare className="w-4 h-4" />
          Agent's Result
        </h3>
        <div className="bg-slate-800/50 rounded-xl p-4 max-h-64 overflow-y-auto">
          <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono">
            {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      </div>

      {/* AI Quality Suggestion */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-cyan-500/30">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-cyan-400 uppercase tracking-wide flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            AI Quality Suggestion
          </h3>
          <span className="px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs rounded-lg">
            AI Generated - You Decide
          </span>
        </div>

        {/* Overall Score */}
        <div className="flex items-center gap-4 mb-4 p-4 bg-slate-800/50 rounded-xl">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-400">Suggested Overall Score</span>
              <span className="text-2xl font-bold text-white">
                {(ai_suggestion.suggested_overall * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-teal-500 rounded-full transition-all"
                style={{ width: `${ai_suggestion.suggested_overall * 100}%` }}
              />
            </div>
          </div>
          <div className={`px-4 py-2 rounded-xl font-semibold ${
            ai_suggestion.recommendation === "accept"
              ? "bg-emerald-500/20 text-emerald-400"
              : ai_suggestion.recommendation === "partial"
              ? "bg-amber-500/20 text-amber-400"
              : "bg-red-500/20 text-red-400"
          }`}>
            {ai_suggestion.recommendation === "accept" ? "Accept" : ai_suggestion.recommendation === "partial" ? "Partial" : "Reject"}
          </div>
        </div>

        {/* Individual Scores */}
        <div className="grid grid-cols-5 gap-3 mb-4">
          {scoreEntries.map((score) => (
            <div key={score.name} className="text-center">
              <div className="text-lg font-bold text-white mb-1">
                {(score.value * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-slate-500">{score.name}</div>
              <div className="h-1.5 bg-slate-700 rounded-full mt-2 overflow-hidden">
                <div
                  className={`h-full bg-gradient-to-r ${score.color} rounded-full`}
                  style={{ width: `${score.value * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Feedback */}
        <div className="space-y-3">
          <p className="text-sm text-slate-300">{ai_suggestion.feedback}</p>

          {/* Strengths */}
          {ai_suggestion.strengths.length > 0 && (
            <div className="p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
              <p className="text-xs font-semibold text-emerald-400 uppercase mb-2">Strengths</p>
              <ul className="space-y-1">
                {ai_suggestion.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <ThumbsUp className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Improvements */}
          {ai_suggestion.improvements.length > 0 && (
            <div className="p-3 bg-amber-500/10 rounded-xl border border-amber-500/20">
              <p className="text-xs font-semibold text-amber-400 uppercase mb-2">Areas for Improvement</p>
              <ul className="space-y-1">
                {ai_suggestion.improvements.map((s, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <Minus className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Red Flags */}
          {ai_suggestion.red_flags.length > 0 && (
            <div className="p-3 bg-red-500/10 rounded-xl border border-red-500/20">
              <p className="text-xs font-semibold text-red-400 uppercase mb-2">Red Flags</p>
              <ul className="space-y-1">
                {ai_suggestion.red_flags.map((s, i) => (
                  <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Accept AI Suggestion Button */}
        <button
          onClick={handleAcceptAISuggestion}
          className="mt-4 w-full py-2.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 font-medium rounded-xl transition-all text-sm"
        >
          Use AI Suggestion as Starting Point
        </button>
      </div>

      {/* Your Decision */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-4 flex items-center gap-2">
          <Star className="w-4 h-4" />
          Your Decision
        </h3>

        {/* Decision Buttons */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <button
            onClick={() => setDecision("accept")}
            className={`p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2 ${
              decision === "accept"
                ? "border-emerald-500 bg-emerald-500/20"
                : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
            }`}
          >
            <CheckCircle className={`w-6 h-6 ${decision === "accept" ? "text-emerald-400" : "text-slate-500"}`} />
            <span className={`font-semibold ${decision === "accept" ? "text-emerald-400" : "text-slate-400"}`}>
              Accept
            </span>
            <span className="text-xs text-slate-500">Full Payment</span>
          </button>
          <button
            onClick={() => setDecision("partial")}
            className={`p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2 ${
              decision === "partial"
                ? "border-amber-500 bg-amber-500/20"
                : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
            }`}
          >
            <Minus className={`w-6 h-6 ${decision === "partial" ? "text-amber-400" : "text-slate-500"}`} />
            <span className={`font-semibold ${decision === "partial" ? "text-amber-400" : "text-slate-400"}`}>
              Partial
            </span>
            <span className="text-xs text-slate-500">50% Payment</span>
          </button>
          <button
            onClick={() => setDecision("reject")}
            className={`p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2 ${
              decision === "reject"
                ? "border-red-500 bg-red-500/20"
                : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
            }`}
          >
            <XCircle className={`w-6 h-6 ${decision === "reject" ? "text-red-400" : "text-slate-500"}`} />
            <span className={`font-semibold ${decision === "reject" ? "text-red-400" : "text-slate-400"}`}>
              Reject
            </span>
            <span className="text-xs text-slate-500">Full Refund</span>
          </button>
        </div>

        {/* Rating Slider */}
        <div className="mb-4">
          <label className="block text-sm text-slate-400 mb-2">
            Your Quality Rating: <span className="text-white font-semibold">{(rating * 100).toFixed(0)}%</span>
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={rating * 100}
            onChange={(e) => setRating(parseInt(e.target.value) / 100)}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </div>
        </div>

        {/* Feedback */}
        <div className="mb-4">
          <label className="block text-sm text-slate-400 mb-2">Feedback (optional)</label>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Add any feedback for the agent..."
            rows={3}
            className="w-full px-4 py-3 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition-all resize-none"
          />
        </div>

        {/* Payment Summary */}
        {decision && (
          <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-700 mb-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Payment to Agent</span>
              <span className={`text-xl font-bold ${
                decision === "accept" ? "text-emerald-400" : decision === "partial" ? "text-amber-400" : "text-red-400"
              }`}>
                ${paymentAmount.toFixed(2)}
              </span>
            </div>
            {decision === "reject" && (
              <p className="text-xs text-red-400 mt-2">
                Full amount will be refunded to your wallet.
              </p>
            )}
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={handleSubmitReview}
          disabled={!decision}
          className={`w-full py-4 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 ${
            decision
              ? "bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white shadow-lg hover:shadow-cyan-500/25"
              : "bg-slate-800 text-slate-500 cursor-not-allowed"
          }`}
        >
          <Send className="w-5 h-5" />
          Submit Review & Process Payment
        </button>
      </div>
    </div>
  );
}
