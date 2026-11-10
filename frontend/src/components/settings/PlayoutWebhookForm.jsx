import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Loader2 } from "lucide-react";
import { Panel } from "@/components/AdminShell";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { errMsg, settingsApi } from "@/lib/api";

const copy = async (text) => {
  try { await navigator.clipboard.writeText(text); toast.success("Copied"); } catch { toast.error("Copy failed. Select the text and copy it."); }
};

export const PlayoutWebhookForm = () => {
  const [cfg, setCfg] = useState(null);
  const [fresh, setFresh] = useState(null); // plain token, shown once
  const [busy, setBusy] = useState(false);
  const url = `${window.location.origin}/api/hooks/bible`;

  const load = useCallback(async () => {
    try { setCfg((await settingsApi.get("/hooks/config")).data); } catch (e) { toast.error(errMsg(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (fn) => {
    setBusy(true);
    try { await fn(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const create = () => run(async () => {
    if (cfg?.enabled && !window.confirm("Make a new token? The old one stops working immediately.")) return;
    const { data } = await settingsApi.post("/hooks/token");
    setFresh(data.token); setCfg(data);
  });
  const revoke = () => run(async () => {
    if (!window.confirm("Turn the webhook off? The playout app will stop being able to change slides.")) return;
    setCfg((await settingsApi.delete("/hooks/token")).data); setFresh(null);
  });
  const setLog = (v) => run(async () => setCfg((await settingsApi.put("/hooks/config", { log_played: v })).data));

  const sample = `curl -X POST ${url} \\\n  -H "Authorization: Bearer ${fresh || "<token>"}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"action":"hymn","songbook":"Baptist Hymnal","title":"Amazing Grace","page":"112"}'`;

  return (
    <Panel title="Playout webhook" testid="playout-webhook-panel">
      {!cfg ? <Loader2 className="animate-spin" /> : (
        <div className="space-y-5 text-sm text-slate-300">
          <p>Lets the church playout app change slides over the LAN. It needs this address and a secret token.</p>
          <div>
            <p className="label-caps">Address</p>
            <div className="mt-1 flex items-center gap-2">
              <code className="rounded bg-[#0B0E14] px-2 py-1.5 font-mono-ui" data-testid="webhook-url">{url}</code>
              <Button size="sm" variant="secondary" onClick={() => copy(url)}><Copy size={14} /></Button>
            </div>
          </div>
          <div>
            <p className="label-caps">Token</p>
            {fresh ? (
              <div className="mt-1 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3" data-testid="webhook-token-box">
                <p className="mb-2 text-amber-300">Copy this now. It is shown only once.</p>
                <div className="flex items-center gap-2">
                  <code className="break-all rounded bg-[#0B0E14] px-2 py-1.5 font-mono-ui" data-testid="webhook-token">{fresh}</code>
                  <Button size="sm" variant="secondary" onClick={() => copy(fresh)}><Copy size={14} /></Button>
                </div>
              </div>
            ) : (
              <p className="mt-1" data-testid="webhook-status">
                {cfg.enabled ? `On · token ending ${cfg.token_hint}` : "Off · no token yet"}
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={create} disabled={busy} data-testid="webhook-create-btn">{cfg.enabled ? "Make a new token" : "Turn on & create token"}</Button>
              {cfg.enabled && <Button size="sm" variant="secondary" onClick={revoke} disabled={busy} data-testid="webhook-revoke-btn">Turn off</Button>}
            </div>
          </div>
          <label className="flex items-center justify-between">
            Add songs sent by the playout to today's Hymns list (marked Played)
            <Switch checked={cfg.log_played} onCheckedChange={setLog} disabled={busy} data-testid="webhook-log-switch" />
          </label>
          <div>
            <p className="label-caps">Example</p>
            <pre className="mt-1 overflow-x-auto rounded bg-[#0B0E14] p-3 text-xs">{sample}</pre>
            <p className="mt-2 text-xs text-slate-500">Other actions: <code>next</code>, <code>prev</code>, <code>clear</code>, and <code>goto</code> with <code>"index": 0</code>.</p>
          </div>
        </div>
      )}
    </Panel>
  );
};
