import { createContext, useCallback, useContext, useMemo, useState } from "react";

const ToastActionsContext = createContext(null);
const ToastStateContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message, type = "info", duration = 3000) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { id, message, type, duration }]);
      if (duration > 0) {
        setTimeout(() => removeToast(id), duration);
      }
      return id;
    },
    [removeToast]
  );

  const actions = useMemo(
    () => ({
      addToast,
      removeToast,
      success: (message, duration) => addToast(message, "success", duration),
      error: (message, duration) => addToast(message, "error", duration),
      warning: (message, duration) => addToast(message, "warning", duration),
      info: (message, duration) => addToast(message, "info", duration),
    }),
    [addToast, removeToast]
  );

  return (
    <ToastActionsContext.Provider value={actions}>
      <ToastStateContext.Provider value={{ toasts }}>{children}</ToastStateContext.Provider>
    </ToastActionsContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastActionsContext);
  if (!ctx) throw new Error("useToast는 ToastProvider 안에서만 사용할 수 있습니다.");
  return ctx;
}

export function useToastState() {
  const ctx = useContext(ToastStateContext);
  if (!ctx) throw new Error("useToastState는 ToastProvider 안에서만 사용할 수 있습니다.");
  return ctx;
}
