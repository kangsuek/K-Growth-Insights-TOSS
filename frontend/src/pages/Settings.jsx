import GeneralSettingsPanel from "../components/settings/GeneralSettingsPanel";
import WatchlistManagementPanel from "../components/settings/WatchlistManagementPanel";
import DataManagementPanel from "../components/settings/DataManagementPanel";

export default function Settings() {
  return (
    <div className="animate-fadeIn max-w-2xl flex flex-col gap-6">
      <h2 className="text-xl font-bold">설정</h2>
      <GeneralSettingsPanel />
      <WatchlistManagementPanel />
      <DataManagementPanel />
    </div>
  );
}
