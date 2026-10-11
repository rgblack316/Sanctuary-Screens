import { useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { bibleApi, errMsg } from "@/lib/api";
import { TranslationSelect } from "@/components/bible/TranslationSelect";

const ScriptureFields = ({ form, set, translations }) => (
  <>
    <Input value={form.reference} onChange={(e) => set("reference")(e.target.value)} placeholder="Reference, e.g. Psalm 23:1-6" data-testid="prepared-reference-input" className="bg-[#0B0E14]" />
    <Input value={form.title_or_note} onChange={(e) => set("title_or_note")(e.target.value)} placeholder="Note (optional), e.g. Opening reading" maxLength={120} data-testid="prepared-note-input" className="bg-[#0B0E14]" />
    <TranslationSelect translations={translations} value={form.translation_code} onChange={set("translation_code")} testid="prepared-translation-select" />
    <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-slate-300">
      <Checkbox checked={form.reference_only} onCheckedChange={(v) => set("reference_only")(!!v)} data-testid="prepared-reference-only-checkbox" />
      Reference only (no verse text)
    </label>
    {!form.reference_only && (
      <Textarea value={form.preloaded_text_optional} onChange={(e) => set("preloaded_text_optional")(e.target.value)} rows={4} placeholder="Optional manual text (overrides lookup). Blank line = new slide." data-testid="prepared-text-input" className="bg-[#0B0E14]" />
    )}
  </>
);

const CustomFields = ({ form, set }) => (
  <>
    <Input value={form.reference} onChange={(e) => set("reference")(e.target.value)} placeholder="Title, e.g. Hymn 245 – Amazing Grace" maxLength={200} data-testid="prepared-custom-title-input" className="bg-[#0B0E14]" />
    <Input value={form.title_or_note} onChange={(e) => set("title_or_note")(e.target.value)} placeholder="Note (optional, not shown on screen)" maxLength={120} data-testid="prepared-custom-note-input" className="bg-[#0B0E14]" />
    <Textarea value={form.preloaded_text_optional} onChange={(e) => set("preloaded_text_optional")(e.target.value)} rows={5} placeholder={"Optional text, e.g. Page 312\nA line with only --- starts a new slide."} data-testid="prepared-custom-body-input" className="bg-[#0B0E14]" />
  </>
);

export const PreparedDialog = ({ item, translations, defaultCode, onClose, onSaved, submit, title }) => {
  const withName = item.name !== undefined;
  const [name, setName] = useState(item.name || "");
  const [form, setForm] = useState({
    service_date: item.service_date,
    title_or_note: item.title_or_note || "",
    reference: item.reference || "",
    translation_code: item.translation_code || defaultCode,
    preloaded_text_optional: item.preloaded_text_optional || "",
    kind: item.kind || "scripture",
    reference_only: !!item.reference_only,
    library_id: item.library_id || null,
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const custom = form.kind === "custom";

  const save = async () => {
    if (withName && !name.trim()) return toast.error("Name is required.");
    if (!form.reference.trim()) return toast.error(custom ? "Title is required." : "Reference is required.");
    const body = { ...form, translation_code: custom ? null : form.translation_code,
      preloaded_text_optional: !custom && form.reference_only ? "" : form.preloaded_text_optional,
      reference_only: !custom && form.reference_only };
    setBusy(true);
    try {
      if (submit) await submit({ ...body, name: name.trim() });
      else if (item.id) await bibleApi.put(`/bible/prepared/${item.id}`, body);
      else await bibleApi.post("/bible/prepared", body);
      if (!submit) toast.success("Prepared list saved");
      onSaved();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="border-[#222B3E] bg-[#121620]" data-testid="prepared-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{title || (item.id ? "Edit prepared item" : "Add prepared item")}</DialogTitle>
        </DialogHeader>
        {withName && (
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Library name" maxLength={120} data-testid="library-name-input" className="bg-[#0B0E14]" />
        )}
        <Tabs value={form.kind} onValueChange={set("kind")}>
          <TabsList className="bg-[#0B0E14]">
            <TabsTrigger value="scripture" data-testid="prepared-kind-scripture">Scripture</TabsTrigger>
            <TabsTrigger value="custom" data-testid="prepared-kind-custom">Custom slide</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="space-y-3">
          {custom ? <CustomFields form={form} set={set} /> : <ScriptureFields form={form} set={set} translations={translations} />}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} data-testid="prepared-cancel-btn">Cancel</Button>
          <Button onClick={save} disabled={busy} data-testid="prepared-save-btn">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
