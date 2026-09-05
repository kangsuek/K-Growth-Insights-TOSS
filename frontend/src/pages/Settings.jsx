import { useSettings } from "../contexts/SettingsContext";

const THEME_OPTIONS = [
  { value: "light", label: "라이트" },
  { value: "dark", label: "다크" },
  { value: "system", label: "시스템 설정 따르기" },
];

export default function Settings() {
  const { settings, updateSettings } = useSettings();

  return (
    <div className="animate-fadeIn max-w-xl">
      <h2 className="text-xl font-bold mb-4">설정</h2>
      <div className="card-bordered">
        <h3 className="font-semibold mb-3">테마</h3>
        <div className="flex flex-col gap-2">
          {THEME_OPTIONS.map((option) => (
            <label key={option.value} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="theme"
                value={option.value}
                checked={settings.theme === option.value}
                onChange={() => updateSettings("theme", option.value)}
                className="accent-primary-500"
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
