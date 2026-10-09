import { useLayoutEffect, useRef, useState } from "react";
import { useLiveChannel } from "@/hooks/useLiveChannel";
import { WsStatus } from "@/components/live/WsStatus";
import { assetUrl } from "@/lib/api";

const baseSize = (n) => (n < 80 ? 8 : n < 160 ? 6.6 : n < 280 ? 5.4 : n < 420 ? 4.6 : n < 600 ? 3.9 : 3.3);

// Shrinks the verse until it fits the box (handles very long verses on small screens).
function FitText({ text }) {
  const boxRef = useRef(null);
  const textRef = useRef(null);
  const [size, setSize] = useState(baseSize(text.length));
  const [tick, setTick] = useState(0);

  useLayoutEffect(() => {
    const onResize = () => setTick((t) => t + 1);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useLayoutEffect(() => {
    const box = boxRef.current;
    const el = textRef.current;
    if (!box || !el) return;
    let s = baseSize(text.length);
    el.style.fontSize = `${s}vmin`;
    while (s > 1.6 && (el.scrollHeight > box.clientHeight || el.scrollWidth > box.clientWidth)) {
      s *= 0.93;
      el.style.fontSize = `${s}vmin`;
    }
    setSize(s);
  }, [text, tick]);

  return (
    <div ref={boxRef} className="bible-text-box">
      <p ref={textRef} data-testid="bible-verse-text" className="bible-text fade-in" key={text} style={{ fontSize: `${size}vmin` }}>
        {text}
      </p>
    </div>
  );
}

const IdleSlide = ({ idle }) => (
  <div className="bible-screen items-center justify-center text-center" data-testid="bible-idle-slide">
    {idle?.image_url && (
      <img src={assetUrl(idle.image_url)} alt="" data-testid="bible-idle-image" className="absolute inset-0 h-full w-full object-cover" />
    )}
    {!idle?.image_url && (
      <div className="fade-in relative">
        <div className="mx-auto mb-[4vmin] h-[0.5vmin] w-[10vmin] bg-amber-500" />
        <h1 className="font-display font-black tracking-tight" style={{ fontSize: "11vmin" }} data-testid="bible-idle-title">
          {idle?.title || "Welcome"}
        </h1>
        {idle?.subtitle && (
          <p className="mt-[2vmin] text-slate-400" style={{ fontSize: "3.6vmin" }} data-testid="bible-idle-subtitle">{idle.subtitle}</p>
        )}
      </div>
    )}
  </div>
);

export default function BibleDisplay() {
  const { data, status } = useLiveChannel("bible");
  const live = data?.mode === "passage" && data.slide;

  return (
    <div className="relative" data-testid="bible-display" data-mode={live ? "passage" : "idle"}>
      {live ? (
        <div className="bible-screen">
          <FitText text={data.slide.verse_text} />
          <footer className="mt-[3vmin] flex items-end justify-between gap-6 border-t border-[#222B3E] pt-[2.5vmin]">
            <span className="bible-ref" data-testid="bible-reference">{data.slide.reference_label}</span>
            <span className="bible-meta flex items-center gap-[2vmin] font-semibold">
              {data.translation_code && <span data-testid="bible-translation-badge" className="font-display tracking-widest">{data.translation_code}</span>}
              {data.total > 1 && <span data-testid="bible-slide-counter" className="font-mono-ui">{data.slide_index + 1} / {data.total}</span>}
            </span>
          </footer>
        </div>
      ) : (
        <IdleSlide idle={data?.idle} />
      )}
      <WsStatus status={status} subtle className="absolute left-3 bottom-3 z-10" />
    </div>
  );
}
