import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Lock, Loader2 } from "lucide-react";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { API, clearToken, errMsg, getToken, setToken } from "@/lib/api";

const TITLES = { register: "Register Admin", bible: "Bible Admin" };

function PinForm({ area, onUnlocked }) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (value) => {
    setBusy(true);
    setError("");
    try {
      const { data } = await axios.post(`${API}/auth/unlock`, { pin: value, area });
      setToken(area, data.token);
      onUnlocked();
    } catch (e) {
      setError(errMsg(e, "Unlock failed"));
      setPin("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#090B10] p-4" data-testid="pin-gate">
      <div className="w-full max-w-sm rounded-xl border border-[#222B3E] bg-[#121620] p-8 rise-in">
        <div className="flex items-center gap-3 mb-8">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-amber-500/10 text-amber-400"><Lock size={18} /></span>
          <div>
            <p className="label-caps">Sanctuary Screens</p>
            <h1 className="font-display text-2xl font-bold">{TITLES[area]}</h1>
          </div>
        </div>
        <p className="text-sm text-slate-400 mb-4">Enter the 4-digit admin PIN.</p>
        <InputOTP
          maxLength={4}
          value={pin}
          onChange={setPin}
          onComplete={submit}
          disabled={busy}
          inputMode="numeric"
          pattern="^[0-9]*$"
          autoFocus
          data-testid="pin-input"
        >
          <InputOTPGroup className="gap-3">
            {[0, 1, 2, 3].map((i) => (
              <InputOTPSlot key={i} index={i} className="h-16 w-16 rounded-lg border text-2xl font-display font-bold first:rounded-lg last:rounded-lg border-[#2A3550] bg-[#0B0E14]" />
            ))}
          </InputOTPGroup>
        </InputOTP>
        <div className="mt-5 h-6 text-sm" aria-live="polite">
          {busy && <span className="inline-flex items-center gap-2 text-slate-400"><Loader2 size={14} className="animate-spin" /> Checking…</span>}
          {error && <span data-testid="pin-error" className="text-rose-400">{error}</span>}
        </div>
      </div>
    </div>
  );
}

export const PinGate = ({ area, children }) => {
  const [state, setState] = useState(getToken(area) ? "checking" : "locked");

  const check = useCallback(async () => {
    const token = getToken(area);
    if (!token) return setState("locked");
    try {
      await axios.get(`${API}/auth/check/${area}`, { headers: { Authorization: `Bearer ${token}` } });
      setState("open");
    } catch (e) {
      if (e.response?.status === 401) { clearToken(area); setState("locked"); } else setState("open");
    }
  }, [area]);

  useEffect(() => { check(); }, [check]);
  useEffect(() => {
    const onLock = (e) => e.detail === area && setState("locked");
    window.addEventListener("ss-locked", onLock);
    return () => window.removeEventListener("ss-locked", onLock);
  }, [area]);

  if (state === "checking") return <div className="min-h-screen bg-[#090B10]" />;
  if (state === "locked") return <PinForm area={area} onUnlocked={() => setState("open")} />;
  return children;
};

export const lockArea = (area) => {
  clearToken(area);
  window.dispatchEvent(new CustomEvent("ss-locked", { detail: area }));
};
