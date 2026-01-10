import { useOnAction } from "@thesysai/genui-sdk";
import { Bot, Star } from "lucide-react";
import type { AgentCardProps } from "../schemas/marketplace-components";

export function AgentCard({
  agent_id,
  name,
  description,
  capabilities,
  rating,
  jobs_completed,
  base_rate,
  status,
}: AgentCardProps) {
  const onAction = useOnAction();

  const statusColors: Record<string, string> = {
    available: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    busy: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    offline: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  };

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700/50 hover:border-indigo-500/50 transition-all duration-300 hover:shadow-xl hover:shadow-indigo-500/10">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">{name}</h3>
            <p className="text-sm text-slate-400 line-clamp-1">{description}</p>
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${statusColors[status] || statusColors.offline}`}>
          {status}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-slate-800/50 rounded-xl p-3 text-center">
          <div className="flex items-center justify-center gap-1 text-amber-400 mb-1">
            <Star className="w-4 h-4 fill-current" />
            <span className="font-bold">{rating.toFixed(1)}</span>
          </div>
          <span className="text-xs text-slate-500">Rating</span>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-3 text-center">
          <div className="text-cyan-400 font-bold mb-1">{jobs_completed}</div>
          <span className="text-xs text-slate-500">Jobs Done</span>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-3 text-center">
          <div className="text-emerald-400 font-bold mb-1">${base_rate.toFixed(2)}</div>
          <span className="text-xs text-slate-500">Per Task</span>
        </div>
      </div>

      <div className="mb-4">
        <div className="text-xs text-slate-500 mb-2 uppercase tracking-wide">Top Capabilities</div>
        <div className="flex flex-wrap gap-2">
          {capabilities.slice(0, 4).map((cap) => (
            <div key={cap.name} className="flex items-center gap-2 bg-slate-800/70 rounded-lg px-3 py-1.5">
              <span className="text-xs text-slate-300">{cap.name}</span>
              <div className="w-12 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                  style={{ width: `${cap.score * 100}%` }}
                />
              </div>
              <span className="text-xs text-indigo-400 font-medium">{(cap.score * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={() => onAction("Hire Agent", `User wants to hire agent ${agent_id} (${name})`)}
        className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-indigo-500/25"
      >
        Hire This Agent
      </button>
    </div>
  );
}
