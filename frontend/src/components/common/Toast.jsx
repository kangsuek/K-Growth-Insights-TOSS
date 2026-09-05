import { useToast } from "../../contexts/ToastContext";

const STYLES = {
  success: "bg-success-50 text-success-700 border-success-200 dark:bg-success-900/30 dark:text-success-400 dark:border-success-800",
  error: "bg-danger-50 text-danger-700 border-danger-200 dark:bg-danger-900/30 dark:text-danger-400 dark:border-danger-800",
  warning: "bg-warning-50 text-warning-700 border-warning-200 dark:bg-warning-900/30 dark:text-warning-400 dark:border-warning-800",
  info: "bg-info-50 text-info-700 border-info-200 dark:bg-info-900/30 dark:text-info-400 dark:border-info-800",
};

const ICONS = {
  success: "✓",
  error: "✕",
  warning: "!",
  info: "i",
};

export default function Toast({ id, message, type = "info" }) {
  const { removeToast } = useToast();

  return (
    <div
      className={`flex items-center gap-3 min-w-[280px] max-w-md p-4 rounded-lg shadow-lg border animate-slide-in ${STYLES[type] || STYLES.info}`}
    >
      <span aria-hidden="true">{ICONS[type] || ICONS.info}</span>
      <span className="flex-1 text-sm">{message}</span>
      <button onClick={() => removeToast(id)} aria-label="닫기" className="text-sm opacity-60 hover:opacity-100">
        ✕
      </button>
    </div>
  );
}
