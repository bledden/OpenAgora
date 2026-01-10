import { Bot, Briefcase, DollarSign, Activity } from "lucide-react";
import type { MarketplaceStatsProps } from "../schemas/marketplace-components";

export function MarketplaceStats({
  total_agents,
  total_jobs,
  total_volume,
  active_jobs,
}: MarketplaceStatsProps) {
  const stats = [
    { label: "AI Agents", value: total_agents, icon: Bot, color: "from-indigo-500 to-purple-500", bgColor: "bg-indigo-500/10", textColor: "text-indigo-400" },
    { label: "Total Jobs", value: total_jobs, icon: Briefcase, color: "from-cyan-500 to-blue-500", bgColor: "bg-cyan-500/10", textColor: "text-cyan-400" },
    { label: "Volume (USD)", value: `$${total_volume.toLocaleString()}`, icon: DollarSign, color: "from-emerald-500 to-teal-500", bgColor: "bg-emerald-500/10", textColor: "text-emerald-400" },
    { label: "Active Now", value: active_jobs, icon: Activity, color: "from-amber-500 to-orange-500", bgColor: "bg-amber-500/10", textColor: "text-amber-400" },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div key={stat.label} className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-5 border border-slate-700/50">
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-10 h-10 rounded-xl ${stat.bgColor} flex items-center justify-center`}>
              <stat.icon className={`w-5 h-5 ${stat.textColor}`} />
            </div>
            <span className="text-sm text-slate-400">{stat.label}</span>
          </div>
          <div className={`text-2xl font-bold ${stat.textColor}`}>
            {stat.value}
          </div>
        </div>
      ))}
    </div>
  );
}
