import React, { useEffect, useState } from "react";
import Alert from "./Alert";

/**
 * Toast notification container styled after ui-laravel/toast.blade.php
 * Usage: <Toast toasts={[{type: 'success', message: 'Berhasil!'}]} />
 * type: success | error | warning | info
 */
export default function Toast({ toasts = [] }) {
  const [visible, setVisible] = useState([]);

  useEffect(() => {
    setVisible(toasts.map(() => true));
    if (toasts.length > 0) {
      const timers = toasts.map((_, i) =>
        setTimeout(
          () =>
            setVisible((v) => v.map((val, idx) => (idx === i ? false : val))),
          5000,
        ),
      );
      return () => timers.forEach(clearTimeout);
    }
  }, [toasts]);

  if (!toasts.length) return null;

  return (
    <div className="toast toast-end toast-bottom z-[9999]">
      {toasts.map((t, i) =>
        visible[i] ? (
          <Alert key={i} type={t.type || "info"} className="max-w-sm">
            {t.message}
          </Alert>
        ) : null,
      )}
    </div>
  );
}
