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

export async function lookupDraft(reference, translation_code) {
  const { data } = await bibleApi.post("/bible/lookup", { reference, translation_code });
  return data;
}

export async function referenceOnlyDraft(reference, translation_code) {
  const data = await lookupDraft(reference, translation_code);
  return { ...data, source_type: "reference_only", verses: [{ reference_label: data.normalized_reference, verse_text: "" }] };
}

export function draftFromPrepared(item, defaultCode) {
  if (item.kind === "custom") return customDraft(item.reference, item.preloaded_text_optional || "");
  if (item.preloaded_text_optional?.trim()) return manualDraft(item.reference, item.preloaded_text_optional);
  const code = item.translation_code || defaultCode;
  return item.reference_only ? referenceOnlyDraft(item.reference, code) : lookupDraft(item.reference, code);
}

export function preparedFromDraft(draft, service_date) {
  const base = { service_date, title_or_note: "", translation_code: draft.translation_code, preloaded_text_optional: "", kind: "scripture", reference_only: false };
  if (draft.source_type === "custom") return { ...base, kind: "custom", translation_code: null, reference: draft.normalized_reference, preloaded_text_optional: draft.verses.map((v) => v.verse_text).filter(Boolean).join("\n---\n") };
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
