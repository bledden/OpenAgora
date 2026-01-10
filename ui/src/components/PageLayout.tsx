import { ReactNode } from "react";
import type { PageLayoutProps } from "../schemas/marketplace-components";

interface PageLayoutComponentProps extends PageLayoutProps {
  children?: ReactNode;
}

const pageTypeLabels: Record<string, string> = {
  home: "Marketplace Home",
  agents_list: "AI Agents",
  jobs_list: "Jobs",
  agent_detail: "Agent Details",
  job_detail: "Job Details",
  post_job: "Post a Job",
  negotiations: "Negotiations",
  approvals: "Pending Approvals",
  transaction_history: "Transactions",
};

export function PageLayout({
  page_type,
  title,
  subtitle,
  children,
}: PageLayoutComponentProps) {
  return (
    <div className="min-h-screen bg-slate-950">
      {/* Page Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-2">
          <span>AgentBazaar</span>
          <span>/</span>
          <span className="text-slate-400">{pageTypeLabels[page_type] || page_type}</span>
        </div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-white via-indigo-200 to-cyan-200 bg-clip-text text-transparent">
          {title}
        </h1>
        {subtitle && (
          <p className="text-slate-400 mt-2">{subtitle}</p>
        )}
      </div>

      {/* Page Content */}
      <div className="px-6 pb-6">
        {children}
      </div>

      {/* Footer */}
      <footer className="px-6 py-4 border-t border-slate-800">
        <p className="text-sm text-slate-500 text-center">
          Built for MongoDB Agentic Orchestration Hackathon | Powered by x402 + MongoDB Atlas
        </p>
      </footer>
    </div>
  );
}
