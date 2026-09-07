import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { applyTheme } from "../utils/theme";

const STORAGE_KEY = "app_settings";

const DEFAULT_SETTINGS = {
  theme: "system",
  autoRefresh: { interval: 30000 },
  defaultDateRange: "3M",
};

function loadSettingsFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const merged = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    // 얕은 병합이라 저장된 값이 { autoRefresh: null } 같은 손상된 모양이면 중첩 필드가
    // 통째로 사라질 수 있다 — 여기서 한 번에 검증해 컴포넌트마다 방어 코드를 두지 않게 한다.
    if (typeof merged.autoRefresh?.interval !== "number") {
      merged.autoRefresh = DEFAULT_SETTINGS.autoRefresh;
    }
    return merged;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettingsToStorage(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // localStorage를 쓸 수 없는 환경(프라이빗 브라우징 등)에서는 조용히 무시한다.
  }
}

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(() => {
    const initial = loadSettingsFromStorage();
    applyTheme(initial.theme);
    return initial;
  });

  useEffect(() => {
    saveSettingsToStorage(settings);
    applyTheme(settings.theme);
  }, [settings]);

  useEffect(() => {
    if (settings.theme !== "system") return undefined;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => applyTheme("system");
    if (media.addEventListener) {
      media.addEventListener("change", handleChange);
      return () => media.removeEventListener("change", handleChange);
    }
    media.addListener(handleChange);
    return () => media.removeListener(handleChange);
  }, [settings.theme]);

  const updateSettings = useCallback((key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, resetSettings }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings는 SettingsProvider 안에서만 사용할 수 있습니다.");
  return ctx;
}
