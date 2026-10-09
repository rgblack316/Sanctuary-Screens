import { useLiveChannel } from "@/hooks/useLiveChannel";
import { usePreview } from "@/hooks/usePreview";
import { WsStatus } from "@/components/live/WsStatus";
import { DisplayBackground, ChurchName, appearanceVars } from "@/components/live/DisplayBackground";
import { formatCount, formatDate, formatMoney } from "@/lib/api";

const SAMPLE = {
  currency: "$",
  current: { service_label: "Sunday Service", service_date: "2026-01-11", attendance: 248, offering: 4385.5 },
  previous: { attendance: 231, offering: 3920 },
  comparison_service_date: "2026-01-04",
};

const Metric = ({ testid, label, sub, value, current }) => (
  <div className={`reg-tile ${current ? "current" : ""}`} data-testid={`${testid}-tile`}>
    <div className="flex items-baseline justify-between gap-4">
      <span className={`reg-label font-display font-bold uppercase tracking-[0.14em] ${current ? "ss-accent" : "ss-muted"}`}>{label}</span>
      <span className="reg-sub font-semibold ss-muted truncate">{sub}</span>
    </div>
    <div data-testid={`${testid}-value`} className={`reg-value mt-[1.5vmin] ${value == null ? "na" : current ? "ss-text" : "ss-text-soft"}`}>
      {value ?? "N/A"}
    </div>
  </div>
);

export default function RegisterDisplay() {
  const { data: live, status } = useLiveChannel("register");
  const preview = usePreview();
  const data = preview?.sample ? { ...SAMPLE, currency: live?.currency ?? "$" } : live;
  const appearance = preview?.appearance || live?.appearance;
  const churchName = preview ? preview.church_name : live?.church_name;
  const logoUrl = preview ? preview.church_logo_url : live?.church_logo_url;
  const cur = data?.current;
  const prev = data?.previous;
  const currency = data?.currency ?? "$";
  const prevSub = data?.comparison_service_date ? formatDate(data.comparison_service_date) : "Previous week";

  return (
    <div className="reg-screen" data-testid="register-display" style={appearanceVars(appearance)}>
      <DisplayBackground appearance={appearance} />
      <ChurchName name={churchName} logoUrl={logoUrl} appearance={appearance} place="top" />
      <header className="flex items-center gap-4">
        <div className="min-w-0">
          <p className="reg-label font-display font-bold ss-text truncate" data-testid="register-service-label">
            {cur?.service_label || "Service"}
          </p>
          <p className="reg-sub ss-muted" data-testid="register-service-date">{cur ? formatDate(cur.service_date) : ""}</p>
        </div>
        <WsStatus status={status} subtle className="ml-auto" />
      </header>
      {!cur ? (
        <div className="flex flex-1 items-center justify-center text-center" data-testid="register-empty-state">
          <p className="reg-label font-display ss-muted">Waiting for this week's numbers</p>
        </div>
      ) : (
        <div className="reg-grid">
          <Metric testid="attendance-this-week" label="Attendance" sub="This week" value={formatCount(cur.attendance)} current />
          <Metric testid="offering-this-week" label="Offering" sub="This week" value={formatMoney(cur.offering, currency)} current />
          <Metric testid="attendance-previous-week" label="Attendance" sub={prevSub} value={formatCount(prev?.attendance)} />
          <Metric testid="offering-previous-week" label="Offering" sub={prevSub} value={formatMoney(prev?.offering, currency)} />
        </div>
      )}
      <ChurchName name={churchName} logoUrl={logoUrl} appearance={appearance} place="bottom" />
    </div>
  );
}
