import { Panel } from "@/components/AdminShell";
import { formatCount, formatDate, formatMoney } from "@/lib/api";

export const ServiceHistory = ({ services, activeDate, onEdit, onActivate }) => (
  <Panel title="Recent services" testid="service-history">
    {services.length === 0 ? (
      <p className="text-sm text-slate-500">No services recorded yet.</p>
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="label-caps pb-3 pr-4">Date</th>
              <th className="label-caps pb-3 pr-4">Label</th>
              <th className="label-caps pb-3 pr-4 text-right">Attendance</th>
              <th className="label-caps pb-3 pr-4 text-right">Offering</th>
              <th className="pb-3" />
            </tr>
          </thead>
          <tbody>
            {services.map((s) => (
              <tr key={s.service_date} className="border-t border-[#222B3E]" data-testid={`history-row-${s.service_date}`}>
                <td className="py-3 pr-4 whitespace-nowrap">{formatDate(s.service_date)}</td>
                <td className="py-3 pr-4 text-slate-300">{s.service_label}</td>
                <td className="py-3 pr-4 text-right font-mono-ui">{formatCount(s.attendance) ?? "—"}</td>
                <td className="py-3 pr-4 text-right font-mono-ui">{formatMoney(s.offering, "") ?? "—"}</td>
                <td className="py-3 text-right whitespace-nowrap">
                  <button onClick={() => onEdit({ ...s })} data-testid={`history-edit-${s.service_date}`} className="mr-2 rounded-md px-2 py-1 text-xs font-semibold text-slate-300 hover:bg-[#1A202C]">Edit</button>
                  {activeDate === s.service_date ? (
                    <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-300" data-testid={`history-live-${s.service_date}`}>On screen</span>
                  ) : (
                    <button onClick={() => onActivate(s.service_date)} data-testid={`history-show-${s.service_date}`} className="rounded-md border border-[#2A3550] px-2 py-1 text-xs font-semibold text-amber-300 hover:border-amber-500/60">Show</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </Panel>
);
