import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, CircleOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { bibleApi, errMsg } from "@/lib/api";
import { TranslationSelect } from "@/components/bible/TranslationSelect";

const isTyping = (el) => el && (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.isContentEditable);

export const LiveControl = ({ live, translations }) => {
  const [busy, setBusy] = useState(false);
  const active = live?.mode === "passage";

  const call = async (path, body) => {
    setBusy(true);
    try {
      await bibleApi.post(path, body);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!active) return undefined;
    const onKey = (e) => {
      if (isTyping(document.activeElement) || document.querySelector("[role=dialog]")) return;
      if (["ArrowRight", "PageDown"].includes(e.key)) { e.preventDefault(); call("/bible/display/next"); }
      if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); call("/bible/display/prev"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  return (
    <section data-testid="live-control" className={`rounded-xl border bg-[#121620] ${active ? "border-amber-500/50" : "border-[#222B3E]"}`}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[#222B3E] px-5 py-3">
        <span data-testid="live-mode-badge" className={`rounded-full px-3 py-1 text-xs font-bold tracking-widest ${active ? "bg-amber-500 text-[#090B10]" : "bg-slate-700/50 text-slate-300"}`}>
          {active ? "ON SCREEN" : "IDLE"}
        </span>
        <h2 className="font-display text-lg font-bold" data-testid="live-reference">{active ? live.reference : "Idle slide is showing"}</h2>
        {active && live.source_type === "manual" && <span className="text-xs text-slate-500">manual text</span>}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {active && live.source_type === "local_lookup" && (
            <TranslationSelect
              translations={translations}
              value={live.translation_code}
              onChange={(code) => code !== live.translation_code && call("/bible/display/translation", { translation_code: code })}
              testid="live-translation-select"
              className="h-9 w-56"
              disabled={busy}
            />
          )}
          <Button variant="outline" disabled={!active || busy} onClick={() => call("/bible/display/clear")} data-testid="clear-to-idle-btn" className="h-9 border-rose-500/40 text-rose-300 hover:bg-rose-500/10 hover:text-rose-200">
            <CircleOff size={14} /> Clear to idle
          </Button>
        </div>
      </div>
      {active ? (
        <div className="grid gap-5 p-5 md:grid-cols-[auto_1fr_auto] md:items-center">
          <Button size="lg" variant="secondary" disabled={busy || live.slide_index === 0} onClick={() => call("/bible/display/prev")} data-testid="prev-slide-btn" className="h-16 w-full md:w-28">
            <ChevronLeft /> Prev
          </Button>
          <div className="min-w-0 text-center">
            <p className="font-display text-sm font-bold uppercase tracking-widest text-amber-400" data-testid="live-slide-label">
              {live.slide.reference_label} <span className="text-slate-500">· {live.slide_index + 1}/{live.total}</span>
            </p>
            <p className="mt-2 line-clamp-3 text-lg text-slate-200" data-testid="live-slide-text">{live.slide.verse_text}</p>
            {live.total > 1 && (
              <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                {live.slides.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => call("/bible/display/goto", { index: i })}
                    title={s.reference_label}
                    data-testid={`live-slide-chip-${i}`}
                    className={`h-8 min-w-8 rounded-md px-2 font-mono-ui text-xs transition-colors ${i === live.slide_index ? "bg-amber-500 text-[#090B10] font-bold" : "border border-[#2A3550] text-slate-400 hover:border-amber-500/60"}`}
                  >
                    {s.verse ?? i + 1}
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button size="lg" disabled={busy || live.slide_index >= live.total - 1} onClick={() => call("/bible/display/next")} data-testid="next-slide-btn" className="h-16 w-full md:w-28">
            Next <ChevronRight />
          </Button>
        </div>
      ) : (
        <p className="p-5 text-sm text-slate-500">Look up or load a prepared scripture below, then send it to the screen. Arrow keys / PageUp / PageDown move between verses while live.</p>
      )}
    </section>
  );
};
