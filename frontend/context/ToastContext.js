"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import Toast from "@/components/ui/Toast";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timerRef = useRef(null);

  const clearToasts = useCallback(() => {
    setToasts([]);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const showToast = useCallback(
    (typeOrOptions, message) => {
      const options =
        typeof typeOrOptions === "string"
          ? { type: typeOrOptions, message }
          : typeOrOptions || {};

      const duration = options.duration ?? 4000;

      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      setToasts([
        {
          id: Date.now(),
          type: options.type || options.variant || "info",
          message: options.message || "",
          duration,
          dismissible: options.dismissible,
          className: options.className || "",
        },
      ]);

      timerRef.current = setTimeout(() => {
        setToasts([]);
        timerRef.current = null;
      }, duration);
    },
    [],
  );

  useEffect(() => () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  }, []);

  return (
    <ToastContext.Provider value={{ showToast, clearToasts }}>
      {children}
      <Toast toasts={toasts} position="top-right" duration={4000} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
