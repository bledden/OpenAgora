import { useState } from "react";
import { useOnAction } from "@thesysai/genui-sdk";
import { DollarSign, MessageSquare, Send } from "lucide-react";
import type { CounterOfferFormProps } from "../schemas/marketplace-components";

export function CounterOfferForm({
  bid_id,
  current_price,
  min_price,
  max_price,
  job_title,
}: CounterOfferFormProps) {
  const onAction = useOnAction();

  const [price, setPrice] = useState(current_price.toString());
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const priceNum = parseFloat(price);
    if (isNaN(priceNum) || priceNum <= 0) return;

    onAction(
      "Submit Counter Offer",
      `User submits counter-offer of $${priceNum.toFixed(2)} on bid ${bid_id}${
        message ? ` with message: "${message}"` : ""
      }${job_title ? ` for job "${job_title}"` : ""}`
    );
  };

  const suggestedPrices = [
    { label: "-10%", value: current_price * 0.9 },
    { label: "-20%", value: current_price * 0.8 },
    { label: "-30%", value: current_price * 0.7 },
  ].filter((p) => !min_price || p.value >= min_price);

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-slate-700/50">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
          <MessageSquare className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h3 className="font-semibold text-white">Counter Offer</h3>
          <p className="text-xs text-slate-500">
            Current offer: ${current_price.toFixed(2)}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Price Input */}
        <div>
          <label className="block text-sm text-slate-400 mb-2">Your Offer (USD)</label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="number"
              step="0.01"
              min={min_price || 0.01}
              max={max_price}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition-all"
              placeholder="Enter your counter offer"
            />
          </div>

          {/* Quick Select Buttons */}
          {suggestedPrices.length > 0 && (
            <div className="flex gap-2 mt-2">
              {suggestedPrices.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => setPrice(p.value.toFixed(2))}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg text-xs transition-all"
                >
                  {p.label} (${p.value.toFixed(2)})
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Message Input */}
        <div>
          <label className="block text-sm text-slate-400 mb-2">Message (optional)</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition-all resize-none"
            rows={2}
            placeholder="Explain your counter offer..."
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-purple-500/25 flex items-center justify-center gap-2"
        >
          <Send className="w-4 h-4" />
          Submit Counter Offer
        </button>
      </form>
    </div>
  );
}
