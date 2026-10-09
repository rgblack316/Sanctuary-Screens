import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Loader2, MonitorUp, Search } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errMsg } from "@/lib/api";
import { lookupDraft, manualDraft, publishDraft } from "@/lib/bible";
import { TranslationSelect } from "@/components/bible/TranslationSelect";
import { SlidePreview } from "@/components/bible/SlidePreview";

export const Composer = ({ translations, defaultCode, draft, setDraft }) => {
  const [tab, setTab] = useState("lookup");
  const [reference, setReference] = useState("");
  const [code, setCode] = useState(null);
  const [lookupError, setLookupError] = useState("");
  const [manualLabel, setManualLabel] = useState("");
  const [manualText, setManualText] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!code && defaultCode) setCode(defaultCode); }, [defaultCode, code]);
  useEffect(() => {
    if (draft?.source_type === "local_lookup") { setReference(draft.reference_input || draft.normalized_reference); setCode(draft.translation_code); }
  }, [draft]);

  const lookup = async (e) => {
    e?.preventDefault();
    if (!reference.trim() || !code) return;
    setBusy(true);
    setLookupError("");
    try {
      setDraft(await lookupDraft(reference.trim(), code));
    } catch (err) {
      setLookupError(errMsg(err, "Lookup failed"));
    } finally {
      setBusy(false);
    }
  };

  const toManual = () => {
    setManualLabel(reference.trim());
    setTab("manual");
  };

  const buildManual = () => {
    if (!manualLabel.trim() || !manualText.trim()) return toast.error("Enter a reference label and the text.");
    setDraft(manualDraft(manualLabel, manualText));
  };

  const publish = async () => {
    setBusy(true);
    try {
      await publishDraft(draft, 0);
      toast.success(`${draft.normalized_reference} is on screen`);
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Compose" testid="composer-panel">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-5 bg-[#0B0E14]">
          <TabsTrigger value="lookup" data-testid="composer-tab-lookup">Reference lookup</TabsTrigger>
          <TabsTrigger value="manual" data-testid="composer-tab-manual">Manual text</TabsTrigger>
        </TabsList>
        <TabsContent value="lookup">
          <form onSubmit={lookup} className="flex flex-col gap-3 sm:flex-row">
            <Input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="e.g. Romans 6:23-25 or John 3:16-4:2"
              data-testid="bible-lookup-input"
              className="h-11 flex-1 bg-[#0B0E14] text-base"
            />
            <TranslationSelect translations={translations} value={code} onChange={setCode} testid="lookup-translation-select" className="sm:w-52" />
            <Button type="submit" disabled={busy || !reference.trim() || !code} data-testid="bible-lookup-btn" className="h-11">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />} Look up
            </Button>
          </form>
          {lookupError && (
            <div data-testid="lookup-error" className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">
              <AlertTriangle size={16} /> <span className="flex-1">{lookupError}</span>
              <Button size="sm" variant="outline" onClick={toManual} data-testid="lookup-to-manual-btn">Enter text manually</Button>
            </div>
          )}
        </TabsContent>
        <TabsContent value="manual" className="space-y-3">
          <Input value={manualLabel} onChange={(e) => setManualLabel(e.target.value)} placeholder="Reference label shown on screen" maxLength={120} data-testid="manual-label-input" className="h-11 bg-[#0B0E14]" />
          <Textarea value={manualText} onChange={(e) => setManualText(e.target.value)} rows={6} placeholder="Paste or type the text. Leave a blank line between slides." data-testid="manual-text-input" className="bg-[#0B0E14]" />
          <Button variant="secondary" onClick={buildManual} data-testid="manual-build-btn">Build slides</Button>
        </TabsContent>
      </Tabs>

      {draft && (
        <div className="mt-6 border-t border-[#222B3E] pt-5" data-testid="draft-preview">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <p className="font-display text-lg font-bold" data-testid="draft-reference">{draft.normalized_reference}</p>
            <span className="text-xs text-slate-500" data-testid="draft-slide-count">
              {draft.verses.length} slide{draft.verses.length === 1 ? "" : "s"} · {draft.source_type === "manual" ? "manual" : draft.translation_code}
            </span>
            <Button onClick={publish} disabled={busy} data-testid="publish-passage-btn" className="ml-auto h-11 px-5 font-semibold">
              <MonitorUp size={16} /> Send to screen
            </Button>
          </div>
          {draft.warnings?.map((w) => (
            <p key={w} className="mb-2 flex items-center gap-2 text-xs text-amber-300" data-testid="draft-warning"><AlertTriangle size={12} /> {w}</p>
          ))}
          <SlidePreview draft={draft} setDraft={setDraft} />
        </div>
      )}
    </Panel>
  );
};
