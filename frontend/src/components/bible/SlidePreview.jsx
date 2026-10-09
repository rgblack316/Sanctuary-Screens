import { useState } from "react";
import { Check, Pencil } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

function SlideRow({ slide, index, onChange }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(slide.verse_text);

  const save = () => {
    if (text.trim()) onChange(index, text.trim());
    setEditing(false);
  };

  return (
    <li className="rounded-lg border border-[#222B3E] bg-[#0B0E14] p-4" data-testid={`preview-slide-${index}`}>
      <div className="flex items-center gap-3">
        <span className="font-mono-ui text-xs text-slate-500">{String(index + 1).padStart(2, "0")}</span>
        <span className="font-display text-sm font-bold uppercase tracking-widest text-amber-400">{slide.reference_label}</span>
        <button
          type="button"
          onClick={() => (editing ? save() : setEditing(true))}
          data-testid={`preview-slide-edit-${index}`}
          className="ml-auto rounded-md p-1.5 text-slate-400 hover:bg-[#1A202C] hover:text-amber-300"
          aria-label={editing ? "Save slide text" : "Edit slide text"}
        >
          {editing ? <Check size={14} /> : <Pencil size={14} />}
        </button>
      </div>
      {editing ? (
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} data-testid={`preview-slide-textarea-${index}`} className="mt-3 bg-[#121620]" autoFocus />
      ) : (
        <p className="mt-2 text-slate-200">{slide.verse_text}</p>
      )}
    </li>
  );
}

export const SlidePreview = ({ draft, setDraft }) => {
  const update = (i, text) =>
    setDraft({ ...draft, verses: draft.verses.map((v, j) => (j === i ? { ...v, verse_text: text } : v)) });
  return (
    <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1" data-testid="slide-preview-list">
      {draft.verses.map((s, i) => (
        <SlideRow key={`${draft.normalized_reference}-${i}-${s.reference_label}`} slide={s} index={i} onChange={update} />
      ))}
    </ul>
  );
};
