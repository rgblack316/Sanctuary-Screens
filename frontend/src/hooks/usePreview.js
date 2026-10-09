import { useEffect, useState } from "react";

// When a display page is embedded as a preview iframe in Display Settings, the parent
// sends {type: "ss-preview", appearance, sample} so unsaved changes show instantly.
export function usePreview() {
  const [preview, setPreview] = useState(null);
  useEffect(() => {
    if (window.parent === window) return undefined;
    const onMsg = (e) => {
      if (e.origin === window.location.origin && e.data?.type === "ss-preview") setPreview(e.data);
    };
    window.addEventListener("message", onMsg);
    window.parent.postMessage({ type: "ss-preview-ready" }, window.location.origin);
    return () => window.removeEventListener("message", onMsg);
  }, []);
  return preview;
}
