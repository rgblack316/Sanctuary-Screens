import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, MonitorUp, Pencil, Plus, Trash2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { bibleApi, errMsg } from "@/lib/api";
import { KINDS, draftFromPrepared, itemDetail, kindOf, publishDraft } from "@/lib/bible";
import { PreparedDialog } from "@/components/bible/PreparedDialog";
import { DatePicker } from "@/components/DatePicker";

const IconBtn = ({ onClick, label, testid, children, danger, disabled }) => (
  <button
    type="button" onClick={onClick} aria-label={label} title={label} data-testid={testid} disabled={disabled}
    className={`rounded-md p-1.5 text-slate-400 transition-colors hover:bg-[#1A202C] disabled:opacity-30 disabled:hover:bg-transparent ${danger ? "hover:text-rose-300" : "hover:text-amber-300"}`}
  >
    {children}
  </button>
);

const EMPTY = {
  scripture: "No scripture prepared for this date.",
  hymn: "No hymns prepared for this date.",
  custom: "No custom slides prepared for this date.",
};

export const PreparedList = ({ translations, defaultCode, onLoad, date, setDate, tick }) => {
  const [items, setItems] = useState([]);
  const [dialog, setDialog] = useState(null);
  const [markedDates, setMarkedDates] = useState([]);
  const [tab, setTab] = useState("scripture");

  const load = useCallback(async () => {
    try {
      const [{ data }, { data: d }] = await Promise.all([
        bibleApi.get("/bible/prepared", { params: { service_date: date } }),
        bibleApi.get("/bible/prepared-dates"),
      ]);
      setItems(data.items);
      setMarkedDates(d.dates);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, [date]);

  useEffect(() => { load(); }, [load, tick]);

  const lists = useMemo(() => {
    const out = { scripture: [], hymn: [], custom: [] };
    items.forEach((it) => (out[kindOf(it)] || out.custom).push(it));
    return out;
  }, [items]);
  const shown = lists[tab];

  const loadItem = async (item, live) => {
    try {
      const d = await draftFromPrepared(item, defaultCode);
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
    try {
      const { data } = await bibleApi.post(`/bible/prepared/${item.id}/move`, { direction });
      setItems(data.items);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const remove = async (item) => {
    await bibleApi.delete(`/bible/prepared/${item.id}`);
    load();
  };

  return (
    <Panel
      title="Prepared for service"
      testid="prepared-panel"
      actions={
        <Button size="sm" onClick={() => setDialog({ service_date: date, kind: tab })} data-testid="prepared-add-btn">
          <Plus size={14} /> Add
        </Button>
      }
    >
      <div className="block">
        <span className="label-caps">Service date</span>
        <DatePicker value={date} onChange={setDate} testid="prepared-date" markedDates={markedDates} markLabel="Has prepared scripture" />
      </div>

      <Tabs value={tab} onValueChange={setTab} className="mt-4">
        <TabsList className="grid w-full grid-cols-3 bg-[#0B0E14]">
          {KINDS.map((k) => (
            <TabsTrigger key={k.id} value={k.id} data-testid={`prepared-tab-${k.id}`}>
              {k.label}
              <span className="ml-2 rounded-full bg-[#1A202C] px-1.5 text-[10px] text-slate-400" data-testid={`prepared-count-${k.id}`}>{lists[k.id].length}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <ol className="mt-4 max-h-[28rem] space-y-2 overflow-y-auto pr-1" data-testid="prepared-list" data-kind={tab}>
        {shown.length === 0 && <li className="text-sm text-slate-500" data-testid="prepared-empty">{EMPTY[tab]}</li>}
        {shown.map((it, i) => (
          <li key={it.id} className="group rounded-lg border border-[#222B3E] bg-[#0B0E14] p-3" data-testid={`prepared-item-${i}`}>
            <div className="flex items-start gap-3">
              <span className="mt-0.5 font-mono-ui text-xs text-slate-500">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="font-display font-bold" data-testid={`prepared-item-ref-${i}`}>{it.reference}</p>
                <p className="truncate text-xs text-slate-500">
                  {it.title_or_note || "—"} · <span data-testid={`prepared-item-kind-${i}`}>{itemDetail(it, defaultCode)}</span>
                </p>
              </div>
              <div className="flex items-center">
                <IconBtn onClick={() => move(it, "up")} label="Move up" testid={`prepared-up-${i}`} disabled={i === 0}><ArrowUp size={14} /></IconBtn>
                <IconBtn onClick={() => move(it, "down")} label="Move down" testid={`prepared-down-${i}`} disabled={i === shown.length - 1}><ArrowDown size={14} /></IconBtn>
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
