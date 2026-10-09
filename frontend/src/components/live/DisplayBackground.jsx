import { assetUrl } from "@/lib/api";

export const hexToRgba = (hex, alpha) => {
  const n = parseInt((hex || "#000000").slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};

// CSS variables consumed by the display stylesheets.
export const appearanceVars = (a) => {
  if (!a) return {};
  const op = a.panel_opacity / 100;
  return {
    "--ss-bg": a.background_color,
    "--ss-text": a.text_color,
    "--ss-accent": a.accent_color,
    "--ss-muted": a.muted_color,
    "--ss-panel": hexToRgba(a.panel_color, op),
    "--ss-border": hexToRgba(a.muted_color, 0.25 * op),
    "--ss-accent-border": hexToRgba(a.accent_color, 0.4 * op),
    "--ss-line": hexToRgba(a.muted_color, 0.3),
  };
};

export const DisplayBackground = ({ appearance: a }) => {
  if (!a?.image_url) return null;
  return (
    <div className="ss-bg-wrap" aria-hidden="true" data-testid="display-background">
      <div
        data-testid="display-background-image"
        data-motion={a.image_motion}
        className={`ss-bg-image ${a.image_motion === "parallax" ? "ss-parallax" : ""}`}
        style={{
          backgroundImage: `url(${assetUrl(a.image_url)})`,
          filter: a.image_blur ? `blur(${a.image_blur}px)` : undefined,
          animationDuration: `${90 - a.motion_speed * 8}s`,
        }}
      />
      <div className="ss-bg-dim" style={{ background: hexToRgba(a.background_color, a.image_dim / 100) }} />
    </div>
  );
};
