import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Mail, Save } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { errMsg, settingsApi } from "@/lib/api";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const sel = "mt-2 h-10 w-full rounded-md border border-[#2A3550] bg-[#0B0E14] px-3 text-sm";

const Field = ({ label, children }) => (
  <label className="block"><span className="label-caps">{label}</span>{children}</label>
);

export const BackupSettingsForm = () => {
  const [s, setS] = useState(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(null);
  const set = (k) => (v) => setS((f) => ({ ...f, [k]: v }));
  const inp = (k, props = {}) => (
    <Input value={s[k]} onChange={(e) => set(k)(props.type === "number" ? Number(e.target.value) : e.target.value)}
      data-testid={`backup-${k.replace(/_/g, "-")}-input`} className="mt-2 h-10 bg-[#0B0E14]" {...props} />
  );

  useEffect(() => { settingsApi.get("/backup/settings").then((r) => setS(r.data)).catch((e) => toast.error(errMsg(e))); }, []);
  if (!s) return null;

  const save = async () => {
    setBusy("save");
    try {
      const { data } = await settingsApi.put("/backup/settings", { ...s, smtp_password: password });
      setS(data); setPassword("");
      toast.success("Backup settings saved");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };

  const testEmail = async () => {
    setBusy("test");
    try { await settingsApi.post("/backup/test-email"); toast.success(`Test email sent to ${s.email_to}`); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(null); }
  };

  return (
    <Panel title="Schedule & email" testid="backup-settings-panel">
      <div className="space-y-5">
        <label className="flex items-center justify-between text-sm text-slate-300">
          Weekly automatic backup
          <Switch checked={s.schedule_enabled} onCheckedChange={set("schedule_enabled")} data-testid="backup-schedule-switch" />
        </label>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Day">
            <select value={s.weekday} onChange={(e) => set("weekday")(Number(e.target.value))} data-testid="backup-weekday-select" className={sel}>
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </Field>
          <Field label="Time">{inp("time", { type: "time" })}</Field>
          <Field label="Keep last">{inp("keep", { type: "number", min: 1, max: 100 })}</Field>
        </div>
        <div className="border-t border-[#222B3E] pt-5">
          <label className="flex items-center justify-between text-sm text-slate-300">
            Email each backup to me
            <Switch checked={s.email_enabled} onCheckedChange={set("email_enabled")} data-testid="backup-email-switch" />
          </label>
          <p className="mt-1 text-xs text-slate-500">Uses your own email account (SMTP). For Gmail: smtp.gmail.com, port 587, STARTTLS, your address and a Google app password. Needs internet on the NUC.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="SMTP server">{inp("smtp_host", { placeholder: "smtp.gmail.com" })}</Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Port">{inp("smtp_port", { type: "number" })}</Field>
            <Field label="Security">
              <select value={s.smtp_security} onChange={(e) => set("smtp_security")(e.target.value)} data-testid="backup-security-select" className={sel}>
                <option value="starttls">STARTTLS</option><option value="ssl">SSL</option><option value="none">None</option>
              </select>
            </Field>
          </div>
          <Field label="Username">{inp("smtp_user", { autoComplete: "off" })}</Field>
          <Field label={s.has_password ? "Password (saved – leave blank to keep)" : "Password / app password"}>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" data-testid="backup-smtp-password-input" className="mt-2 h-10 bg-[#0B0E14]" />
          </Field>
          <Field label="From address (optional)">{inp("email_from")}</Field>
          <Field label="Send to">{inp("email_to", { placeholder: "you@example.com" })}</Field>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button onClick={save} disabled={!!busy} data-testid="backup-settings-save-btn">
            {busy === "save" ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save settings
          </Button>
          <Button variant="secondary" onClick={testEmail} disabled={!!busy} data-testid="backup-test-email-btn">
            {busy === "test" ? <Loader2 size={14} className="animate-spin" /> : <Mail size={14} />} Send test email
          </Button>
        </div>
      </div>
    </Panel>
  );
};
