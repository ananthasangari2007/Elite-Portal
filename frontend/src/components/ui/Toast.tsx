import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

type ToastKind = "success" | "error" | "info";
type Toast = { id: number; kind: ToastKind; message: string };

const ToastContext = createContext<{ push: (message: string, kind?: ToastKind) => void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((message: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, kind, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4200);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex w-[min(92vw,22rem)] flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`card flex items-start gap-3 p-4 shadow-soft border-l-4 ${
              toast.kind === "success"
                ? "border-l-emerald-500"
                : toast.kind === "error"
                ? "border-l-red-500"
                : "border-l-brand-500"
            }`}
          >
            {toast.kind === "success" && <CheckCircle2 className="h-5 w-5 text-emerald-500 mt-0.5 shrink-0" />}
            {toast.kind === "error" && <XCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />}
            {toast.kind === "info" && <Info className="h-5 w-5 text-brand-500 mt-0.5 shrink-0" />}
            <p className="text-sm text-slate-700 flex-1">{toast.message}</p>
            <button onClick={() => dismiss(toast.id)} className="text-slate-400 hover:text-slate-600">
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
