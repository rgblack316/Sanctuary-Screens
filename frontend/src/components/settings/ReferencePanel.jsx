import { Panel } from "@/components/AdminShell";
import { ColorField, RangeField } from "@/components/settings/Fields";

export const ReferencePanel = ({ form, set }) => (
  <Panel title="Scripture reference" testid="reference-panel">
    <div className="space-y-5">
      <p className="text-xs text-slate-500">The reference shown above each verse, e.g. ROMANS 10:13.</p>
      <ColorField label="Reference color" value={form.accent_color} onChange={set("accent_color")} testid="color-reference" />
      <RangeField label="Reference size" value={form.reference_size} onChange={set("reference_size")} min={1} max={10} testid="reference-size" />
    </div>
  </Panel>
);
