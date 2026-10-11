import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { bibleApi, errMsg } from "@/lib/api";

const NONE = "__none__";

export const HymnalSelect = ({ value, onChange }) => {
  const [hymnals, setHymnals] = useState([]);
  const [adding, setAdding] = useState("");

  const load = useCallback(async () => {
    const { data } = await bibleApi.get("/bible/hymnals");
    setHymnals(data.hymnals);
    return data;
  }, []);

  useEffect(() => {
    load().then((d) => onChange(d.last_used || "")).catch(() => {});
  }, [load]); // eslint-disable-line react-hooks/exhaustive-deps

  const add = async () => {
    if (!adding.trim()) return;
    try {
      const { data } = await bibleApi.post("/bible/hymnals", { name: adding.trim() });
      await load();
      onChange(data.name);
      setAdding("");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const remove = async () => {
    const h = hymnals.find((x) => x.name === value);
    if (!h) return;
    await bibleApi.delete(`/bible/hymnals/${h.id}`);
    onChange("");
    load();
  };

  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? "" : v)}>
        <SelectTrigger data-testid="hymnal-select" className="h-11 bg-[#0B0E14] sm:w-56"><SelectValue placeholder="Hymnal" /></SelectTrigger>
        <SelectContent>
          <SelectItem value={NONE} data-testid="hymnal-option-none">No hymnal name</SelectItem>
          {hymnals.map((h) => <SelectItem key={h.id} value={h.name} data-testid={`hymnal-option-${h.name}`}>{h.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {value && (
        <Button type="button" variant="ghost" size="icon" onClick={remove} aria-label="Delete hymnal from list" data-testid="hymnal-delete-btn" className="h-11 text-slate-400 hover:text-rose-300">
          <Trash2 size={14} />
        </Button>
      )}
      <Input value={adding} onChange={(e) => setAdding(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())} placeholder="New hymnal name" maxLength={80} data-testid="hymnal-new-input" className="h-11 flex-1 bg-[#0B0E14]" />
      <Button type="button" variant="outline" onClick={add} disabled={!adding.trim()} data-testid="hymnal-add-btn" className="h-11"><Plus size={14} /> Add</Button>
    </div>
  );
};
