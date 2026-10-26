import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { PinGate } from "@/components/live/PinGate";
import { AdminShell } from "@/components/AdminShell";
import { useLiveChannel } from "@/hooks/useLiveChannel";
import { bibleApi, errMsg, todayLocal } from "@/lib/api";
import { previewBody } from "@/lib/bible";
import { LiveControl } from "@/components/bible/LiveControl";
import { Composer } from "@/components/bible/Composer";
import { PreparedList } from "@/components/bible/PreparedList";
import { SlideLibrary } from "@/components/bible/SlideLibrary";
import { TranslationManager } from "@/components/bible/TranslationManager";
import { SongbookManager } from "@/components/bible/SongbookManager";

function BibleConsole() {
  const { data: live, status } = useLiveChannel("bible");
  const [translations, setTranslations] = useState([]);
  const [defaultCode, setDefaultCode] = useState(null);
  const [draft, setDraft] = useState(null);
  const [date, setDate] = useState(todayLocal());
  const [preparedTick, setPreparedTick] = useState(0);
  const [libraryTick, setLibraryTick] = useState(0);
  const [songbooksTick, setSongbooksTick] = useState(0);
  const [previewIndex, setPreviewIndex] = useState(0);
  const bumpPrepared = () => setPreparedTick((t) => t + 1);
  const lastRef = useRef(null); // which slide set is on the preview screen, to reset to slide 1 when it changes
  const indexRef = useRef(0);
  indexRef.current = previewIndex;

  // Whatever is loaded in the composer is mirrored to /bible-preview (not to the live /bible screen).
  useEffect(() => {
    if (!draft) return undefined;
    const id = `${draft.source_type}|${draft.normalized_reference}|${draft.translation_code}`;
    if (lastRef.current !== id) { lastRef.current = id; setPreviewIndex(0); indexRef.current = 0; }
    const t = setTimeout(() => {
      bibleApi.put("/preview", previewBody(draft, indexRef.current)).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [draft]);

  const selectSlide = (i) => {
    setPreviewIndex(i);
    bibleApi.post("/preview/index", { index: i }).catch(() => {});
  };

  const loadTranslations = useCallback(async () => {
    try {
      const { data } = await bibleApi.get("/bible/translations");
      setTranslations(data.translations);
      setDefaultCode(data.default_translation);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, []);

  useEffect(() => { loadTranslations(); }, [loadTranslations, live?.translation_code, live?.mode]);

  return (
    <AdminShell area="bible" title="Bible Admin" status={status} displayPath="/bible" extraLinks={[{ path: "/bible-preview", label: "Open /bible-preview" }]}>
      <LiveControl live={live} translations={translations} />
      <div className="grid gap-8 lg:grid-cols-12">
        <div className="space-y-8 lg:col-span-5">
          <PreparedList translations={translations} defaultCode={defaultCode} onLoad={setDraft} date={date} setDate={setDate} tick={preparedTick} />
          <SlideLibrary translations={translations} defaultCode={defaultCode} onLoad={setDraft} date={date} tick={libraryTick} onPrepared={bumpPrepared} />
        </div>
        <div className="lg:col-span-7">
          <Composer translations={translations} defaultCode={defaultCode} draft={draft} setDraft={setDraft}
            serviceDate={date} onPrepared={bumpPrepared} onLibrary={() => setLibraryTick((t) => t + 1)} libraryTick={libraryTick}
            songbooksTick={songbooksTick} previewIndex={previewIndex} onSelectSlide={selectSlide} />
        </div>
      </div>
      <SongbookManager onChanged={() => setSongbooksTick((t) => t + 1)} />
      <TranslationManager translations={translations} defaultCode={defaultCode} reload={loadTranslations} />
    </AdminShell>
  );
}

export default function BibleAdmin() {
  return (
    <PinGate area="bible">
      <BibleConsole />
    </PinGate>
  );
}
