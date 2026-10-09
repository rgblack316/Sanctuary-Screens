import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { bibleApi, errMsg } from "@/lib/api";

export const TranslationTable = ({ translations, reload }) => {
  const [target, setTarget] = useState(null);
  const only = translations.length <= 1;

  const setDefault = async (code) => {
    try {
      await bibleApi.put("/bible/settings", { default_translation: code });
      toast.success(`${code} is now the default`);
      reload();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const remove = async () => {
    try {
      const { data } = await bibleApi.delete(`/bible/translations/${target.translation_code}`, { params: { confirm: true } });
      toast.success(`${data.deleted} deleted (${data.verses_removed.toLocaleString()} verses removed)`);
      reload();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setTarget(null);
    }
  };

  return (
    <>
      <p className="label-caps mb-3">Installed</p>
      <ul className="space-y-2" data-testid="translation-list">
        {translations.map((t) => {
          const blocked = t.is_live ? "On the live display" : only ? "Last installed translation" : null;
          return (
            <li key={t.translation_code} className="flex flex-wrap items-center gap-3 rounded-lg border border-[#222B3E] bg-[#0B0E14] p-3" data-testid={`translation-row-${t.translation_code}`}>
              <span className="font-display text-lg font-black text-amber-400">{t.translation_code}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{t.translation_name}</p>
                <p className="text-xs text-slate-500">{t.verse_count.toLocaleString()} verses · {t.book_count} books · v{t.import_version} · {new Date(t.updated_at).toLocaleDateString()}</p>
              </div>
              {t.is_live && <span className="rounded-full bg-amber-500/10 px-2 py-1 text-xs font-semibold text-amber-300">Live</span>}
              {t.is_default ? (
                <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-300" data-testid={`translation-default-badge-${t.translation_code}`}>Default</span>
              ) : (
                <button onClick={() => setDefault(t.translation_code)} data-testid={`translation-set-default-${t.translation_code}`} className="rounded-md border border-[#2A3550] px-2 py-1 text-xs font-semibold text-slate-300 hover:border-amber-500/60">Set default</button>
              )}
              <button
                onClick={() => setTarget(t)}
                disabled={!!blocked}
                title={blocked || "Delete translation"}
                data-testid={`translation-delete-${t.translation_code}`}
                className="rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-30"
              >
                <Trash2 size={14} />
              </button>
            </li>
          );
        })}
      </ul>
      <AlertDialog open={!!target} onOpenChange={(o) => !o && setTarget(null)}>
        <AlertDialogContent className="border-[#222B3E] bg-[#121620]" data-testid="delete-translation-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display">Delete {target?.translation_code}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes {target?.translation_name} and {target?.verse_count.toLocaleString()} verses from this machine. Prepared items using it will need another translation.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-translation-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={remove} data-testid="delete-translation-confirm" className="bg-rose-600 hover:bg-rose-500">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
