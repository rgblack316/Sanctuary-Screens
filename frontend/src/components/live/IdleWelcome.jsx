import { useEffect, useState } from "react";
import { assetUrl } from "@/lib/api";

const today = () =>
  new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });

function useToday() {
  const [value, setValue] = useState(today());
  useEffect(() => {
    const t = setInterval(() => setValue(today()), 60000);
    return () => clearInterval(t);
  }, []);
  return value;
}

// Centered idle welcome: optional logo, "Welcome to <Church Name>", today's date, optional subtitle.
export const IdleWelcome = ({ idle, appearance: a, churchName, logoUrl }) => {
  const date = useToday();
  const showName = a?.church_name_show !== false && churchName?.trim();
  const logo = a?.church_name_show !== false && a?.church_logo_show && logoUrl;
  return (
    <div className="fade-in flex max-w-[88vw] flex-col items-center">
      {logo && (
        <img src={assetUrl(logoUrl)} alt="" data-testid="bible-idle-logo" className="mb-[4vmin] object-contain"
          style={{ height: `${6 + (a.church_logo_size || 5) * 1.6}vmin`, maxWidth: "40vw" }} />
      )}
      {showName ? (
        <>
          <p className="font-display font-bold ss-text" style={{ fontSize: "5.5vmin" }} data-testid="bible-idle-title">
            {idle?.title || "Welcome"} to
          </p>
          <h1
            data-testid="bible-idle-church-name"
            className="mt-[1.5vmin] font-display font-black leading-[1.05] tracking-tight"
            style={{
              fontSize: churchName.length > 28 ? "7.5vmin" : "9.5vmin",
              color: a?.church_name_color || "var(--ss-text)",
              textTransform: a?.church_name_uppercase ? "uppercase" : "none",
              letterSpacing: a?.church_name_uppercase ? "0.04em" : "-0.01em",
              textWrap: "balance",
            }}
          >
            {churchName}
          </h1>
        </>
      ) : (
        <h1 className="font-display font-black tracking-tight ss-text" style={{ fontSize: "11vmin" }} data-testid="bible-idle-title">
          {idle?.title || "Welcome"}
        </h1>
      )}
      <p className="mt-[3.5vmin] font-semibold ss-muted" style={{ fontSize: "3.6vmin" }} data-testid="bible-idle-date">{date}</p>
      {idle?.subtitle && (
        <p className="mt-[1.5vmin] ss-muted" style={{ fontSize: "3vmin" }} data-testid="bible-idle-subtitle">{idle.subtitle}</p>
      )}
    </div>
  );
};
