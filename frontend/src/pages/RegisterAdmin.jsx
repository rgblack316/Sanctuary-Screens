import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { PinGate } from "@/components/live/PinGate";
import { AdminShell } from "@/components/AdminShell";
import { useLiveChannel } from "@/hooks/useLiveChannel";
import { errMsg, registerApi } from "@/lib/api";
import { ServiceForm } from "@/components/register/ServiceForm";
import { ServiceHistory } from "@/components/register/ServiceHistory";
import { RegisterMirror } from "@/components/register/RegisterMirror";

function RegisterConsole() {
  const { data: live, status } = useLiveChannel("register");
  const [history, setHistory] = useState({ services: [], active_service_date: null });
  const [editing, setEditing] = useState(null);
  const [markedDates, setMarkedDates] = useState([]);

  const load = useCallback(async () => {
    try {
      const [{ data }, { data: d }] = await Promise.all([
        registerApi.get("/register/services"),
        registerApi.get("/register/dates"),
      ]);
      setHistory(data);
      setMarkedDates(d.dates);
    } catch (e) {
      if (e.response?.status !== 401) toast.error(errMsg(e));
    }
  }, []);

  useEffect(() => { load(); }, [load, live]);

  const makeActive = async (service_date) => {
    try {
      await registerApi.post("/register/active", { service_date });
      toast.success("Display switched");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <AdminShell area="register" title="Register Admin" status={status} displayPath="/register">
      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <ServiceForm services={history.services} markedDates={markedDates} live={live} editing={editing} onSaved={load} />
        </div>
        <div className="lg:col-span-5">
          <RegisterMirror live={live} />
        </div>
      </div>
      <ServiceHistory
        services={history.services}
        activeDate={live?.current?.service_date}
        onEdit={setEditing}
        onActivate={makeActive}
      />
    </AdminShell>
  );
}

export default function RegisterAdmin() {
  return (
    <PinGate area="register">
      <RegisterConsole />
    </PinGate>
  );
}
