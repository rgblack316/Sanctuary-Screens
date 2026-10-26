import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Download, FileUp, Loader2, Trash2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { bibleApi, errMsg } from "@/lib/api";

const Report = ({ r }) => (
  <div data-testid="songs-report" className={`rounded-lg border p-4 text-sm ${r.ok ? "border-emerald-500/40 bg-emerald-500/5" : "border-rose-500/40 bg-rose-500/5"}`}>
    <p className={`font-semibold ${r.ok ? "text-emerald-300" : "text-rose-300"}`} data-testid="songs-report-status">
      {r.ok ? "Validation passed" : `Validation failed – ${r.error_count} problem(s)`}
    </p>
    {r.ok && (
      <>
        <p className="mt-1 text-slate-400">{r.row_count.toLocaleString()} songs{r.duplicates ? ` · ${r.duplicates} duplicate row(s) ignored` : ""}</p>
        <ul className="mt-2 space-y-0.5 text-xs text-slate-300">
          {Object.entries(r.songbooks).map(([name, n]) => (
            <li key={name}>{name}: {n.toLocaleString()} songs{r.existing?.[name] ? <span className="text-amber-300"> · already has {r.existing[name].toLocaleString()}</span> : null}</li>
          ))}
        </ul>
      </>
    )}
    {r.errors.length > 0 && (
      <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto font-mono-ui text-xs text-rose-200">
        {r.errors.map((e, i) => <li key={i}>{e.row ? `Row ${e.row}: ` : ""}{e.error}</li>)}
      </ul>
    )}
  </div>
);

export const SongbookManager = ({ onChanged }) => {
  const fileRef = useRef(null);
  const [books, setBooks] = useState([]);
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [replace, setReplace] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadBooks = useCallback(async () => {
    try {
      setBooks((await bibleApi.get("/bible/songs/books")).data.songbooks);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, []);
  useEffect(() => { loadBooks(); }, [loadBooks]);

  const send = async (path, f, extra = {}) => {
    const fd = new FormData();
    fd.append("file", f);
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return (await bibleApi.post(path, fd)).data;
  };

  const pick = async (f) => {
    setFile(f); setReport(null);
    if (!f) return;
    setBusy(true);
    try {
      setReport(await send("/bible/songs/validate", f));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const doImport = async () => {
    setBusy(true);
    try {
      const res = await send("/bible/songs/import", file, { replace: String(replace) });
      if (!res.ok) return setReport(res.report);
      toast.success(`${res.imported.toLocaleString()} songs imported`);
      setFile(null); setReport(null);
      if (fileRef.current) fileRef.current.value = "";
      loadBooks(); onChanged();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (name) => {
    if (!window.confirm(`Remove all songs from “${name}”? The songbook name stays in the hymnal list.`)) return;
    try {
      await bibleApi.delete(`/bible/songs/books/${encodeURIComponent(name)}`, { params: { confirm: true } });
      loadBooks(); onChanged();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const sample = async () => {
    const { data } = await bibleApi.get("/bible/songs/sample.csv", { responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(data);
    a.download = "songbook-sample.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <Panel title="Hymnal songbooks" testid="songbook-manager">
      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <p className="label-caps mb-3">Imported songbooks</p>
          {books.length === 0 ? (
            <p className="text-sm text-slate-500" data-testid="songbooks-empty">No songbooks imported yet. Import a CSV to look songs up by page, number or title in the hymn shortcut.</p>
          ) : (
            <ul className="max-h-64 space-y-2 overflow-y-auto pr-1" data-testid="songbook-list">
              {books.map((b) => (
                <li key={b.name} className="flex items-center gap-3 rounded-lg border border-[#222B3E] bg-[#0B0E14] px-4 py-3" data-testid={`songbook-${b.name}`}>
                  <span className="min-w-0 flex-1 truncate font-display font-bold">{b.name}</span>
                  <span className="text-xs text-slate-500">{b.count.toLocaleString()} songs</span>
                  <button type="button" onClick={() => remove(b.name)} aria-label={`Remove ${b.name}`} data-testid={`songbook-delete-${b.name}`} className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-rose-300"><Trash2 size={14} /></button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="space-y-3 lg:col-span-5">
          <p className="label-caps">Import CSV</p>
          <p className="text-xs text-slate-400">
            Columns: <code className="font-mono-ui text-amber-300">songbook, title, page</code>, optional <code className="font-mono-ui text-amber-300">number</code>. Several songs may share a page. UTF-8.
          </p>
          <button type="button" onClick={sample} className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:underline" data-testid="songs-sample-btn"><Download size={12} /> Download a sample file</button>
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-[#2A3550] bg-[#0B0E14] p-4 text-sm text-slate-300 hover:border-amber-500/60" data-testid="songs-dropzone">
            <FileUp size={18} className="text-amber-400" />
            <span className="truncate">{file ? file.name : "Choose a songbook CSV…"}</span>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => pick(e.target.files?.[0] || null)} data-testid="songs-file-input" />
          </label>
          {busy && !report && <p className="flex items-center gap-2 text-xs text-slate-400"><Loader2 size={12} className="animate-spin" /> Checking…</p>}
          {report && <Report r={report} />}
          {report?.ok && (
            <>
              <div className="space-y-1.5 text-sm text-slate-300">
                <label className="flex cursor-pointer items-center gap-2"><input type="radio" checked={replace} onChange={() => setReplace(true)} data-testid="songs-mode-replace" /> Replace these songbooks with the file</label>
                <label className="flex cursor-pointer items-center gap-2"><input type="radio" checked={!replace} onChange={() => setReplace(false)} data-testid="songs-mode-add" /> Add to what is already there</label>
              </div>
              <Button onClick={doImport} disabled={busy} data-testid="songs-import-btn">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <FileUp size={14} />} Import {report.row_count.toLocaleString()} songs
              </Button>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
};
