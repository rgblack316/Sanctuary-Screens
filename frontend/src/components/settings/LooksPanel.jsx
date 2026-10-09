import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { assetUrl, errMsg, settingsApi } from "@/lib/api";

const Swatches = ({ s, imageUrl }) => (
  <div className="relative h-10 w-16 shrink-0 overflow-hidden rounded-md border border-[#2A3550]" style={{ background: s.background_color }}>
    {imageUrl && <img src={assetUrl(imageUrl)} alt="" className="absolute inset-0 h-full w-full object-cover opacity-70" />}
    <span className="absolute bottom-1 left-1 h-2.5 w-2.5 rounded-full ring-1 ring-black/40" style={{ background: s.text_color }} />
    <span className="absolute bottom-1 left-4 h-2.5 w-2.5 rounded-full ring-1 ring-black/40" style={{ background: s.accent_color }} />
  </div>
);

// Saved looks for one display: save current settings (incl. unsaved edits) by name, apply, update, delete.
export const LooksPanel = ({ display, settings, onApplied }) => {
  const [looks, setLooks] = useState([]);
  const [active, setActive] = useState(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(null);
  const [toDelete, setToDelete] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await settingsApi.get(`/appearance/${display}/looks`);
      setLooks(data.looks); setActive(data.active_look_id);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, [display]);
  useEffect(() => { load(); }, [load]);

  const run = async (key, fn, msg) => {
    setBusy(key);
    try { await fn(); if (msg) toast.success(msg); await load(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };

  const save = () => name.trim() && run("new", async () => {
    await settingsApi.post(`/appearance/${display}/looks`, { name: name.trim(), settings });
    setName("");
  }, `Look "${name.trim()}" saved`);

  const update = (l) => run(l.id, () => settingsApi.put(`/appearance/${display}/looks/${l.id}`, { name: l.name, settings }),
    `"${l.name}" updated with the current settings`);

  const apply = (l) => run(l.id, async () => {
    const { data } = await settingsApi.post(`/appearance/${display}/looks/${l.id}/apply`);
    onApplied(data);
  }, `"${l.name}" is now on /${display}`);

  const remove = () => run(toDelete.id, () => settingsApi.delete(`/appearance/${display}/looks/${toDelete.id}`),
    `"${toDelete.name}" deleted`).then(() => setToDelete(null));

  return (
    <Panel title="Saved looks" testid="looks-panel">
      <div className="flex gap-2">
        <Input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()}
          placeholder="Name this look, e.g. Christmas" data-testid="look-name-input" className="h-10 bg-[#0B0E14]" />
        <Button onClick={save} disabled={!name.trim() || busy === "new"} data-testid="look-save-btn" className="h-10">
          {busy === "new" ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Save look
        </Button>
      </div>
      <p className="mt-2 text-xs text-slate-500">Saves everything on this tab (including unsaved edits) and the current background image. The church name and logo are shared and not part of a look.</p>
      <ul className="mt-4 space-y-2" data-testid="looks-list">
        {looks.length === 0 && <li className="text-sm text-slate-500" data-testid="looks-empty">No saved looks yet.</li>}
        {looks.map((l) => (
          <li key={l.id} className="flex items-center gap-3 rounded-lg border border-[#222B3E] bg-[#0B0E14] p-2.5" data-testid={`look-row-${l.name}`}>
            <Swatches s={l.settings} imageUrl={l.image_url} />
            <span className="min-w-0 flex-1 truncate font-semibold">{l.name}</span>
            {active === l.id && <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-300" data-testid={`look-active-${l.name}`}>On screen</span>}
            <Button size="sm" onClick={() => apply(l)} disabled={busy === l.id} data-testid={`look-apply-${l.name}`}>
              {busy === l.id ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Apply
            </Button>
            <button onClick={() => update(l)} title="Overwrite with the current settings" data-testid={`look-update-${l.name}`}
              className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-amber-300"><RefreshCw size={14} /></button>
            <button onClick={() => setToDelete(l)} title="Delete look" data-testid={`look-delete-${l.name}`}
              className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-rose-300"><Trash2 size={14} /></button>
          </li>
        ))}
      </ul>
      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent className="border-[#222B3E] bg-[#121620]" data-testid="delete-look-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display">Delete "{toDelete?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>The display keeps its current appearance; only the saved look is removed.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-look-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={remove} data-testid="delete-look-confirm" className="bg-rose-600 hover:bg-rose-500">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Panel>
  );
};
