// Row of small slide details (translation label, slide counter) at the top or bottom of a verse slide.
export const SlideMeta = ({ place, appearance: a, translationCode, counter }) => {
  const slots = { left: [], center: [], right: [] };
  if (translationCode && a?.translation_show !== false) {
    const [vert, horiz] = (a?.translation_position || "bottom-right").split("-");
    if (vert === place) {
      slots[horiz].push(
        <span key="t" data-testid="bible-translation-badge" data-position={a?.translation_position} className="font-display tracking-widest">
          {translationCode}
        </span>,
      );
    }
  }
  if (place === "bottom" && counter) {
    slots.right.push(<span key="c" data-testid="bible-slide-counter" className="font-mono-ui">{counter}</span>);
  }
  if (!slots.left.length && !slots.center.length && !slots.right.length) return null;
  return (
    <div className={`bible-meta grid grid-cols-3 items-center font-semibold ${place === "top" ? "mb-[2vmin]" : "mt-[2.5vmin]"}`} data-testid={`bible-meta-${place}`}>
      <div className="flex items-center gap-[2vmin] justify-self-start">{slots.left}</div>
      <div className="flex items-center gap-[2vmin] justify-self-center">{slots.center}</div>
      <div className="flex items-center gap-[2vmin] justify-self-end">{slots.right}</div>
    </div>
  );
};
