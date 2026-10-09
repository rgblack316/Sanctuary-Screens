const STYLES = {
  live: { dot: "bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.18)]", text: "Live", cls: "text-emerald-300" },
  connecting: { dot: "bg-amber-400 animate-pulse", text: "Connecting", cls: "text-amber-300" },
  reconnecting: { dot: "bg-amber-400 animate-pulse", text: "Reconnecting", cls: "text-amber-300" },
  offline: { dot: "bg-red-500 animate-pulse", text: "Offline – retrying", cls: "text-red-300" },
};

export const WsStatus = ({ status, subtle = false, className = "" }) => {
  const s = STYLES[status] || STYLES.connecting;
  if (subtle && status === "live") {
    return <span data-testid="ws-status-badge" data-status={status} className={`block h-2 w-2 rounded-full bg-emerald-500/40 ${className}`} />;
  }
  return (
    <span
      data-testid="ws-status-badge"
      data-status={status}
      className={`inline-flex items-center gap-2 rounded-full border border-[#222B3E] bg-[#121620]/90 px-3 py-1 text-xs font-semibold ${s.cls} ${className}`}
    >
      <span className={`h-2 w-2 rounded-full ${s.dot}`} />
      {s.text}
    </span>
  );
};
