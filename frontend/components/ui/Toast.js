import React, { useEffect, useState } from "react";
import Alert from "./Alert";

/**
 * Toast notification container styled after ui-laravel/toast.blade.php
 * Usage: <Toast toasts={[{type: 'success', message: 'Berhasil!'}]} />
 * type: success | error | warning | info
 */
const positionClass = {
  "top-right": "toast-top toast-end",
  "top-left": "toast-top toast-start",
  "bottom-right": "toast-bottom toast-end",
  "bottom-left": "toast-bottom toast-start",
};

export default function Toast({
  toasts = [],
  position = "bottom-right",
  duration = 5000,
  className = "",
}) {
  const [visible, setVisible] = useState([]);

  useEffect(() => {
    setVisible(toasts.map(() => true));
    if (toasts.length > 0) {
      const timers = toasts.map((_, i) =>
        setTimeout(
          () =>
            setVisible((v) => v.map((val, idx) => (idx === i ? false : val))),
          toasts[i]?.duration ?? duration,
        ),
      );
      return () => timers.forEach(clearTimeout);
    }
  }, [toasts, duration]);

  const hasVisibleToast = toasts.some((_, i) => visible[i]);
  if (!toasts.length || !hasVisibleToast) return null;

  return (
    <div
      className={`toast ${positionClass[position] || positionClass["bottom-right"]} z-[9999] ${className}`}
    >
      {toasts.map((t, i) =>
        visible[i] ? (
          <Alert
            key={t.id || i}
            type={t.type || t.variant || "info"}
            dismissible={t.dismissible}
            className={`w-full shadow-lg ${t.className || ""}`}
          >
            {t.message}
          </Alert>
        ) : null,
      )}
    </div>
  );
}
