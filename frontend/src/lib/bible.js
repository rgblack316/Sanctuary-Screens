import { bibleApi } from "@/lib/api";

// Each blank-line-separated paragraph becomes its own slide.
export function manualDraft(label, text) {
  const parts = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  return {
    reference_input: label,
    normalized_reference: label.trim(),
    translation_code: null,
    source_type: "manual",
    verses: parts.map((p) => ({ reference_label: label.trim(), verse_text: p })),
    warnings: [],
  };
}

// A line containing only "---" starts a new slide; the title shows on every slide.
export function customDraft(title, body = "") {
  const parts = body.split(/^[ \t]*---[ \t]*$/m).map((p) => p.trim()).filter(Boolean);
  return {
    reference_input: title.trim(),
    normalized_reference: title.trim(),
    translation_code: null,
    source_type: "custom",
    custom_body: body,
    verses: (parts.length ? parts : [""]).map((p) => ({ reference_label: title.trim(), verse_text: p })),
    warnings: [],
  };
}

export function hymnDraft({ title, page, hymnal }) {
  const t = title.trim(), p = page.trim();
  const line = p ? `Page ${p}` : "";
  return { ...customDraft(t, [line, hymnal.trim()].filter(Boolean).join("\n")), hymn: true };
}

// The three kinds of slide kept in prepared lists and in the library.
export const KINDS = [
  { id: "scripture", label: "Scripture" },
  { id: "hymn", label: "Hymns" },
  { id: "custom", label: "Custom" },
];
export const kindOf = (it) => it?.kind || "scripture";

export const itemDetail = (it, defaultCode) => {
  if (it.kind === "hymn") return "hymn";
  if (it.kind === "custom") return "custom slide";
  if (it.preloaded_text_optional) return "manual text";
  const code = it.translation_code || `default (${defaultCode})`;
  return it.reference_only ? `reference only · ${code}` : code;
};

export async function lookupDraft(reference, translation_code) {
  const { data } = await bibleApi.post("/bible/lookup", { reference, translation_code });
  return data;
}

export async function referenceOnlyDraft(reference, translation_code) {
  const data = await lookupDraft(reference, translation_code);
  return { ...data, source_type: "reference_only", verses: [{ reference_label: data.normalized_reference, verse_text: "" }] };
}

export function draftFromPrepared(item, defaultCode) {
  if (item.kind === "hymn") return { ...customDraft(item.reference, item.preloaded_text_optional || ""), hymn: true };
  if (item.kind === "custom") return customDraft(item.reference, item.preloaded_text_optional || "");
  if (item.preloaded_text_optional?.trim()) return manualDraft(item.reference, item.preloaded_text_optional);
  const code = item.translation_code || defaultCode;
  return item.reference_only ? referenceOnlyDraft(item.reference, code) : lookupDraft(item.reference, code);
}

export function preparedFromDraft(draft, service_date) {
  const base = { service_date, title_or_note: "", translation_code: draft.translation_code, preloaded_text_optional: "", kind: "scripture", reference_only: false };
  if (draft.source_type === "custom") return { ...base, kind: draft.hymn ? "hymn" : "custom", translation_code: null, reference: draft.normalized_reference, preloaded_text_optional: draft.verses.map((v) => v.verse_text).filter(Boolean).join("\n---\n") };
  if (draft.source_type === "manual") return { ...base, translation_code: null, reference: draft.normalized_reference, preloaded_text_optional: draft.verses.map((v) => v.verse_text).join("\n\n") };
  return { ...base, reference: draft.normalized_reference, reference_only: draft.source_type === "reference_only" };
}

export async function publishDraft(draft, start_index = 0) {
  const { data } = await bibleApi.post("/bible/publish", {
    reference_input: draft.reference_input || "",
    normalized_reference: draft.normalized_reference,
    translation_code: ["local_lookup", "reference_only"].includes(draft.source_type) ? draft.translation_code : null,
    source_type: draft.source_type,
    verses: draft.verses,
    start_index,
  });
  return data;
}

// Name a draft is saved under in the library (the server refuses two slides with the same name).
export function libraryNameFor(draft) {
  const suffix = { reference_only: " (reference only)", local_lookup: ` (${draft.translation_code})`, manual: " (manual)" }[draft.source_type] || "";
  return `${draft.normalized_reference}${suffix}`;
}

// The slides as the preview screen needs them.
export const previewBody = (draft, slide_index = 0) => ({
  normalized_reference: draft.normalized_reference,
  translation_code: ["local_lookup", "reference_only"].includes(draft.source_type) ? draft.translation_code : null,
  source_type: draft.source_type,
  verses: draft.verses.map(({ reference_label, verse_text, book_name, chapter, verse }) => ({ reference_label, verse_text, book_name, chapter, verse })),
  slide_index,
});
