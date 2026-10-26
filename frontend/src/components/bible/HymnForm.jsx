import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Music, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { bibleApi } from "@/lib/api";
import { hymnDraft } from "@/lib/bible";
import { useDebounced } from "@/hooks/useDebounced";
import { HymnalSelect } from "@/components/bible/HymnalSelect";
import { LibrarySuggest } from "@/components/bible/LibrarySuggest";

const songLine = (s) => [`Page ${s.page}`, s.number ? `#${s.number}` : "", s.songbook].filter(Boolean).join(" · ");

export const HymnForm = ({ setDraft, suggest, songbooksTick }) => {
  const [number, setNumber] = useState("");
  const [title, setTitle] = useState("");
  const [page, setPage] = useState("");
  const [hymnal, setHymnal] = useState("");
  const [lookup, setLookup] = useState("");
  const [hits, setHits] = useState(null); // null = nothing searched yet
  const [searching, setSearching] = useState(false);
  const [bookCount, setBookCount] = useState(null);
  const seq = useRef(0);
  const dq = useDebounced(lookup.trim(), 250);

  useEffect(() => {
    bibleApi.get("/bible/songs/books").then(({ data }) => setBookCount(data.songbooks.length)).catch(() => {});
  }, [songbooksTick]);

  useEffect(() => {
    if (!dq) { setHits(null); return; }
    const mine = ++seq.current;
    setSearching(true);
    bibleApi.get("/bible/songs/search", { params: { q: dq, ...(hymnal ? { songbook: hymnal } : {}) } })
      .then(({ data }) => { if (mine === seq.current) setHits(data); })
      .catch(() => { if (mine === seq.current) setHits({ items: [], total: 0 }); })
      .finally(() => { if (mine === seq.current) setSearching(false); });
  }, [dq, hymnal, songbooksTick]);

  const remember = (name) => bibleApi.put("/bible/hymnals/last", { name }).catch(() => {});

  const build = () => {
    if (!number.trim() && !title.trim()) return toast.error("Enter a hymn number or title.");
    setDraft(hymnDraft({ number, title, page, hymnal }));
    remember(hymnal);
  };

  const choose = (s) => {
    setNumber(s.number || ""); setTitle(s.title); setPage(s.page); setHymnal(s.songbook);
    setDraft(hymnDraft({ number: s.number || "", title: s.title, page: s.page, hymnal: s.songbook }));
    remember(s.songbook);
    setLookup(""); setHits(null);
  };

  return (
    <div className="space-y-3 rounded-lg border border-[#222B3E] bg-[#0B0E14]/60 p-4" data-testid="hymn-form">
      <p className="label-caps flex items-center gap-2"><Music size={12} /> Hymn shortcut</p>
      <HymnalSelect value={hymnal} onChange={setHymnal} />

      <div data-testid="hymn-lookup">
        <div className="relative">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <Input value={lookup} onChange={(e) => setLookup(e.target.value)} placeholder={hymnal ? `Find in ${hymnal} by page, song number or title` : "Find by page, song number or title"}
            data-testid="hymn-lookup-input" className="h-11 bg-[#0B0E14] pl-9" />
          {searching && <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-slate-500" />}
        </div>
        {bookCount === 0 && !hits && (
          <p className="mt-2 text-xs text-slate-500" data-testid="hymn-lookup-hint">No songbook imported yet. Use “Hymnal songbooks” at the bottom of this page to import a CSV and enable quick lookup.</p>
        )}
        {hits && (
          <div className="mt-2" data-testid="hymn-lookup-results">
            {hits.items.length === 0 ? (
              <p className="text-sm text-slate-500" data-testid="hymn-lookup-none">No songs found{hymnal ? ` in ${hymnal}` : ""}.</p>
            ) : (
              <>
                <p className="mb-1 text-xs text-slate-400" data-testid="hymn-lookup-count">
                  {hits.total} match{hits.total === 1 ? "" : "es"}{hits.total > 1 ? " — pick the song you want" : ""}
                </p>
                <ul className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
                  {hits.items.map((s, i) => (
                    <li key={s.id}>
                      <button type="button" onClick={() => choose(s)} data-testid={`hymn-hit-${i}`}
                        className="flex w-full items-center gap-3 rounded-md border border-[#222B3E] bg-[#121620] px-3 py-2 text-left transition-colors hover:border-amber-500/60">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold">{s.title}</span>
                          <span className="block truncate text-xs text-slate-500">{songLine(s)}</span>
                        </span>
                        <span className="text-xs font-semibold text-amber-400">Select</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>

      <p className="label-caps pt-1">Or enter it yourself</p>
      <div className="grid gap-2 sm:grid-cols-[110px_1fr_110px]">
        <Input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="Number" maxLength={12} data-testid="hymn-number-input" className="h-11 bg-[#0B0E14]" />
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title, e.g. Amazing Grace" maxLength={160} data-testid="hymn-title-input" className="h-11 bg-[#0B0E14]" />
        <Input value={page} onChange={(e) => setPage(e.target.value)} placeholder="Page" maxLength={12} data-testid="hymn-page-input" className="h-11 bg-[#0B0E14]" />
      </div>
      <LibrarySuggest text={title} kind="hymn" {...suggest} />
      <Button variant="secondary" onClick={build} data-testid="hymn-build-btn">Build hymn slide</Button>
    </div>
  );
};
