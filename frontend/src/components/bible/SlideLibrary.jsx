import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { CalendarPlus, Loader2, MonitorUp, Pencil, Search, Trash2, X } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { bibleApi, errMsg } from "@/lib/api";
import { KINDS, draftFromPrepared, itemDetail, publishDraft } from "@/lib/bible";
import { useDebounced } from "@/hooks/useDebounced";
import { PreparedDialog } from "@/components/bible/PreparedDialog";

const PAGE = 25;

export const SlideLibrary = ({ translations, defaultCode, onLoad, date, tick, onPrepared }) => {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState({ scripture: 0, hymn: 0, custom: 0 });
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);
  const seq = useRef(0);
  const search = useDebounced(q, 250);

  const fetchPage = useCallback(async (offset) => {
    const mine = ++seq.current;
    setLoading(true);
    try {
      const params = { q: search, limit: PAGE, offset, ...(kind !== "all" ? { kind } : {}) };
      const { data } = await bibleApi.get("/bible/library", { params });
      if (mine !== seq.current) return; // a newer search replaced this one
      setItems((prev) => (offset === 0 ? data.items : [...prev, ...data.items]));
      setTotal(data.total);
      setCounts(data.counts);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [search, kind]);

  useEffect(() => { fetchPage(0); }, [fetchPage, tick]);

  const saveEdit = async ({ service_date, title_or_note, library_id, ...body }) => {
    const { data } = await bibleApi.put(`/bible/library/${editing.id}`, body);
    toast.success(data.prepared_updated ? `Saved · updated ${data.prepared_updated} prepared item(s)` : "Library slide saved");
    onPrepared();
  };

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

  const addToService = async ({ id, name, created_at, exact, ...rest }) => {
    try {
      await bibleApi.post("/bible/prepared", { ...rest, title_or_note: name, service_date: date, library_id: id });
      toast.success(`${name} added to ${date}`);
      onPrepared();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const remove = async (item) => {
    await bibleApi.delete(`/bible/library/${item.id}`);
    fetchPage(0);
  };

  const allCount = counts.scripture + counts.hymn + counts.custom;

  return (
    <Panel title="Slide library" testid="library-panel">
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <Input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, reference or slide text…"
          data-testid="library-search-input" className="h-10 bg-[#0B0E14] pl-9 pr-9"
        />
        {q && (
          <button type="button" onClick={() => setQ("")} aria-label="Clear search" data-testid="library-search-clear"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:text-slate-200">
            <X size={14} />
          </button>
        )}
      </div>
      <Tabs value={kind} onValueChange={setKind} className="mt-3">
        <TabsList className="grid w-full grid-cols-4 bg-[#0B0E14]">
          <TabsTrigger value="all" data-testid="library-tab-all">All <span className="ml-1.5 text-[10px] text-slate-400">{allCount}</span></TabsTrigger>
          {KINDS.map((k) => (
            <TabsTrigger key={k.id} value={k.id} data-testid={`library-tab-${k.id}`}>
              {k.label} <span className="ml-1.5 text-[10px] text-slate-400">{counts[k.id]}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <ul className="mt-4 max-h-[28rem] space-y-2 overflow-y-auto pr-1" data-testid="library-list">
        {!loading && items.length === 0 && (
          <li className="text-sm text-slate-500" data-testid="library-empty">
            {q || kind !== "all" ? "No saved slides match." : "No saved slides yet. Build a slide, then use “Save to library”."}
          </li>
        )}
        {items.map((it, i) => (
          <li key={it.id} className="rounded-lg border border-[#222B3E] bg-[#0B0E14] p-3" data-testid={`library-item-${i}`}>
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-display font-bold" data-testid={`library-item-name-${i}`}>{it.name}</p>
                <p className="truncate text-xs text-slate-500">{it.reference} · {itemDetail(it, defaultCode)}</p>
              </div>
              <button type="button" onClick={() => setEditing(it)} aria-label="Edit" data-testid={`library-edit-${i}`} className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-amber-300">
                <Pencil size={14} />
              </button>
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
        {loading && <li className="flex items-center gap-2 text-xs text-slate-500"><Loader2 size={12} className="animate-spin" /> Loading…</li>}
      </ul>
      {total > 0 && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span data-testid="library-showing">Showing {items.length} of {total}</span>
          {items.length < total && (
            <Button size="sm" variant="outline" onClick={() => fetchPage(items.length)} disabled={loading} data-testid="library-load-more">Load more</Button>
          )}
        </div>
      )}
      {editing && (
        <PreparedDialog item={editing} translations={translations} defaultCode={defaultCode} title="Edit library slide" submit={saveEdit}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); fetchPage(0); }} />
      )}
    </Panel>
  );
};
