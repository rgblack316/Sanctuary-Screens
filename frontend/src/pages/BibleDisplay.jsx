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
function FitText({ text, reference }) {
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
    if (!box || !el || !group) return;
    let s = baseSize(text.length);
    el.style.fontSize = `${s}vmin`;
    while (s > 1.6 && (group.scrollHeight > box.clientHeight || el.scrollWidth > box.clientWidth)) {
      s *= 0.93;
      el.style.fontSize = `${s}vmin`;
    }
    setSize(s);
  }, [text, tick]);

  return (
    <div ref={boxRef} className="bible-text-box">
      <div ref={groupRef} className="flex max-h-full flex-col items-center fade-in" key={`${reference}-${text}`}>
        <span className="bible-ref mb-[3vmin] text-center" data-testid="bible-reference">{reference}</span>
        <p ref={textRef} data-testid="bible-verse-text" className="bible-text" style={{ fontSize: `${size}vmin` }}>
          {text}
        </p>
      </div>
    </div>
  );
}

const IdleSlide = ({ idle, appearance, churchName, logoUrl }) => (
  <div className="bible-screen items-center justify-center text-center" data-testid="bible-idle-slide">
    <DisplayBackground appearance={appearance} />
    {idle?.image_url && (
      <img src={assetUrl(idle.image_url)} alt="" data-testid="bible-idle-image" className="absolute inset-0 h-full w-full object-cover" />
    )}
    {!idle?.image_url && <IdleWelcome idle={idle} appearance={appearance} churchName={churchName} logoUrl={logoUrl} />}
  </div>
);

export default function BibleDisplay() {
  const { data: live, status } = useLiveChannel("bible");
  const preview = usePreview();
  const data = preview?.sample ? { ...live, ...SAMPLE } : live;
  const appearance = preview?.appearance || live?.appearance;
  const churchName = preview ? preview.church_name : live?.church_name;
  const logoUrl = preview ? preview.church_logo_url : live?.church_logo_url;
  const active = data?.mode === "passage" && data.slide;

  return (
    <div className="relative" data-testid="bible-display" data-mode={active ? "passage" : "idle"} style={appearanceVars(appearance)}>
      {active ? (
        <div className="bible-screen">
          <DisplayBackground appearance={appearance} />
          <ChurchName name={churchName} logoUrl={logoUrl} appearance={appearance} place="top" />
          <SlideMeta place="top" appearance={appearance} translationCode={data.translation_code} />
          <FitText text={data.slide.verse_text} reference={data.slide.reference_label} />
          <SlideMeta place="bottom" appearance={appearance} translationCode={data.translation_code}
            counter={data.total > 1 ? `${data.slide_index + 1} / ${data.total}` : null} />
          <div className="mt-[2vmin]"><ChurchName name={churchName} logoUrl={logoUrl} appearance={appearance} place="bottom" /></div>
        </div>
      ) : (
        <IdleSlide idle={data?.idle} appearance={appearance} churchName={churchName} logoUrl={logoUrl} />
      )}
      <WsStatus status={status} subtle className="absolute left-3 bottom-3 z-10" />
    </div>
  );
}
