import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Loader2, Send } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { errMsg, registerApi, todayLocal } from "@/lib/api";
import { CompareSelector, minusSeven } from "@/components/register/CompareSelector";
import { DatePicker } from "@/components/DatePicker";

const INT_RE = /^\d*$/;
const MONEY_RE = /^\d*(\.\d{0,2})?$/;

const Quick = ({ items, onAdd, prefix, testid }) => (
  <div className="mt-2 flex flex-wrap gap-2">
    {items.map((n) => (
      <button
        key={n}
        type="button"
        onClick={() => onAdd(n)}
        data-testid={`${testid}-plus-${n}`}
        className="rounded-md border border-[#2A3550] bg-[#0B0E14] px-3 py-1.5 font-mono-ui text-xs text-slate-300 transition-colors hover:border-amber-500/60 hover:text-amber-300"
      >
        +{prefix}{n}
      </button>
    ))}
  </div>
);

export const ServiceForm = ({ services, markedDates, live, editing, onSaved }) => {
  const [date, setDate] = useState(todayLocal());
  const [label, setLabel] = useState("Sunday Service");
  const [attendance, setAttendance] = useState("");
  const [offering, setOffering] = useState("");
  const [busy, setBusy] = useState(false);
  const [compareMode, setCompareMode] = useState("auto");
  const [compareDate, setCompareDate] = useState("");

  const existing = useMemo(() => services.find((s) => s.service_date === date), [services, date]);

  const fill = (s) => {
    setLabel(s.service_label || "");
    setAttendance(s.attendance == null ? "" : String(s.attendance));
    setOffering(s.offering == null ? "" : Number(s.offering).toFixed(2));
    setCompareMode(s.comparison_overridden ? "custom" : "auto");
    setCompareDate(s.comparison_overridden ? s.comparison_service_date : "");
  };

  useEffect(() => { if (editing) { setDate(editing.service_date); fill(editing); } }, [editing]);
  useEffect(() => {
    if (existing) fill(existing);
    else { setCompareMode("auto"); setCompareDate(""); }
  }, [existing?.service_date]); // eslint-disable-line react-hooks/exhaustive-deps

  const attOk = INT_RE.test(attendance);
  const offOk = MONEY_RE.test(offering);
  const compareOk = compareMode === "auto" || (compareDate && compareDate < date);
  const valid = date && attOk && offOk && compareOk;
  const effectiveCompare = compareMode === "custom" ? compareDate : minusSeven(date);

  const cur = live?.current;
  const isLive = cur && cur.service_date === date && String(cur.attendance ?? "") === attendance &&
    (cur.offering == null ? "" : Number(cur.offering).toFixed(2)) === (offering === "" ? "" : Number(offering).toFixed(2)) &&
    (cur.service_label || "") === label.trim() && live.comparison_service_date === effectiveCompare;

  const submit = async (e) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      await registerApi.put(`/register/services/${date}`, {
        service_label: label,
        attendance: attendance === "" ? null : parseInt(attendance, 10),
        offering: offering === "" ? null : parseFloat(offering),
        comparison_service_date: compareMode === "custom" ? compareDate : null,
        make_active: true,
      });
      toast.success("Published to /register");
      onSaved();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const addAtt = (n) => setAttendance(String((parseInt(attendance || "0", 10) || 0) + n));
  const addOff = (n) => setOffering(((parseFloat(offering || "0") || 0) + n).toFixed(2));

  return (
    <Panel
      title="Service entry"
      testid="service-form-panel"
      actions={
        <span data-testid="publish-state" className={`rounded-full px-3 py-1 text-xs font-semibold ${isLive ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"}`}>
          {isLive ? "Live on display" : "Not published"}
        </span>
      }
    >
      <form onSubmit={submit} className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="block">
            <span className="label-caps">Service date</span>
            <DatePicker value={date} onChange={setDate} testid="service-date" markedDates={markedDates} markLabel="Has a saved service" />
          </div>
          <label className="block">
            <span className="label-caps">Label</span>
            <Input value={label} maxLength={80} onChange={(e) => setLabel(e.target.value)} data-testid="service-label-input" className="mt-2 h-11 bg-[#0B0E14]" />
          </label>
        </div>
        <CompareSelector date={date} services={services} mode={compareMode} setMode={setCompareMode} compareDate={compareDate} setCompareDate={setCompareDate} />
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <span className="label-caps">Attendance</span>
            <Input
              inputMode="numeric" value={attendance} placeholder="0"
              onChange={(e) => setAttendance(e.target.value.trim())}
              data-testid="attendance-input"
              className={`mt-2 h-16 bg-[#0B0E14] font-display text-3xl font-bold ${attOk ? "" : "border-rose-500"}`}
            />
            {!attOk && <p data-testid="attendance-error" className="mt-1 text-xs text-rose-400">Whole numbers only.</p>}
            <Quick items={[1, 5, 10, 50]} onAdd={addAtt} prefix="" testid="attendance" />
          </div>
          <div>
            <span className="label-caps">Offering</span>
            <Input
              inputMode="decimal" value={offering} placeholder="0.00"
              onChange={(e) => setOffering(e.target.value.trim())}
              data-testid="offering-input"
              className={`mt-2 h-16 bg-[#0B0E14] font-display text-3xl font-bold ${offOk ? "" : "border-rose-500"}`}
            />
            {!offOk && <p data-testid="offering-error" className="mt-1 text-xs text-rose-400">Enter an amount like 1250.50.</p>}
            <Quick items={[10, 100, 500]} onAdd={addOff} prefix={live?.currency ?? "$"} testid="offering" />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={!valid || busy} data-testid="publish-register-btn" className="h-12 px-6 font-semibold">
            {busy ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />} Publish to display
          </Button>
          {existing && <span className="text-xs text-slate-500" data-testid="existing-record-note">Updating the existing record for this date.</span>}
        </div>
      </form>
    </Panel>
  );
};
