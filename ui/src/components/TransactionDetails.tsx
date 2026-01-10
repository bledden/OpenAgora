import { useOnAction } from "@thesysai/genui-sdk";
import {
  Receipt,
  ArrowRight,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
  ExternalLink,
  Wallet,
  DollarSign,
  Shield,
} from "lucide-react";
import type { TransactionDetailsProps } from "../schemas/marketplace-components";

const txnTypeConfig = {
  escrow: {
    label: "Escrow",
    description: "Funds held in marketplace escrow",
    color: "text-blue-400",
    bgColor: "bg-blue-500/20",
    borderColor: "border-blue-500/30",
  },
  release: {
    label: "Release",
    description: "Payment released to agent",
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/20",
    borderColor: "border-emerald-500/30",
  },
  refund: {
    label: "Refund",
    description: "Funds returned to poster",
    color: "text-amber-400",
    bgColor: "bg-amber-500/20",
    borderColor: "border-amber-500/30",
  },
};

const statusConfig = {
  pending: { label: "Pending", icon: Clock, color: "text-slate-400" },
  escrowed: { label: "Escrowed", icon: Shield, color: "text-blue-400" },
  released: { label: "Released", icon: CheckCircle, color: "text-emerald-400" },
  refunded: { label: "Refunded", icon: RefreshCw, color: "text-amber-400" },
  failed: { label: "Failed", icon: XCircle, color: "text-red-400" },
};

export function TransactionDetails({
  txn_id,
  txn_type,
  job_id,
  amount_usd,
  status,
  payer_wallet,
  payee_wallet,
  x402_payment_id,
  created_at,
}: TransactionDetailsProps) {
  const onAction = useOnAction();

  const typeConfig = txnTypeConfig[txn_type];
  const statusInfo = statusConfig[status];
  const StatusIcon = statusInfo.icon;

  const handleViewJob = () => {
    onAction("View Job", `User wants to view job ${job_id} associated with this transaction`);
  };

  const handleViewOnExplorer = () => {
    if (x402_payment_id) {
      onAction(
        "View on Explorer",
        `User wants to view transaction ${x402_payment_id} on Base network explorer`
      );
    }
  };

  const truncateAddress = (addr: string) => {
    if (addr.length <= 12) return addr;
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  return (
    <div className={`bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl border ${typeConfig.borderColor} overflow-hidden`}>
      {/* Header */}
      <div className={`p-5 ${typeConfig.bgColor}`}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl ${typeConfig.bgColor} flex items-center justify-center`}>
              <Receipt className={`w-6 h-6 ${typeConfig.color}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white">{typeConfig.label} Transaction</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${typeConfig.bgColor} ${typeConfig.color}`}>
                  x402
                </span>
              </div>
              <p className="text-sm text-slate-400">{typeConfig.description}</p>
            </div>
          </div>
          <div className={`flex items-center gap-1.5 ${statusInfo.color}`}>
            <StatusIcon className="w-4 h-4" />
            <span className="text-sm font-medium">{statusInfo.label}</span>
          </div>
        </div>
      </div>

      {/* Amount */}
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex items-center justify-center gap-2">
          <DollarSign className="w-8 h-8 text-emerald-400" />
          <span className="text-4xl font-bold text-white">{amount_usd.toFixed(2)}</span>
          <span className="text-lg text-slate-400">USDC</span>
        </div>
      </div>

      {/* Flow Visualization */}
      <div className="p-5 border-b border-slate-700/50">
        <div className="flex items-center justify-between gap-4">
          {/* Payer */}
          <div className="flex-1 text-center">
            <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center mx-auto mb-2">
              <Wallet className="w-6 h-6 text-blue-400" />
            </div>
            <p className="text-xs text-slate-500 mb-1">
              {txn_type === "escrow" ? "Poster" : txn_type === "release" ? "Escrow" : "Escrow"}
            </p>
            <p className="text-sm text-slate-300 font-mono">{truncateAddress(payer_wallet)}</p>
          </div>

          {/* Arrow */}
          <div className="flex flex-col items-center gap-1">
            <ArrowRight className={`w-6 h-6 ${typeConfig.color}`} />
            <span className="text-xs text-slate-500">${amount_usd.toFixed(2)}</span>
          </div>

          {/* Payee */}
          <div className="flex-1 text-center">
            <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mx-auto mb-2">
              <Wallet className="w-6 h-6 text-purple-400" />
            </div>
            <p className="text-xs text-slate-500 mb-1">
              {txn_type === "escrow" ? "Escrow" : txn_type === "release" ? "Agent" : "Poster"}
            </p>
            <p className="text-sm text-slate-300 font-mono">
              {payee_wallet ? truncateAddress(payee_wallet) : "—"}
            </p>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="p-5 space-y-3">
        <div className="flex justify-between">
          <span className="text-sm text-slate-500">Transaction ID</span>
          <span className="text-sm text-slate-300 font-mono">{truncateAddress(txn_id)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-sm text-slate-500">Job ID</span>
          <button
            onClick={handleViewJob}
            className="text-sm text-cyan-400 hover:text-cyan-300 font-mono"
          >
            {job_id}
          </button>
        </div>
        {x402_payment_id && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-500">x402 Hash</span>
            <span className="text-sm text-slate-300 font-mono">{truncateAddress(x402_payment_id)}</span>
          </div>
        )}
        {created_at && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-500">Created</span>
            <span className="text-sm text-slate-300">
              {new Date(created_at).toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Actions */}
      {x402_payment_id && (
        <div className="p-5 border-t border-slate-700/50">
          <button
            onClick={handleViewOnExplorer}
            className="w-full py-3 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            View on Base Explorer
          </button>
        </div>
      )}
    </div>
  );
}
