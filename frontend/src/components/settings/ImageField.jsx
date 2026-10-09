import { useRef, useState } from "react";
import { toast } from "sonner";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { assetUrl, errMsg, settingsApi } from "@/lib/api";

export const ImageField = ({ display, imageUrl, onChanged }) => {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await settingsApi.post(`/appearance/${display}/image`, fd);
      onChanged(data.appearance);
      toast.success("Background image is live");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      const { data } = await settingsApi.delete(`/appearance/${display}/image`);
      onChanged(data.appearance);
      toast.success("Background image removed");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-4" data-testid="bg-image-field">
      <div className="grid h-20 w-32 shrink-0 place-items-center overflow-hidden rounded-lg border border-[#2A3550] bg-[#0B0E14]">
        {imageUrl ? (
          <img src={assetUrl(imageUrl)} alt="Background" className="h-full w-full object-cover" data-testid="bg-image-thumb" />
        ) : (
          <span className="text-xs text-slate-500">No image</span>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => ref.current?.click()} data-testid="bg-image-upload-btn">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <ImagePlus size={14} />} {imageUrl ? "Replace image" : "Upload image"}
        </Button>
        {imageUrl && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={remove} data-testid="bg-image-remove-btn" className="text-rose-300 hover:text-rose-200">
            <Trash2 size={14} /> Remove
          </Button>
        )}
        <span className="text-xs text-slate-500">PNG, JPG, WEBP or GIF · max 12 MB</span>
      </div>
      <input ref={ref} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={(e) => upload(e.target.files?.[0])} data-testid="bg-image-input" />
    </div>
  );
};
