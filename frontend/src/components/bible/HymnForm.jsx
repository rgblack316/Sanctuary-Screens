import { useState } from "react";
import { toast } from "sonner";
import { Music } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { bibleApi } from "@/lib/api";
import { hymnDraft } from "@/lib/bible";
import { HymnalSelect } from "@/components/bible/HymnalSelect";

export const HymnForm = ({ setDraft }) => {
  const [number, setNumber] = useState("");
  const [title, setTitle] = useState("");
  const [page, setPage] = useState("");
  const [hymnal, setHymnal] = useState("");

  const build = () => {
    if (!number.trim() && !title.trim()) return toast.error("Enter a hymn number or title.");
    setDraft(hymnDraft({ number, title, page, hymnal }));
    bibleApi.put("/bible/hymnals/last", { name: hymnal }).catch(() => {});
  };

  return (
    <div className="space-y-3 rounded-lg border border-[#222B3E] bg-[#0B0E14]/60 p-4" data-testid="hymn-form">
      <p className="label-caps flex items-center gap-2"><Music size={12} /> Hymn shortcut</p>
      <div className="grid gap-2 sm:grid-cols-[110px_1fr_110px]">
        <Input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="Number" maxLength={12} data-testid="hymn-number-input" className="h-11 bg-[#0B0E14]" />
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title, e.g. Amazing Grace" maxLength={160} data-testid="hymn-title-input" className="h-11 bg-[#0B0E14]" />
        <Input value={page} onChange={(e) => setPage(e.target.value)} placeholder="Page" maxLength={12} data-testid="hymn-page-input" className="h-11 bg-[#0B0E14]" />
      </div>
      <HymnalSelect value={hymnal} onChange={setHymnal} />
      <Button variant="secondary" onClick={build} data-testid="hymn-build-btn">Build hymn slide</Button>
    </div>
  );
};
