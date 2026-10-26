import { useState } from "react";
import { Check, Pencil } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

function SlideRow({ slide, index, onChange, allowEmpty, active, onSelect }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(slide.verse_text);

  const save = () => {
    if (text.trim() || allowEmpty) onChange(index, text.trim());
    setEditing(false);
  };

  return (
    <li className={`rounded-lg border bg-[#0B0E14] p-4 ${active ? "border-amber-500/60" : "border-[#222B3E]"}`} data-testid={`preview-slide-${index}`} data-active={active ? "true" : "false"}>
      <div className="flex items-center gap-3">
        {onSelect ? (
          <button type="button" onClick={() => onSelect(index)} title="Show this slide on /bible-preview" data-testid={`preview-slide-select-${index}`}
            className={`font-mono-ui rounded px-1.5 py-0.5 text-xs transition-colors ${active ? "bg-amber-500 font-bold text-[#090B10]" : "text-slate-500 hover:bg-[#1A202C] hover:text-amber-300"}`}>
            {String(index + 1).padStart(2, "0")}
          </button>
        ) : (
          <span className="font-mono-ui text-xs text-slate-500">{String(index + 1).padStart(2, "0")}</span>
        )}
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
        <p className="mt-2 whitespace-pre-line text-slate-200">{slide.verse_text || <span className="italic text-slate-500">Title only</span>}</p>
      )}
    </li>
  );
}

export const SlidePreview = ({ draft, setDraft, activeIndex, onSelect }) => {
  const update = (i, text) =>
    setDraft({ ...draft, verses: draft.verses.map((v, j) => (j === i ? { ...v, verse_text: text } : v)) });
  return (
    <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1" data-testid="slide-preview-list">
      {draft.verses.map((s, i) => (
        <SlideRow key={`${draft.normalized_reference}-${i}-${s.reference_label}`} slide={s} index={i} onChange={update} allowEmpty={draft.source_type !== "manual" && draft.source_type !== "local_lookup"} active={activeIndex === i} onSelect={onSelect} />
      ))}
    </ul>
  );
};
