import { Link } from "react-router-dom";
import { BookOpen, Users, MonitorPlay, SlidersHorizontal, Palette } from "lucide-react";

const LINKS = [
  { to: "/register", label: "Register Display", desc: "Attendance and offering screen", icon: MonitorPlay, id: "register" },
  { to: "/register-admin", label: "Register Admin", desc: "Enter service numbers (PIN)", icon: Users, id: "register-admin" },
  { to: "/bible", label: "Bible Display", desc: "Scripture screen for the sermon", icon: BookOpen, id: "bible" },
  { to: "/bible-admin", label: "Bible Admin", desc: "Prepare and present scripture (PIN)", icon: SlidersHorizontal, id: "bible-admin" },
  { to: "/settings-admin", label: "Display Settings", desc: "Backgrounds, colors and admin PIN (PIN)", icon: Palette, id: "settings-admin" },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-[#090B10] px-6 py-16 md:px-16">
      <div className="max-w-5xl rise-in">
        <p className="label-caps text-amber-400">Local church display system</p>
        <h1 className="font-display mt-3 text-4xl font-black tracking-tight sm:text-5xl lg:text-6xl">Sanctuary Screens</h1>
        <p className="mt-4 max-w-xl text-base text-slate-400 md:text-lg">
          Open a display on each screen, then control it from its admin page.
        </p>
      </div>
      <div className="mt-14 grid max-w-5xl gap-4 sm:grid-cols-2">
        {LINKS.map(({ to, label, desc, icon: Icon, id }, i) => (
          <Link
            key={to}
            to={to}
            data-testid={`home-link-${id}`}
            style={{ animationDelay: `${80 * i}ms` }}
            className="rise-in group flex items-start gap-4 rounded-xl border border-[#222B3E] bg-[#121620] p-6 transition-colors hover:border-amber-500/60 hover:bg-[#1A202C]"
          >
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-amber-500/10 text-amber-400 transition-transform group-hover:-translate-y-0.5">
              <Icon size={20} />
            </span>
            <span>
              <span className="font-display block text-xl font-bold">{label}</span>
              <span className="mt-1 block text-sm text-slate-400">{desc}</span>
              <span className="font-mono-ui mt-3 block text-xs text-slate-500">{to}</span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
