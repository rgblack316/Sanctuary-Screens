import { useState } from "react";
import { CalendarDays } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { todayLocal } from "@/lib/api";

const toDate = (iso) => (iso ? new Date(`${iso}T12:00:00`) : undefined);
const toIso = (d) => d.toLocaleDateString("en-CA");

// Typed date input with a mouse-friendly calendar popover beside it.
export const DatePicker = ({ value, onChange, testid, markedDates = [], markLabel }) => {
  const [open, setOpen] = useState(false);
  const marked = markedDates.map(toDate);
  return (
    <div className="mt-2 flex gap-2">
      <Input type="date" value={value} onChange={(e) => onChange(e.target.value)} data-testid={`${testid}-input`} className="h-10 flex-1 bg-[#0B0E14]" />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="Open calendar"
            data-testid={`${testid}-calendar-btn`}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-[#2A3550] bg-[#0B0E14] text-slate-300 transition-colors hover:border-amber-500/60 hover:text-amber-300"
          >
            <CalendarDays size={16} />
          </button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-auto border-[#222B3E] bg-[#121620] p-0" data-testid={`${testid}-calendar`}>
          <Calendar
            mode="single"
            selected={toDate(value)}
            defaultMonth={toDate(value)}
            onSelect={(d) => { if (d) { onChange(toIso(d)); setOpen(false); } }}
            modifiers={{ recorded: marked }}
            modifiersClassNames={{ recorded: "ss-recorded" }}
            initialFocus
          />
          <div className="flex items-center gap-3 border-t border-[#222B3E] p-2">
            {markLabel && (
              <span className="flex items-center gap-1.5 pl-1 text-xs text-slate-400" data-testid={`${testid}-legend`}>
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> {markLabel}
              </span>
            )}
            <button
              type="button"
              onClick={() => { onChange(todayLocal()); setOpen(false); }}
              data-testid={`${testid}-today-btn`}
              className="ml-auto rounded-md px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-[#1A202C]"
            >
              Today
            </button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
};
