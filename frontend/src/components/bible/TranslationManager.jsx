import { useRef, useState } from "react";
import { toast } from "sonner";
import { FileUp, Loader2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { bibleApi, errMsg } from "@/lib/api";
import { TranslationTable } from "@/components/bible/TranslationTable";

const Report = ({ r }) => (
  <div data-testid="import-report" className={`rounded-lg border p-4 text-sm ${r.ok ? "border-emerald-500/40 bg-emerald-500/5" : "border-rose-500/40 bg-rose-500/5"}`}>
    <p className={`font-semibold ${r.ok ? "text-emerald-300" : "text-rose-300"}`} data-testid="import-report-status">
      {r.ok ? "Validation passed" : `Validation failed – ${r.error_count} problem(s)`}
    </p>
    <p className="mt-1 text-slate-400">
      {r.translation_code || "?"} · {r.row_count.toLocaleString()} verses · {r.book_count} books · {r.chapter_count} chapters
      {r.already_installed && <span className="text-amber-300"> · already installed</span>}
    </p>
    {r.errors.length > 0 && (
      <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto font-mono-ui text-xs text-rose-200">
        {r.errors.map((e, i) => <li key={i}>{e.row ? `Row ${e.row}: ` : ""}{e.error}</li>)}
      </ul>
    )}
  </div>
);

export const TranslationManager = ({ translations, defaultCode, reload }) => {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [name, setName] = useState("");
  const [replace, setReplace] = useState(false);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);

  const send = async (path, f, extra = {}) => {
    const fd = new FormData();
    fd.append("file", f);
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return (await bibleApi.post(path, fd)).data;
  };

  const pick = async (f) => {
    setFile(f);
    setReport(null);
    if (!f) return;
    setBusy(true);
    try {
      setReport(await send("/bible/translations/validate", f));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const doImport = async () => {
    setBusy(true);
    try {
      const res = await send("/bible/translations/import", file, { translation_name: name, replace: String(replace) });
      setReport(res.report);
      if (res.ok) {
        toast.success(`${res.translation.translation_code} imported (${res.translation.verse_count.toLocaleString()} verses)`);
        setFile(null); setName(""); setReplace(false); setReport(null);
        if (fileRef.current) fileRef.current.value = "";
        reload();
      }
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Translations" testid="translation-manager">
      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <TranslationTable translations={translations} defaultCode={defaultCode} reload={reload} />
        </div>
        <div className="space-y-3 lg:col-span-5">
          <p className="label-caps">Import CSV</p>
          <p className="text-xs text-slate-400">
            Required columns: <code className="font-mono-ui text-amber-300">translation, book, chapter, verse, text</code>. Optional: book_abbrev, testament, reference. One translation per file, UTF-8.
          </p>
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-[#2A3550] bg-[#0B0E14] p-4 text-sm text-slate-300 hover:border-amber-500/60" data-testid="import-dropzone">
            <FileUp size={18} className="text-amber-400" />
            <span className="truncate">{file ? file.name : "Choose a translation CSV…"}</span>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => pick(e.target.files?.[0] || null)} data-testid="import-file-input" />
          </label>
          {busy && !report && <p className="flex items-center gap-2 text-xs text-slate-400"><Loader2 size={12} className="animate-spin" /> Validating…</p>}
          {report && <Report r={report} />}
          {report?.ok && (
            <>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={`Display name (e.g. ${report.translation_code} full name)`} data-testid="import-name-input" className="bg-[#0B0E14]" />
              {report.already_installed && (
                <label className="flex items-center gap-2 text-sm text-slate-300">
                  <Checkbox checked={replace} onCheckedChange={(v) => setReplace(!!v)} data-testid="import-replace-checkbox" /> Replace existing {report.translation_code}
                </label>
              )}
              <Button onClick={doImport} disabled={busy || (report.already_installed && !replace)} data-testid="import-commit-btn">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <FileUp size={14} />} Import {report.row_count.toLocaleString()} verses
              </Button>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
};
