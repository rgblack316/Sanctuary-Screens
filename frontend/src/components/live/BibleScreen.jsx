import { useLayoutEffect, useRef, useState } from "react";
import { useLiveChannel } from "@/hooks/useLiveChannel";
import { usePreview } from "@/hooks/usePreview";
import { WsStatus } from "@/components/live/WsStatus";
import { DisplayBackground, ChurchName, appearanceVars } from "@/components/live/DisplayBackground";
import { assetUrl } from "@/lib/api";
import { IdleWelcome } from "@/components/live/IdleWelcome";
import { SlideMeta } from "@/components/live/SlideMeta";

const SAMPLE = {
  mode: "passage", translation_code: "KJV", slide_index: 0, total: 3,
  slide: {
    reference_label: "John 3:16",
    verse_text: "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
  },
};

const baseSize = (n) => (n < 80 ? 8 : n < 160 ? 6.6 : n < 280 ? 5.4 : n < 420 ? 4.6 : n < 600 ? 3.9 : 3.3);

// Shrinks the reference + verse group until it fits the box (handles very long verses on small screens).
function FitText({ text, reference, scale = 1, refSize, custom }) {
  const boxRef = useRef(null);
  const groupRef = useRef(null);
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
    const group = groupRef.current;
    const el = textRef.current;
    if (!box || !group) return;
    if (!el) {
      let r = 1;
      const refEl = group.firstChild;
      refEl.style.fontSize = "";
      while (r > 0.3 && (group.scrollHeight > box.clientHeight || refEl.scrollWidth > box.clientWidth)) {
        r *= 0.93;
        refEl.style.fontSize = `calc(var(--ss-ref-solo-size) * ${r})`;
      }
      return;
    }
    let s = baseSize(text.length) * scale;
    el.style.fontSize = `${s}vmin`;
    while (s > 1.6 && (group.scrollHeight > box.clientHeight || el.scrollWidth > box.clientWidth)) {
      s *= 0.93;
      el.style.fontSize = `${s}vmin`;
    }
    setSize(s);
  }, [text, tick, scale, refSize]);

  return (
    <div ref={boxRef} className="bible-text-box">
      <div ref={groupRef} className="flex max-h-full flex-col items-center fade-in" key={`${reference}-${text}`}>
        <span className={`bible-ref text-center ${text ? "mb-[3vmin]" : "bible-ref-solo"}`} data-testid="bible-reference">{reference}</span>
        {text && (
          <p ref={textRef} data-testid="bible-verse-text" className={`bible-text ${custom ? "whitespace-pre-line" : ""}`} style={{ fontSize: `${size}vmin` }}>
            {text}
          </p>
        )}
      </div>
    </div>
  );
}

const IdleSlide = ({ idle, appearance, churchName, logoUrl }) => (
  <div className="bible-screen items-center justify-center text-center" data-testid="bible-idle-slide">
    {idle?.image_url && (
      <img src={assetUrl(idle.image_url)} alt="" data-testid="bible-idle-image" className="absolute inset-0 h-full w-full object-cover" />
    )}
    {!idle?.image_url && <IdleWelcome idle={idle} appearance={appearance} churchName={churchName} logoUrl={logoUrl} />}
  </div>
);

const PreviewEmpty = ({ appearance }) => (
  <div className="bible-screen items-center justify-center text-center" data-testid="preview-empty">
    <p className="relative z-10 max-w-[70vmin] text-[3.2vmin] text-slate-300">
      Nothing in preview yet.<br /><span className="text-slate-500">Look up or load a slide in Bible Admin and it will appear here.</span>
    </p>
  </div>
);

export function BibleScreen({ channel = "bible" }) {
  const isPreview = channel === "preview";
  const { data: live, status } = useLiveChannel(channel);
  const preview = usePreview();
  const data = preview?.sample ? { ...live, ...SAMPLE } : live;
  const appearance = preview?.appearance || live?.appearance;
  const churchName = preview ? preview.church_name : live?.church_name;
  const logoUrl = preview ? preview.church_logo_url : live?.church_logo_url;
  const hideName = !!appearance?.church_name_hide_on_slides;
  const active = data?.mode === "passage" && data.slide;

  return (
    <div className="bible-root relative" data-testid={isPreview ? "bible-preview" : "bible-display"} data-mode={active ? "passage" : "idle"} style={appearanceVars(appearance)}>
      {/* One persistent background so the parallax drift never restarts when switching slides. */}
      <DisplayBackground appearance={appearance} />
      {active ? (
        <div className="bible-screen">
                {!hideName && <ChurchName name={churchName} logoUrl={logoUrl} appearance={appearance} place="top" />}
          <SlideMeta place="top" appearance={appearance} translationCode={data.translation_code} />
          <FitText text={data.slide.verse_text} reference={data.slide.reference_label}
            scale={0.6 + (appearance?.verse_size ?? 5) * 0.08} refSize={appearance?.reference_size} custom={data.source_type === "custom"} />
          <SlideMeta place="bottom" appearance={appearance} translationCode={data.translation_code}
            counter={data.total > 1 ? `${data.slide_index + 1} / ${data.total}` : null} />
          {!hideName && <div className="mt-[2vmin]"><ChurchName name={churchName} logoUrl={logoUrl} appearance={appearance} place="bottom" /></div>}
        </div>
      ) : isPreview ? (
        <PreviewEmpty appearance={appearance} />
      ) : (
        <IdleSlide idle={data?.idle} appearance={appearance} churchName={churchName} logoUrl={logoUrl} />
      )}
      {isPreview && (
        <span data-testid="preview-badge" className="pointer-events-none absolute right-3 top-3 z-20 rounded-full bg-sky-500 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-[#04121c] shadow-lg">
          Preview · not on screen
        </span>
      )}
      <WsStatus status={status} subtle className="absolute left-3 bottom-3 z-10" />
    </div>
  );
}
