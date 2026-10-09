import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ColorField, RangeField } from "@/components/settings/Fields";

const POSITIONS = ["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"];

export const ChurchNamePanel = ({ name, setName, form, set }) => (
  <Panel title="Church name" testid="church-name-panel">
    <div className="space-y-5">
      <label className="block">
        <span className="label-caps">Name (shared by both displays)</span>
        <Input
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter your church name"
          data-testid="church-name-input"
          className="mt-2 h-11 bg-[#0B0E14]"
        />
      </label>
      <label className="flex items-center justify-between text-sm text-slate-300">
        Show on this display
        <Switch checked={form.church_name_show} onCheckedChange={set("church_name_show")} data-testid="church-name-show-switch" />
      </label>
      <div className={form.church_name_show ? "space-y-5" : "space-y-5 opacity-40 pointer-events-none"}>
        <div>
          <p className="mb-2 text-sm text-slate-300">Position</p>
          <div className="grid w-full max-w-xs grid-cols-3 gap-2" data-testid="church-name-position-grid">
            {POSITIONS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => set("church_name_position")(p)}
                data-testid={`church-name-pos-${p}`}
                className={`rounded-md px-2 py-1.5 text-xs font-semibold capitalize transition-colors ${form.church_name_position === p ? "bg-amber-500 text-[#090B10]" : "border border-[#2A3550] text-slate-300 hover:border-amber-500/60"}`}
              >
                {p.replace("-", " ")}
              </button>
            ))}
          </div>
        </div>
        <RangeField label="Size" value={form.church_name_size} onChange={set("church_name_size")} min={1} max={10} testid="church-name-size" />
        <ColorField label="Name color" value={form.church_name_color} onChange={set("church_name_color")} testid="color-church-name" />
        <label className="flex items-center justify-between text-sm text-slate-300">
          All capitals
          <Switch checked={form.church_name_uppercase} onCheckedChange={set("church_name_uppercase")} data-testid="church-name-uppercase-switch" />
        </label>
      </div>
    </div>
  </Panel>
);
