import { useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { bibleApi, errMsg } from "@/lib/api";
import { TranslationSelect } from "@/components/bible/TranslationSelect";

export const PreparedDialog = ({ item, translations, defaultCode, onClose, onSaved }) => {
  const [form, setForm] = useState({
    service_date: item.service_date,
    title_or_note: item.title_or_note || "",
    reference: item.reference || "",
    translation_code: item.translation_code || defaultCode,
    preloaded_text_optional: item.preloaded_text_optional || "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.reference.trim()) return toast.error("Reference is required.");
    setBusy(true);
    try {
      if (item.id) await bibleApi.put(`/bible/prepared/${item.id}`, form);
      else await bibleApi.post("/bible/prepared", form);
      toast.success("Prepared list saved");
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
          <DialogTitle className="font-display">{item.id ? "Edit prepared scripture" : "Add prepared scripture"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <Input value={form.reference} onChange={(e) => set("reference")(e.target.value)} placeholder="Reference, e.g. Psalm 23:1-6" data-testid="prepared-reference-input" className="bg-[#0B0E14]" />
          <Input value={form.title_or_note} onChange={(e) => set("title_or_note")(e.target.value)} placeholder="Note (optional), e.g. Opening reading" maxLength={120} data-testid="prepared-note-input" className="bg-[#0B0E14]" />
          <TranslationSelect translations={translations} value={form.translation_code} onChange={set("translation_code")} testid="prepared-translation-select" />
          <Textarea value={form.preloaded_text_optional} onChange={(e) => set("preloaded_text_optional")(e.target.value)} rows={4} placeholder="Optional manual text (overrides lookup). Blank line = new slide." data-testid="prepared-text-input" className="bg-[#0B0E14]" />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} data-testid="prepared-cancel-btn">Cancel</Button>
          <Button onClick={save} disabled={busy} data-testid="prepared-save-btn">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
