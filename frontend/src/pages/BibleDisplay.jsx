import { useLayoutEffect, useRef, useState } from "react";
import { useLiveChannel } from "@/hooks/useLiveChannel";
import { usePreview } from "@/hooks/usePreview";
import { WsStatus } from "@/components/live/WsStatus";
import { DisplayBackground, appearanceVars } from "@/components/live/DisplayBackground";
import { assetUrl } from "@/lib/api";

const SAMPLE = {
  mode: "passage", translation_code: "KJV", slide_index: 0, total: 3,
  slide: {
    reference_label: "John 3:16",
    verse_text: "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
  },
};

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

const IdleSlide = ({ idle, appearance }) => (
  <div className="bible-screen items-center justify-center text-center" data-testid="bible-idle-slide">
    <DisplayBackground appearance={appearance} />
    {idle?.image_url && (
      <img src={assetUrl(idle.image_url)} alt="" data-testid="bible-idle-image" className="absolute inset-0 h-full w-full object-cover" />
    )}
    {!idle?.image_url && (
      <div className="fade-in relative">
        <div className="mx-auto mb-[4vmin] h-[0.5vmin] w-[10vmin]" style={{ background: "var(--ss-accent, #f59e0b)" }} />
        <h1 className="font-display font-black tracking-tight ss-text" style={{ fontSize: "11vmin" }} data-testid="bible-idle-title">
          {idle?.title || "Welcome"}
        </h1>
        {idle?.subtitle && (
          <p className="mt-[2vmin] ss-muted" style={{ fontSize: "3.6vmin" }} data-testid="bible-idle-subtitle">{idle.subtitle}</p>
        )}
      </div>
    )}
  </div>
);

export default function BibleDisplay() {
  const { data: live, status } = useLiveChannel("bible");
  const preview = usePreview();
  const data = preview?.sample ? { ...live, ...SAMPLE } : live;
  const appearance = preview?.appearance || live?.appearance;
  const active = data?.mode === "passage" && data.slide;

  return (
    <div className="relative" data-testid="bible-display" data-mode={active ? "passage" : "idle"} style={appearanceVars(appearance)}>
      {active ? (
        <div className="bible-screen">
          <DisplayBackground appearance={appearance} />
          <FitText text={data.slide.verse_text} />
          <footer className="bible-footer mt-[3vmin] flex items-end justify-between gap-6 pt-[2.5vmin]">
            <span className="bible-ref" data-testid="bible-reference">{data.slide.reference_label}</span>
            <span className="bible-meta flex items-center gap-[2vmin] font-semibold">
              {data.translation_code && <span data-testid="bible-translation-badge" className="font-display tracking-widest">{data.translation_code}</span>}
              {data.total > 1 && <span data-testid="bible-slide-counter" className="font-mono-ui">{data.slide_index + 1} / {data.total}</span>}
            </span>
          </footer>
        </div>
      ) : (
        <IdleSlide idle={data?.idle} appearance={appearance} />
      )}
      <WsStatus status={status} subtle className="absolute left-3 bottom-3 z-10" />
    </div>
  );
}
