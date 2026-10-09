import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PinGate } from "@/components/live/PinGate";
import { AdminShell } from "@/components/AdminShell";
import { AppearanceEditor } from "@/components/settings/AppearanceEditor";
import { PinChangeForm } from "@/components/settings/PinChangeForm";
import { BackupSettingsForm } from "@/components/settings/BackupSettingsForm";
import { BackupList } from "@/components/settings/BackupList";

function SettingsConsole() {
  const [tab, setTab] = useState("bible");
  return (
    <AdminShell area="settings" title="Display Settings">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-6 bg-[#121620]">
          <TabsTrigger value="bible" data-testid="settings-tab-bible">Bible display</TabsTrigger>
          <TabsTrigger value="register" data-testid="settings-tab-register">Register display</TabsTrigger>
          <TabsTrigger value="security" data-testid="settings-tab-security">Admin PIN</TabsTrigger>
          <TabsTrigger value="backup" data-testid="settings-tab-backup">Backups</TabsTrigger>
        </TabsList>
        <TabsContent value="bible"><AppearanceEditor display="bible" /></TabsContent>
        <TabsContent value="register"><AppearanceEditor display="register" /></TabsContent>
        <TabsContent value="security"><PinChangeForm /></TabsContent>
        <TabsContent value="backup">
          <div className="grid gap-8 lg:grid-cols-2"><BackupList /><BackupSettingsForm /></div>
        </TabsContent>
      </Tabs>
    </AdminShell>
  );
}

export default function SettingsAdmin() {
  return (
    <PinGate area="settings">
      <SettingsConsole />
    </PinGate>
  );
}
