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

export async function lookupDraft(reference, translation_code) {
  const { data } = await bibleApi.post("/bible/lookup", { reference, translation_code });
  return data;
}

export async function publishDraft(draft, start_index = 0) {
  const { data } = await bibleApi.post("/bible/publish", {
    reference_input: draft.reference_input || "",
    normalized_reference: draft.normalized_reference,
    translation_code: draft.source_type === "local_lookup" ? draft.translation_code : null,
    source_type: draft.source_type,
    verses: draft.verses,
    start_index,
  });
  return data;
}
