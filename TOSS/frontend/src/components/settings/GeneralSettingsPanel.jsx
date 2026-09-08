import { useState } from "react";
import { useSettings } from "../../contexts/SettingsContext";

const THEME_OPTIONS = [
  { value: "light", label: "라이트" },
  { value: "dark", label: "다크" },
  { value: "system", label: "시스템 설정 따르기" },
];

const REFRESH_OPTIONS = [
  { value: 10000, label: "10초" },
  { value: 30000, label: "30초" },
  { value: 60000, label: "60초" },
];

const DATE_RANGE_OPTIONS = [
  { value: "1M", label: "1개월" },
  { value: "3M", label: "3개월" },
  { value: "6M", label: "6개월" },
];

export default function GeneralSettingsPanel() {
  const { settings, updateSettings, resetSettings } = useSettings();
  const [confirmingReset, setConfirmingReset] = useState(false);

  return (
    <div className="card-bordered">
      <h3 className="font-semibold mb-3">일반</h3>

      <div className="mb-4">
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">테마</p>
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

      <div className="mb-4">
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">자동 새로고침 간격</p>
        <select
          className="input w-auto"
          value={settings.autoRefresh.interval}
          onChange={(e) => updateSettings("autoRefresh", { interval: Number(e.target.value) })}
        >
          {REFRESH_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mb-4">
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">기본 조회 기간(캔들/매매동향)</p>
        <select
          className="input w-auto"
          value={settings.defaultDateRange}
          onChange={(e) => updateSettings("defaultDateRange", e.target.value)}
        >
          {DATE_RANGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {confirmingReset ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-danger-600 dark:text-danger-400">
            테마·새로고침 간격·조회 기간을 기본값으로 되돌립니다(종목·수집 데이터는 유지).
          </span>
          <button
            className="btn-danger px-2 py-1 text-xs shrink-0"
            onClick={() => {
              resetSettings();
              setConfirmingReset(false);
            }}
          >
            확인
          </button>
          <button className="btn px-2 py-1 text-xs shrink-0" onClick={() => setConfirmingReset(false)}>
            취소
          </button>
        </div>
      ) : (
        <button className="btn px-3 py-1.5 text-sm" onClick={() => setConfirmingReset(true)}>
          기본값으로 초기화
        </button>
      )}
    </div>
  );
}
