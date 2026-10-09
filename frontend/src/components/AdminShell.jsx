import { Link } from "react-router-dom";
import { ExternalLink, Lock, Settings } from "lucide-react";
import { WsStatus } from "@/components/live/WsStatus";
import { lockArea } from "@/components/live/PinGate";

export const AdminShell = ({ area, title, status, displayPath, children }) => (
  <div className="min-h-screen bg-[#0B0E14] text-slate-100">
    <header className="sticky top-0 z-30 border-b border-[#222B3E] bg-[#0B0E14]/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 md:px-8">
        <Link to="/" className="label-caps hover:text-amber-400 transition-colors" data-testid="home-link">Sanctuary Screens</Link>
        <span className="text-slate-600">/</span>
        <h1 className="font-display text-xl font-bold tracking-tight" data-testid="admin-title">{title}</h1>
        <div className="ml-auto flex items-center gap-3">
          {status && <WsStatus status={status} />}
          {area !== "settings" && (
            <Link
              to="/settings-admin"
              data-testid="settings-link"
              title="Display settings"
              className="inline-flex items-center gap-1.5 rounded-md border border-[#222B3E] px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-amber-500/60 hover:text-amber-300 transition-colors"
            >
              <Settings size={12} /> <span className="hidden md:inline">Settings</span>
            </Link>
          )}
          {displayPath && (
          <a
            href={displayPath}
            target="_blank"
            rel="noreferrer"
            data-testid="open-display-link"
            className="hidden sm:inline-flex items-center gap-1.5 rounded-md border border-[#222B3E] px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-amber-500/60 hover:text-amber-300 transition-colors"
          >
            Open {displayPath} <ExternalLink size={12} />
          </a>
          )}
          <button
            onClick={() => lockArea(area)}
            data-testid="lock-admin-btn"
            className="inline-flex items-center gap-1.5 rounded-md border border-[#222B3E] px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-rose-500/60 hover:text-rose-300 transition-colors"
          >
            <Lock size={12} /> Lock
          </button>
        </div>
      </div>
    </header>
    <main className="mx-auto max-w-7xl space-y-8 p-4 md:p-8">{children}</main>
  </div>
);

export const Panel = ({ title, actions, children, className = "", testid }) => (
  <section data-testid={testid} className={`rounded-xl border border-[#222B3E] bg-[#121620] ${className}`}>
    {(title || actions) && (
      <div className="flex flex-wrap items-center gap-3 border-b border-[#222B3E] px-5 py-3">
        <h2 className="label-caps">{title}</h2>
        <div className="ml-auto flex items-center gap-2">{actions}</div>
      </div>
    )}
    <div className="p-5">{children}</div>
  </section>
);
