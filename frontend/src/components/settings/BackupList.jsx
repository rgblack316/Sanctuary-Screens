import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArchiveRestore, DatabaseBackup, Download, Loader2, Trash2, Upload } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { errMsg, settingsApi } from "@/lib/api";

const mb = (n) => `${(n / 1048576).toFixed(1)} MB`;
const when = (name) => {
  const m = name.match(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/);
  return m ? new Date(+m[1], m[2] - 1, +m[3], +m[4], +m[5]).toLocaleString() : name;
};

export const BackupList = () => {
  const [list, setList] = useState({ backups: [], last_run: null });
  const [busy, setBusy] = useState(null);
  const [restore, setRestore] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(() => settingsApi.get("/backup/list").then((r) => setList(r.data)).catch((e) => toast.error(errMsg(e))), []);
  useEffect(() => { load(); }, [load]);

  const run = async () => {
    setBusy("run");
    try {
      const { data } = await settingsApi.post("/backup/run");
      if (data.email_error) toast.warning(`Backup saved, but the email failed: ${data.email_error}`);
      else toast.success(data.emailed ? "Backup saved and emailed" : "Backup saved on the NUC");
      load();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };

  const download = async (name) => {
    const { data } = await settingsApi.get(`/backup/download/${name}`, { responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(data); a.download = name; a.click();
    URL.revokeObjectURL(a.href);
  };

  const remove = async (name) => {
    try { await settingsApi.delete(`/backup/${name}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const doRestore = async () => {
    setBusy("restore");
    try {
      if (restore.file) {
        const fd = new FormData(); fd.append("file", restore.file);
        await settingsApi.post("/backup/restore-upload", fd, { params: { confirm: true } });
      } else {
        await settingsApi.post(`/backup/restore/${restore.name}`, null, { params: { confirm: true } });
      }
      toast.success("Backup restored. Displays have been refreshed.");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); setRestore(null); if (fileRef.current) fileRef.current.value = ""; }
  };

  const last = list.last_run;
  return (
    <Panel
      title="Backups on this NUC"
      testid="backup-list-panel"
      actions={
        <Button size="sm" onClick={run} disabled={busy === "run"} data-testid="backup-now-btn">
          {busy === "run" ? <Loader2 size={14} className="animate-spin" /> : <DatabaseBackup size={14} />} Back up now
        </Button>
      }
    >
      {last && (
        <p className="mb-4 text-xs text-slate-400" data-testid="backup-last-run">
          Last backup: {new Date(last.at).toLocaleString()} ({last.trigger}){last.emailed && " · emailed"}
          {last.email_error && <span className="text-rose-300"> · email failed: {last.email_error}</span>}
        </p>
      )}
      <ul className="space-y-2" data-testid="backup-list">
        {list.backups.length === 0 && <li className="text-sm text-slate-500" data-testid="backup-empty">No backups yet.</li>}
        {list.backups.map((b) => (
          <li key={b.name} className="flex items-center gap-3 rounded-lg border border-[#222B3E] bg-[#0B0E14] p-3" data-testid={`backup-row-${b.name}`}>
            <span className="flex-1 text-sm">{when(b.name)} <span className="text-xs text-slate-500">· {mb(b.size)}</span></span>
            <button onClick={() => download(b.name)} title="Download" data-testid={`backup-download-${b.name}`} className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-amber-300"><Download size={14} /></button>
            <button onClick={() => setRestore({ name: b.name })} title="Restore" data-testid={`backup-restore-${b.name}`} className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-amber-300"><ArchiveRestore size={14} /></button>
            <button onClick={() => remove(b.name)} title="Delete" data-testid={`backup-delete-${b.name}`} className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-rose-300"><Trash2 size={14} /></button>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-3">
        <Button size="sm" variant="secondary" onClick={() => fileRef.current?.click()} data-testid="backup-upload-restore-btn"><Upload size={14} /> Restore from a file…</Button>
        <span className="text-xs text-slate-500">Stored in the <code className="font-mono-ui">backups</code> folder of the install.</span>
        <input ref={fileRef} type="file" accept=".gz" className="hidden" data-testid="backup-upload-input"
          onChange={(e) => e.target.files?.[0] && setRestore({ file: e.target.files[0], name: e.target.files[0].name })} />
      </div>
      <AlertDialog open={!!restore} onOpenChange={(o) => !o && setRestore(null)}>
        <AlertDialogContent className="border-[#222B3E] bg-[#121620]" data-testid="restore-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display">Restore {restore?.file ? restore.name : when(restore?.name || "")}?</AlertDialogTitle>
            <AlertDialogDescription>
              This replaces all register records, translations, prepared scripture, display settings, looks and images with the backup. The admin PIN is not changed. Consider clicking "Back up now" first.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="restore-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doRestore} disabled={busy === "restore"} data-testid="restore-confirm" className="bg-rose-600 hover:bg-rose-500">Restore</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Panel>
  );
};
