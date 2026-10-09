import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { PinGate } from "@/components/live/PinGate";
import { AdminShell } from "@/components/AdminShell";
import { useLiveChannel } from "@/hooks/useLiveChannel";
import { bibleApi, errMsg } from "@/lib/api";
import { LiveControl } from "@/components/bible/LiveControl";
import { Composer } from "@/components/bible/Composer";
import { PreparedList } from "@/components/bible/PreparedList";
import { TranslationManager } from "@/components/bible/TranslationManager";

function BibleConsole() {
  const { data: live, status } = useLiveChannel("bible");
  const [translations, setTranslations] = useState([]);
  const [defaultCode, setDefaultCode] = useState(null);
  const [draft, setDraft] = useState(null);

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
    <AdminShell area="bible" title="Bible Admin" status={status} displayPath="/bible">
      <LiveControl live={live} translations={translations} />
      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <PreparedList translations={translations} defaultCode={defaultCode} onLoad={setDraft} />
        </div>
        <div className="lg:col-span-7">
          <Composer translations={translations} defaultCode={defaultCode} draft={draft} setDraft={setDraft} />
        </div>
      </div>
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
