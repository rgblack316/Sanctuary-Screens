import { useEffect, useRef, useState } from "react";
import { BookmarkCheck, CalendarPlus, FilePlus2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { bibleApi } from "@/lib/api";
import { itemDetail } from "@/lib/bible";
import { useDebounced } from "@/hooks/useDebounced";

// Shows slides already saved in the library that match what is being typed, so the same slide is not built twice.
export const LibrarySuggest = ({ text, kind, translationCode, onUse, onAdd, date }) => {
  const q = useDebounced((text || "").trim(), 300);
  const [res, setRes] = useState({ items: [], normalized: null });
  const seq = useRef(0);

  useEffect(() => {
    if (q.length < 2) { setRes({ items: [], normalized: null }); return undefined; }
    const mine = ++seq.current;
    const params = { text: q, ...(kind ? { kind } : {}), ...(translationCode ? { translation_code: translationCode } : {}) };
    bibleApi.get("/bible/library/match", { params })
      .then(({ data }) => { if (mine === seq.current) setRes(data); })
      .catch(() => {});
    return undefined;
  }, [q, kind, translationCode]);

  if (!res.items.length) return null;
  const exact = res.items.some((i) => i.exact);

  return (
    <div className={`mt-3 rounded-lg border p-3 ${exact ? "border-amber-500/40 bg-amber-500/5" : "border-[#2A3550] bg-[#0B0E14]/60"}`} data-testid="library-suggest">
      <p className={`flex items-center gap-2 text-xs font-semibold ${exact ? "text-amber-300" : "text-slate-400"}`} data-testid="library-suggest-title">
        <BookmarkCheck size={13} />
        {exact ? "Already in your slide library — use it instead of building a new one" : "Similar slides in your library"}
      </p>
      <ul className="mt-2 max-h-44 space-y-1.5 overflow-y-auto pr-1">
        {res.items.map((it, i) => (
          <li key={it.id} className="flex flex-wrap items-center gap-2 rounded-md bg-[#121620] px-3 py-2" data-testid={`library-suggest-item-${i}`}>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">
                {it.name}
                {it.exact && <span className="ml-2 rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">exact</span>}
              </p>
              <p className="truncate text-xs text-slate-500">{it.reference} · {itemDetail(it)}</p>
            </div>
            <Button size="sm" variant="secondary" onClick={() => onUse(it)} data-testid={`library-suggest-use-${i}`}><FilePlus2 size={13} /> Use</Button>
            <Button size="sm" variant="outline" onClick={() => onAdd(it)} data-testid={`library-suggest-add-${i}`}><CalendarPlus size={13} /> Add to {date}</Button>
          </li>
        ))}
      </ul>
    </div>
  );
};
