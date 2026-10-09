import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, MonitorUp, Pencil, Plus, Trash2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { bibleApi, errMsg, todayLocal } from "@/lib/api";
import { lookupDraft, manualDraft, publishDraft } from "@/lib/bible";
import { PreparedDialog } from "@/components/bible/PreparedDialog";
import { DatePicker } from "@/components/DatePicker";

const IconBtn = ({ onClick, label, testid, children, danger }) => (
  <button
    type="button" onClick={onClick} aria-label={label} title={label} data-testid={testid}
    className={`rounded-md p-1.5 text-slate-400 transition-colors hover:bg-[#1A202C] ${danger ? "hover:text-rose-300" : "hover:text-amber-300"}`}
  >
    {children}
  </button>
);

export const PreparedList = ({ translations, defaultCode, onLoad }) => {
  const [date, setDate] = useState(todayLocal());
  const [items, setItems] = useState([]);
  const [dialog, setDialog] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await bibleApi.get("/bible/prepared", { params: { service_date: date } });
      setItems(data.items);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const toDraft = async (item) => {
    if (item.preloaded_text_optional?.trim()) return manualDraft(item.reference, item.preloaded_text_optional);
    return lookupDraft(item.reference, item.translation_code || defaultCode);
  };

  const loadItem = async (item, live) => {
    try {
      const d = await toDraft(item);
      onLoad(d);
      if (live) {
        await publishDraft(d, 0);
        toast.success(`${d.normalized_reference} is on screen`);
      }
    } catch (e) {
      toast.error(`${item.reference}: ${errMsg(e)}`);
    }
  };

  const move = async (item, direction) => {
    const { data } = await bibleApi.post(`/bible/prepared/${item.id}/move`, { direction });
    setItems(data.items);
  };

  const remove = async (item) => {
    await bibleApi.delete(`/bible/prepared/${item.id}`);
    load();
  };

  return (
    <Panel
      title="Prepared scripture"
      testid="prepared-panel"
      actions={
        <Button size="sm" onClick={() => setDialog({ service_date: date })} data-testid="prepared-add-btn">
          <Plus size={14} /> Add
        </Button>
      }
    >
      <div className="block">
        <span className="label-caps">Service date</span>
        <DatePicker value={date} onChange={setDate} testid="prepared-date" />
      </div>
      <ol className="mt-4 space-y-2" data-testid="prepared-list">
        {items.length === 0 && <li className="text-sm text-slate-500" data-testid="prepared-empty">No scriptures prepared for this date.</li>}
        {items.map((it, i) => (
          <li key={it.id} className="group rounded-lg border border-[#222B3E] bg-[#0B0E14] p-3" data-testid={`prepared-item-${i}`}>
            <div className="flex items-start gap-3">
              <span className="mt-0.5 font-mono-ui text-xs text-slate-500">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="font-display font-bold" data-testid={`prepared-item-ref-${i}`}>{it.reference}</p>
                <p className="truncate text-xs text-slate-500">
                  {it.title_or_note || "—"} · {it.preloaded_text_optional ? "manual text" : it.translation_code || `default (${defaultCode})`}
                </p>
              </div>
              <div className="flex items-center">
                <IconBtn onClick={() => move(it, "up")} label="Move up" testid={`prepared-up-${i}`}><ArrowUp size={14} /></IconBtn>
                <IconBtn onClick={() => move(it, "down")} label="Move down" testid={`prepared-down-${i}`}><ArrowDown size={14} /></IconBtn>
                <IconBtn onClick={() => setDialog(it)} label="Edit" testid={`prepared-edit-${i}`}><Pencil size={14} /></IconBtn>
                <IconBtn onClick={() => remove(it)} label="Delete" testid={`prepared-delete-${i}`} danger><Trash2 size={14} /></IconBtn>
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <Button size="sm" variant="secondary" onClick={() => loadItem(it, false)} data-testid={`prepared-load-${i}`}>Preview</Button>
              <Button size="sm" onClick={() => loadItem(it, true)} data-testid={`prepared-golive-${i}`}><MonitorUp size={14} /> Go live</Button>
            </div>
          </li>
        ))}
      </ol>
      {dialog && (
        <PreparedDialog item={dialog} translations={translations} defaultCode={defaultCode} onClose={() => setDialog(null)} onSaved={() => { setDialog(null); load(); }} />
      )}
    </Panel>
  );
};
