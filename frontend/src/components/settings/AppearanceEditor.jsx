import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, RotateCcw, Save } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { errMsg, settingsApi } from "@/lib/api";
import { ColorField, RangeField } from "@/components/settings/Fields";
import { ImageField } from "@/components/settings/ImageField";
import { DisplayPreview } from "@/components/settings/DisplayPreview";
import { ChurchNamePanel } from "@/components/settings/ChurchNamePanel";

const COLOR_LABELS = {
  bible: { text_color: "Verse text", accent_color: "Reference", muted_color: "Secondary text", panel_color: "Text panel" },
  register: { text_color: "Numbers", accent_color: "This-week labels", muted_color: "Secondary text", panel_color: "Tiles" },
};
const KEYS = ["background_color", "text_color", "accent_color", "muted_color", "panel_color", "panel_opacity",
  "image_blur", "image_dim", "image_motion", "motion_speed", "church_name_show", "church_name_position",
  "church_name_size", "church_name_color", "church_name_uppercase", "church_logo_show", "church_logo_size"];
const same = (a, b) => a && b && KEYS.every((k) => a[k] === b[k]);

const Toggle = ({ active, onClick, children, testid }) => (
  <button type="button" onClick={onClick} data-testid={testid}
    className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${active ? "bg-amber-500 text-[#090B10]" : "border border-[#2A3550] text-slate-300 hover:border-amber-500/60"}`}>
    {children}
  </button>
);

export const AppearanceEditor = ({ display }) => {
  const [saved, setSaved] = useState(null);
  const [form, setForm] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sample, setSample] = useState(true);
  const [orientation, setOrientation] = useState("landscape");
  const [name, setName] = useState("");
  const [savedName, setSavedName] = useState("");
  const [logoUrl, setLogoUrl] = useState(null);
  const labels = COLOR_LABELS[display];
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const load = useCallback(async () => {
    try {
      const { data } = await settingsApi.get(`/appearance/${display}`);
      setSaved(data.appearance); setForm(data.appearance); setDefaults(data.defaults);
      setName(data.church_name); setSavedName(data.church_name); setLogoUrl(data.church_logo_url);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, [display]);
  useEffect(() => { load(); }, [load]);

  if (!form) return <p className="text-sm text-slate-500">Loading…</p>;
  const dirty = !same(form, saved) || name.trim() !== savedName;
  const hasImage = !!form.image_url;

  const save = async () => {
    setBusy(true);
    try {
      if (name.trim() !== savedName) {
        const { data: cn } = await settingsApi.put("/appearance/church-name", { church_name: name });
        setName(cn.church_name); setSavedName(cn.church_name);
      }
      const body = Object.fromEntries(KEYS.map((k) => [k, form[k]]));
      const { data } = await settingsApi.put(`/appearance/${display}`, body);
      setSaved(data.appearance); setForm(data.appearance);
      toast.success(`/${display} updated`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const onImage = (data) => { const a = data.appearance; setSaved((s) => ({ ...s, image_url: a.image_url })); setForm((f) => ({ ...f, image_url: a.image_url })); };

  return (
    <div className="grid gap-8 lg:grid-cols-12" data-testid={`appearance-editor-${display}`}>
      <div className="space-y-6 lg:col-span-5">
        <ChurchNamePanel name={name} setName={setName} logoUrl={logoUrl} setLogoUrl={setLogoUrl} form={form} set={set} />
        <Panel title="Colors" testid="colors-panel">
          <div className="space-y-3">
            <ColorField label="Background" value={form.background_color} onChange={set("background_color")} testid="color-background" />
            {Object.entries(labels).map(([k, l]) => (
              <ColorField key={k} label={l} value={form[k]} onChange={set(k)} testid={`color-${k.replace("_color", "")}`} />
            ))}
            <RangeField label={display === "bible" ? "Text panel opacity" : "Tile opacity"} value={form.panel_opacity} onChange={set("panel_opacity")} min={0} max={100} unit="%" testid="panel-opacity" />
          </div>
        </Panel>
        <Panel title="Background image" testid="background-panel">
          <div className="space-y-5">
            <ImageField endpoint={`/appearance/${display}/image`} imageUrl={form.image_url} onChanged={onImage} />
            <RangeField label="Blur" value={form.image_blur} onChange={set("image_blur")} min={0} max={40} unit="px" testid="image-blur" disabled={!hasImage} />
            <RangeField label="Darken / tint" value={form.image_dim} onChange={set("image_dim")} min={0} max={95} unit="%" testid="image-dim" disabled={!hasImage} />
            <div className={hasImage ? "" : "opacity-40"}>
              <p className="mb-2 text-sm text-slate-300">Motion</p>
              <div className="flex gap-2">
                <Toggle active={form.image_motion === "none"} onClick={() => set("image_motion")("none")} testid="motion-none-btn">Still</Toggle>
                <Toggle active={form.image_motion === "parallax"} onClick={() => set("image_motion")("parallax")} testid="motion-parallax-btn">Parallax drift</Toggle>
              </div>
            </div>
            <RangeField label="Motion speed" value={form.motion_speed} onChange={set("motion_speed")} min={1} max={10} testid="motion-speed" disabled={!hasImage || form.image_motion !== "parallax"} />
          </div>
        </Panel>
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={save} disabled={!dirty || busy} data-testid="appearance-save-btn" className="h-11 px-5 font-semibold">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save &amp; apply to /{display}
          </Button>
          <Button variant="ghost" onClick={() => setForm({ ...defaults, image_url: form.image_url })} data-testid="appearance-reset-btn">
            <RotateCcw size={14} /> Reset to defaults
          </Button>
          <span data-testid="appearance-dirty-state" className={`text-xs ${dirty ? "text-amber-300" : "text-slate-500"}`}>
            {dirty ? "Unsaved changes (preview only)" : "Matches the live display"}
          </span>
        </div>
      </div>
      <div className="lg:col-span-7 lg:sticky lg:top-20 lg:self-start">
        <Panel
          title="Preview"
          testid="preview-panel"
          actions={
            <>
              <label className="flex items-center gap-2 text-xs text-slate-400">
                <Switch checked={sample} onCheckedChange={setSample} data-testid="preview-sample-switch" /> Sample content
              </label>
              <Toggle active={orientation === "landscape"} onClick={() => setOrientation("landscape")} testid="preview-landscape-btn">Landscape</Toggle>
              <Toggle active={orientation === "portrait"} onClick={() => setOrientation("portrait")} testid="preview-portrait-btn">Portrait</Toggle>
            </>
          }
        >
          <DisplayPreview path={`/${display}`} appearance={form} churchName={name} logoUrl={logoUrl} sample={sample} orientation={orientation} />
        </Panel>
      </div>
    </div>
  );
};
