import { useState } from "react";
import { toast } from "sonner";
import { KeyRound, Loader2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { clearToken, errMsg, setToken, settingsApi } from "@/lib/api";

const PIN_RE = /^\d{4}$/;

const PinInput = ({ label, value, onChange, testid }) => (
  <label className="block">
    <span className="label-caps">{label}</span>
    <Input
      type="password" inputMode="numeric" autoComplete="off" maxLength={4} value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
      data-testid={testid}
      className="mt-2 h-12 w-40 bg-[#0B0E14] font-mono-ui text-xl tracking-[0.5em]"
    />
  </label>
);

export const PinChangeForm = () => {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const mismatch = confirm.length === 4 && next !== confirm;
  const valid = PIN_RE.test(current) && PIN_RE.test(next) && next === confirm;

  const submit = async (e) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      const { data } = await settingsApi.post("/auth/change-pin", { current_pin: current, new_pin: next });
      setToken("settings", data.token);
      clearToken("register");
      clearToken("bible");
      setCurrent(""); setNext(""); setConfirm("");
      toast.success("PIN changed. Other admin screens will ask for the new PIN.");
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Change admin PIN" testid="pin-change-panel" className="max-w-2xl">
      <form onSubmit={submit} className="space-y-5">
        <p className="text-sm text-slate-400">
          One 4-digit PIN unlocks Register Admin, Bible Admin and Display Settings. Changing it signs out every other admin screen.
        </p>
        <PinInput label="Current PIN" value={current} onChange={setCurrent} testid="current-pin-input" />
        <div className="flex flex-wrap gap-6">
          <PinInput label="New PIN" value={next} onChange={setNext} testid="new-pin-input" />
          <PinInput label="Confirm new PIN" value={confirm} onChange={setConfirm} testid="confirm-pin-input" />
        </div>
        {mismatch && <p className="text-xs text-rose-400" data-testid="pin-mismatch-error">New PINs do not match.</p>}
        <Button type="submit" disabled={!valid || busy} data-testid="change-pin-btn" className="h-11 px-5 font-semibold">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />} Change PIN
        </Button>
        <p className="text-xs text-slate-500">
          The PIN set here is kept through restarts and upgrades. To reset a forgotten PIN on the NUC, run <code className="font-mono-ui text-amber-300">./upgrade.sh --reset-pin</code> (or change ADMIN_PIN in .env and restart).
        </p>
      </form>
    </Panel>
  );
};
