import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarPlus, MonitorUp, Trash2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { bibleApi, errMsg } from "@/lib/api";
import { draftFromPrepared, itemDetail, publishDraft } from "@/lib/bible";

export const SlideLibrary = ({ defaultCode, onLoad, date, tick, onPrepared }) => {
  const [items, setItems] = useState([]);

  const load = useCallback(async () => {
    try {
      const { data } = await bibleApi.get("/bible/library");
      setItems(data.items);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, []);

  useEffect(() => { load(); }, [load, tick]);

  const use = async (item, live) => {
    try {
      const d = await draftFromPrepared(item, defaultCode);
      onLoad(d);
      if (live) {
        await publishDraft(d, 0);
        toast.success(`${item.name} is on screen`);
      }
    } catch (e) {
      toast.error(`${item.name}: ${errMsg(e)}`);
    }
  };

  const addToService = async ({ id, name, created_at, ...rest }) => {
    try {
      await bibleApi.post("/bible/prepared", { ...rest, title_or_note: name, service_date: date });
      toast.success(`${name} added to ${date}`);
      onPrepared();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const remove = async (item) => {
    await bibleApi.delete(`/bible/library/${item.id}`);
    load();
  };

  return (
    <Panel title="Slide library" testid="library-panel">
      <ul className="space-y-2" data-testid="library-list">
        {items.length === 0 && <li className="text-sm text-slate-500" data-testid="library-empty">No saved slides yet. Build a slide, then use “Save to library”.</li>}
        {items.map((it, i) => (
          <li key={it.id} className="rounded-lg border border-[#222B3E] bg-[#0B0E14] p-3" data-testid={`library-item-${i}`}>
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-display font-bold" data-testid={`library-item-name-${i}`}>{it.name}</p>
                <p className="truncate text-xs text-slate-500">{it.reference} · {itemDetail(it, defaultCode)}</p>
              </div>
              <button type="button" onClick={() => remove(it)} aria-label="Delete" data-testid={`library-delete-${i}`} className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-rose-300">
                <Trash2 size={14} />
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => use(it, false)} data-testid={`library-preview-${i}`}>Preview</Button>
              <Button size="sm" onClick={() => use(it, true)} data-testid={`library-golive-${i}`}><MonitorUp size={14} /> Go live</Button>
              <Button size="sm" variant="outline" onClick={() => addToService(it)} data-testid={`library-add-service-${i}`}><CalendarPlus size={14} /> Add to {date}</Button>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
};
