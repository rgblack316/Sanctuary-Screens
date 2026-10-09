import { Panel } from "@/components/AdminShell";
import { formatCount, formatDate, formatMoney } from "@/lib/api";

const Cell = ({ label, value, accent }) => (
  <div className="rounded-lg border border-[#222B3E] bg-[#0B0E14] p-4">
    <p className="label-caps">{label}</p>
    <p className={`mt-2 font-display text-3xl font-black ${value == null ? "text-slate-600" : accent ? "text-white" : "text-slate-300"}`}>{value ?? "N/A"}</p>
  </div>
);

export const RegisterMirror = ({ live }) => {
  const cur = live?.current;
  const prev = live?.previous;
  const c = live?.currency ?? "$";
  return (
    <Panel title="On screen now" testid="register-mirror">
      {!cur ? (
        <p className="text-sm text-slate-500" data-testid="mirror-empty">Nothing published yet.</p>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-slate-400" data-testid="mirror-service">
            <span className="font-semibold text-slate-200">{cur.service_label || "Service"}</span> · {formatDate(cur.service_date)}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Cell label="Attendance" value={formatCount(cur.attendance)} accent />
            <Cell label="Offering" value={formatMoney(cur.offering, c)} accent />
            <Cell label="Prev. attendance" value={formatCount(prev?.attendance)} />
            <Cell label="Prev. offering" value={formatMoney(prev?.offering, c)} />
          </div>
          <p className="text-xs text-slate-500" data-testid="mirror-comparison-date">
            {live.comparison_overridden ? "Compared with" : "Previous week ="} {formatDate(live.comparison_service_date)}{live.comparison_overridden && " (chosen date)"}{!prev && " (no record – shows N/A)"}
          </p>
        </div>
      )}
    </Panel>
  );
};
