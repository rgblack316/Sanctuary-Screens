import { useLiveChannel } from "@/hooks/useLiveChannel";
import { WsStatus } from "@/components/live/WsStatus";
import { formatCount, formatDate, formatMoney } from "@/lib/api";

const Metric = ({ testid, label, sub, value, current }) => (
  <div className={`reg-tile ${current ? "current" : ""}`} data-testid={`${testid}-tile`}>
    <div className="flex items-baseline justify-between gap-4">
      <span className={`reg-label font-display font-bold uppercase tracking-[0.14em] ${current ? "text-amber-400" : "text-slate-400"}`}>{label}</span>
      <span className="reg-sub font-semibold text-slate-500 truncate">{sub}</span>
    </div>
    <div data-testid={`${testid}-value`} className={`reg-value mt-[1.5vmin] ${value == null ? "na" : current ? "text-white" : "text-slate-300"}`}>
      {value ?? "N/A"}
    </div>
  </div>
);

export default function RegisterDisplay() {
  const { data, status } = useLiveChannel("register");
  const cur = data?.current;
  const prev = data?.previous;
  const currency = data?.currency ?? "$";
  const prevSub = data?.comparison_service_date ? formatDate(data.comparison_service_date) : "Previous week";

  return (
    <div className="reg-screen" data-testid="register-display">
      <header className="flex items-center gap-4">
        <div className="min-w-0">
          <p className="reg-label font-display font-bold text-white truncate" data-testid="register-service-label">
            {cur?.service_label || "Service"}
          </p>
          <p className="reg-sub text-slate-400" data-testid="register-service-date">{cur ? formatDate(cur.service_date) : ""}</p>
        </div>
        <WsStatus status={status} subtle className="ml-auto" />
      </header>
      {!cur ? (
        <div className="flex flex-1 items-center justify-center text-center" data-testid="register-empty-state">
          <p className="reg-label font-display text-slate-500">Waiting for this week's numbers</p>
        </div>
      ) : (
        <div className="reg-grid">
          <Metric testid="attendance-this-week" label="Attendance" sub="This week" value={formatCount(cur.attendance)} current />
          <Metric testid="offering-this-week" label="Offering" sub="This week" value={formatMoney(cur.offering, currency)} current />
          <Metric testid="attendance-previous-week" label="Attendance" sub={prevSub} value={formatCount(prev?.attendance)} />
          <Metric testid="offering-previous-week" label="Offering" sub={prevSub} value={formatMoney(prev?.offering, currency)} />
        </div>
      )}
    </div>
  );
}
