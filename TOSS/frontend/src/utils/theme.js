const STORAGE_KEY = "app_settings";

export function getSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function getEffectiveTheme(theme) {
  return theme === "system" ? getSystemTheme() : theme;
}

export function applyTheme(theme) {
  const effective = getEffectiveTheme(theme);
  document.documentElement.classList.remove("dark");
  if (effective === "dark") {
    document.documentElement.classList.add("dark");
  }
}

export function readStoredTheme() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return "system";
    const parsed = JSON.parse(raw);
    return parsed?.theme || "system";
  } catch {
    return "system";
  }
}
