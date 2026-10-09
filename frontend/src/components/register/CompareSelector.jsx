import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCount, formatDate } from "@/lib/api";

export const minusSeven = (date) =>
  date ? new Date(new Date(`${date}T12:00:00`).getTime() - 7 * 864e5).toLocaleDateString("en-CA") : "";

const Choice = ({ active, onClick, children, testid }) => (
  <button
    type="button" onClick={onClick} data-testid={testid}
    className={`rounded-md px-3 py-2 text-xs font-semibold transition-colors ${active ? "bg-amber-500 text-[#090B10]" : "border border-[#2A3550] text-slate-300 hover:border-amber-500/60"}`}
  >
    {children}
  </button>
);

// Choose which earlier service the "previous" values come from.
export const CompareSelector = ({ date, services, mode, setMode, compareDate, setCompareDate }) => {
  const earlier = services.filter((s) => s.service_date < date);
  return (
    <div data-testid="compare-selector">
      <span className="label-caps">Compare with</span>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Choice active={mode === "auto"} onClick={() => setMode("auto")} testid="compare-auto-btn">
          7 days earlier · {date ? formatDate(minusSeven(date)) : "—"}
        </Choice>
        <Choice active={mode === "custom"} onClick={() => setMode("custom")} testid="compare-custom-btn">
          Another service date
        </Choice>
        {mode === "custom" && (
          <Select value={compareDate || undefined} onValueChange={setCompareDate} disabled={earlier.length === 0}>
            <SelectTrigger data-testid="compare-date-select" className="h-9 w-72 bg-[#0B0E14]">
              <SelectValue placeholder={earlier.length ? "Choose an earlier service" : "No earlier services recorded"} />
            </SelectTrigger>
            <SelectContent>
              {earlier.map((s) => (
                <SelectItem key={s.service_date} value={s.service_date} data-testid={`compare-date-option-${s.service_date}`}>
                  {formatDate(s.service_date)} · {s.service_label || "Service"} · {formatCount(s.attendance) ?? "—"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {mode === "auto" ? "Shows N/A if no service was recorded exactly 7 days earlier." : "Use this when last week's service was cancelled or moved."}
      </p>
    </div>
  );
};
