import { useState } from "react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { customDraft } from "@/lib/bible";
import { LibrarySuggest } from "@/components/bible/LibrarySuggest";

export const CustomSlideForm = ({ setDraft, suggest }) => {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const build = () => {
    if (!title.trim()) return toast.error("Enter a title for the slide.");
    setDraft(customDraft(title, body));
  };

  return (
    <div className="space-y-3">
      <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title, e.g. Welcome and announcements" maxLength={200} data-testid="custom-title-input" className="h-11 bg-[#0B0E14] text-base" />
      <LibrarySuggest text={title} kind="custom" {...suggest} />
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6} placeholder={"Optional text, e.g. Page 312\n\nType a line with only --- to start a new slide."} data-testid="custom-body-input" className="bg-[#0B0E14]" />
      <p className="text-xs text-slate-500">Title uses the Scripture Reference style; text uses the Verse Text style. No translation label is shown.</p>
      <Button variant="secondary" onClick={build} data-testid="custom-build-btn">Build slides</Button>
    </div>
  );
};
