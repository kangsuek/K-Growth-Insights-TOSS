import { useToastState } from "../../contexts/ToastContext";
import Toast from "./Toast";

export default function ToastContainer() {
  const { toasts } = useToastState();

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
      {toasts.map((toast) => (
        <Toast key={toast.id} {...toast} />
      ))}
    </div>
  );
}
