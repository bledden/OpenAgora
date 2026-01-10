import { useOnAction } from "@thesysai/genui-sdk";
import {
  Bot,
  Briefcase,
  Home,
  Plus,
  Bell,
  Zap,
  Receipt,
} from "lucide-react";
import type { NavigationHeaderProps } from "../schemas/marketplace-components";

const navItems = [
  { id: "home", label: "Home", icon: Home },
  { id: "agents_list", label: "Agents", icon: Bot },
  { id: "jobs_list", label: "Jobs", icon: Briefcase },
  { id: "approvals", label: "Approvals", icon: Bell },
  { id: "transaction_history", label: "Transactions", icon: Receipt },
];

export function NavigationHeader({
  current_page,
  show_post_job_button = true,
  pending_approvals_count = 0,
}: NavigationHeaderProps) {
  const onAction = useOnAction();

  const handleNavigation = (pageId: string) => {
    const pageLabels: Record<string, string> = {
      home: "marketplace home page",
      agents_list: "agents list",
      jobs_list: "jobs list",
      approvals: "pending approvals",
      transaction_history: "transaction history",
    };
    onAction(
      `Navigate to ${pageId}`,
      `User wants to view the ${pageLabels[pageId] || pageId}`
    );
  };

  const handlePostJob = () => {
    onAction(
      "Post Job",
      "User wants to post a new job. Show the job posting form."
    );
  };

  return (
    <header className="mx-6 mt-6 p-4 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 rounded-2xl border border-slate-700/50">
      <div className="flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/25">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-white via-indigo-200 to-cyan-200 bg-clip-text text-transparent">
              AgentBazaar
            </h1>
            <p className="text-xs text-slate-500">AI Agent Marketplace</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = current_page === item.id;
            const showBadge = item.id === "approvals" && pending_approvals_count > 0;

            return (
              <button
                key={item.id}
                onClick={() => handleNavigation(item.id)}
                className={`
                  relative px-4 py-2 rounded-xl font-medium text-sm transition-all flex items-center gap-2
                  ${isActive
                    ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                {item.label}
                {showBadge && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                    {pending_approvals_count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium text-emerald-400">x402 Active</span>
          </div>
          <div className="px-3 py-1.5 bg-cyan-500/10 border border-cyan-500/30 rounded-lg flex items-center gap-2">
            <Zap className="w-3 h-3 text-cyan-400" />
            <span className="text-xs font-medium text-cyan-400">Base</span>
          </div>
          {show_post_job_button && (
            <button
              onClick={handlePostJob}
              className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-emerald-500/25 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Post Job
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
