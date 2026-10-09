import { useEffect, useRef, useState } from "react";

const SIZES = { landscape: [1920, 1080], portrait: [1080, 1920] };

// Renders the real display page in an iframe and pushes unsaved appearance into it.
export const DisplayPreview = ({ path, appearance, churchName, sample, orientation }) => {
  const frameRef = useRef(null);
  const boxRef = useRef(null);
  const [scale, setScale] = useState(0.3);
  const [w, h] = SIZES[orientation];

  const push = () => frameRef.current?.contentWindow?.postMessage(
    { type: "ss-preview", appearance, sample, church_name: churchName }, window.location.origin);

  useEffect(push); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onMsg = (e) => e.origin === window.location.origin && e.data?.type === "ss-preview-ready" && push();
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  });

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(() => {
      const maxH = orientation === "portrait" ? 560 : Infinity;
      setScale(Math.min(el.clientWidth / w, maxH / h));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [w, h, orientation]);

  return (
    <div ref={boxRef} className="w-full" data-testid="display-preview">
      <div className="mx-auto overflow-hidden rounded-lg border border-[#2A3550]" style={{ width: w * scale, height: h * scale }}>
        <iframe
          ref={frameRef}
          title={`${path} preview`}
          src={path}
          onLoad={push}
          data-testid="display-preview-frame"
          style={{ width: w, height: h, transform: `scale(${scale})`, transformOrigin: "0 0", border: 0, pointerEvents: "none" }}
        />
      </div>
    </div>
  );
};
