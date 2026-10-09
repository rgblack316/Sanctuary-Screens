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

const ALIGN = { left: "left", center: "center", right: "right" };
const JUSTIFY = { left: "flex-start", center: "center", right: "flex-end" };

// Church name + logo row; `place` is "top" or "bottom".
export const ChurchName = ({ name, logoUrl, appearance: a, place }) => {
  const logo = a?.church_logo_show && logoUrl ? logoUrl : null;
  if (!a?.church_name_show || (!name?.trim() && !logo)) return null;
  const [vert, horiz] = a.church_name_position.split("-");
  if (vert !== place) return null;
  return (
    <div
      data-testid={`church-name-${place}`}
      data-position={a.church_name_position}
      className="flex items-center gap-[2vmin] font-display font-bold leading-tight"
      style={{
        justifyContent: JUSTIFY[horiz],
        textAlign: ALIGN[horiz],
        color: a.church_name_color,
        fontSize: `${1.6 + a.church_name_size * 0.55}vmin`,
        textTransform: a.church_name_uppercase ? "uppercase" : "none",
        letterSpacing: a.church_name_uppercase ? "0.14em" : "0.01em",
      }}
    >
      {logo && (
        <img src={assetUrl(logo)} alt="" data-testid={`church-logo-${place}`} className="shrink-0 object-contain"
          style={{ height: `${2 + a.church_logo_size * 1.2}vmin`, maxWidth: "30vw" }} />
      )}
      {name?.trim() && <span>{name}</span>}
    </div>
  );
};
