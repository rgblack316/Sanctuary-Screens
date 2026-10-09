import { Panel } from "@/components/AdminShell";
import { ColorField, RangeField } from "@/components/settings/Fields";

export const ReferencePanel = ({ form, set }) => (
  <Panel title="Scripture text & reference" testid="reference-panel">
    <div className="space-y-5">
      <RangeField label="Verse text size" value={form.verse_size} onChange={set("verse_size")} min={1} max={10} testid="verse-size" />
      <p className="-mt-3 text-xs text-slate-500">Larger helps screens viewed from far away. Very long verses still shrink to fit the screen.</p>
      <p className="text-xs text-slate-500">The reference shown above each verse, e.g. ROMANS 10:13.</p>
      <ColorField label="Reference color" value={form.accent_color} onChange={set("accent_color")} testid="color-reference" />
      <RangeField label="Reference size" value={form.reference_size} onChange={set("reference_size")} min={1} max={10} testid="reference-size" />
    </div>
  </Panel>
);
