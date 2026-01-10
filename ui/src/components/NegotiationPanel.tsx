import { useState } from "react";
import { useOnAction } from "@thesysai/genui-sdk";
import {
  MessageSquare,
  DollarSign,
  Send,
  CheckCircle,
  XCircle,
  AlertCircle,
  ArrowRight,
  User,
  Bot,
} from "lucide-react";
import type { NegotiationPanelProps } from "../schemas/marketplace-components";

export function NegotiationPanel({
  bid,
  job_title,
  original_budget,
  negotiation_history,
  can_counter,
  can_approve,
  can_accept,
}: NegotiationPanelProps) {
  const onAction = useOnAction();

  const [counterPrice, setCounterPrice] = useState(bid.price_usd.toString());
  const [counterMessage, setCounterMessage] = useState("");

  const handleCounterOffer = () => {
    const price = parseFloat(counterPrice);
    if (isNaN(price) || price <= 0) return;

    onAction(
      "Submit Counter Offer",
      `User submits counter-offer of $${price} on bid ${bid.bid_id} with message: "${counterMessage}"`
    );
  };

  const handleAccept = () => {
    onAction(
      "Accept Offer",
      `User accepts the current offer of $${bid.final_price_usd || bid.price_usd} on bid ${bid.bid_id}`
    );
  };

  const handleApprove = () => {
    onAction(
      "Approve Bid",
      `User approves bid ${bid.bid_id} for human-in-the-loop authorization at $${bid.final_price_usd || bid.price_usd}`
    );
  };

  const handleReject = () => {
    onAction(
      "Reject Bid",
      `User rejects bid ${bid.bid_id} and ends negotiation`
    );
  };

  const currentPrice = bid.final_price_usd || bid.price_usd;
  const priceDiff = currentPrice - original_budget;
  const priceDiffPercent = ((priceDiff / original_budget) * 100).toFixed(0);

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl border border-slate-700/50 overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-purple-400" />
              Negotiation
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              {job_title} with {bid.agent_name}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-emerald-400">
              ${currentPrice.toFixed(2)}
            </div>
            <div className={`text-xs ${priceDiff > 0 ? "text-amber-400" : "text-emerald-400"}`}>
              {priceDiff > 0 ? "+" : ""}${priceDiff.toFixed(2)} ({priceDiffPercent}%)
              <span className="text-slate-500 ml-1">vs budget</span>
            </div>
          </div>
        </div>

        {/* Price comparison bar */}
        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>Original Budget</span>
              <span>Current Offer</span>
            </div>
            <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-purple-500 rounded-full transition-all"
                style={{ width: `${Math.min(100, (currentPrice / original_budget) * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs mt-1">
              <span className="text-emerald-400">${original_budget.toFixed(2)}</span>
              <span className="text-purple-400">${currentPrice.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Negotiation History */}
      <div className="p-5 border-b border-slate-700/50 max-h-64 overflow-y-auto">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
          History ({negotiation_history.length} rounds)
        </h3>
        <div className="space-y-3">
          {/* Initial bid */}
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-purple-400" />
            </div>
            <div className="flex-1 bg-slate-800/50 rounded-xl p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-purple-400">{bid.agent_name}</span>
                <span className="text-lg font-bold text-white">${bid.price_usd.toFixed(2)}</span>
              </div>
              <p className="text-xs text-slate-400">Initial bid</p>
            </div>
          </div>

          {/* Counter offers */}
          {negotiation_history.map((offer, idx) => {
            const isPoster = offer.by === "poster";
            return (
              <div key={idx} className="flex items-start gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  isPoster ? "bg-blue-500/20" : "bg-purple-500/20"
                }`}>
                  {isPoster ? (
                    <User className="w-4 h-4 text-blue-400" />
                  ) : (
                    <Bot className="w-4 h-4 text-purple-400" />
                  )}
                </div>
                <div className="flex-1 bg-slate-800/50 rounded-xl p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-sm font-medium ${isPoster ? "text-blue-400" : "text-purple-400"}`}>
                      {isPoster ? "You" : bid.agent_name}
                    </span>
                    <span className="text-lg font-bold text-white">${offer.price_usd.toFixed(2)}</span>
                  </div>
                  {offer.message && (
                    <p className="text-sm text-slate-300">{offer.message}</p>
                  )}
                  {offer.created_at && (
                    <p className="text-xs text-slate-500 mt-1">
                      {new Date(offer.created_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Counter Offer Form */}
      {can_counter && (
        <div className="p-5 border-b border-slate-700/50">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            Make Counter Offer
          </h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Your Offer (USD)</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="number"
                  step="0.01"
                  value={counterPrice}
                  onChange={(e) => setCounterPrice(e.target.value)}
                  className="w-full pl-9 pr-4 py-2.5 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition-all"
                  placeholder="Enter your counter offer"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Message (optional)</label>
              <textarea
                value={counterMessage}
                onChange={(e) => setCounterMessage(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition-all resize-none"
                rows={2}
                placeholder="Add a message to your counter offer..."
              />
            </div>
            <button
              onClick={handleCounterOffer}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-purple-500/25 flex items-center justify-center gap-2"
            >
              <Send className="w-4 h-4" />
              Submit Counter Offer
            </button>
          </div>
        </div>
      )}

      {/* Approval Notice */}
      {can_approve && (
        <div className="p-5 border-b border-slate-700/50 bg-orange-500/5">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-orange-400">Human Approval Required</h3>
              <p className="text-xs text-slate-400 mt-1">
                This transaction exceeds $10 and requires your explicit approval before proceeding.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="p-5 flex gap-3">
        <button
          onClick={handleReject}
          className="px-5 py-3 bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium rounded-xl transition-all flex items-center gap-2"
        >
          <XCircle className="w-4 h-4" />
          Reject
        </button>
        {can_approve ? (
          <button
            onClick={handleApprove}
            className="flex-1 py-3 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-orange-500/25 flex items-center justify-center gap-2"
          >
            <CheckCircle className="w-4 h-4" />
            Approve Transaction
          </button>
        ) : can_accept ? (
          <button
            onClick={handleAccept}
            className="flex-1 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-emerald-500/25 flex items-center justify-center gap-2"
          >
            <CheckCircle className="w-4 h-4" />
            Accept Offer
            <ArrowRight className="w-4 h-4" />
          </button>
        ) : null}
      </div>
    </div>
  );
}
