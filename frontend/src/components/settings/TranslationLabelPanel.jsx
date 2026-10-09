import { Panel } from "@/components/AdminShell";
import { Switch } from "@/components/ui/switch";

const POSITIONS = ["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"];

export const TranslationLabelPanel = ({ form, set }) => (
  <Panel title="Translation label" testid="translation-label-panel">
    <div className="space-y-5">
      <label className="flex items-center justify-between text-sm text-slate-300">
        Show translation (e.g. KJV) on verse slides
        <Switch checked={form.translation_show} onCheckedChange={set("translation_show")} data-testid="translation-show-switch" />
      </label>
      <div className={form.translation_show ? "" : "opacity-40 pointer-events-none"}>
        <p className="mb-2 text-sm text-slate-300">Position</p>
        <div className="grid w-full max-w-xs grid-cols-3 gap-2" data-testid="translation-position-grid">
          {POSITIONS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => set("translation_position")(p)}
              data-testid={`translation-pos-${p}`}
              className={`rounded-md px-2 py-1.5 text-xs font-semibold capitalize transition-colors ${form.translation_position === p ? "bg-amber-500 text-[#090B10]" : "border border-[#2A3550] text-slate-300 hover:border-amber-500/60"}`}
            >
              {p.replace("-", " ")}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">Uses the secondary text color. The slide counter always sits bottom right.</p>
      </div>
    </div>
  </Panel>
);
