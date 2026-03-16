import React from "react";

/**
 * Modal component styled after ui-laravel/modal.blade.php
 * @param {object} props
 * @param {boolean} props.open
 * @param {function} props.onClose
 * @param {string} props.title
 * @param {string} props.size (sm|md|lg|xl)
 * @param {boolean} props.closeButton
 * @param {React.ReactNode} props.children
 * @param {React.ReactNode} props.actions
 */
export default function Modal({
  open,
  onClose,
  title = null,
  size = "lg",
  closeButton = true,
  children,
  actions = null,
  ...rest
}) {
  const sizeClass =
    {
      sm: "max-w-sm",
      lg: "max-w-lg",
      lg: "max-w-3xl",
      xl: "max-w-5xl",
    }[size] || "max-w-lg";

  if (!open) return null;

  return (
    <div
      className="modal modal-open modal-bottom sm:modal-middle"
      tabIndex={-1}
      {...rest}
    >
      <div className={`modal-box ${sizeClass}`}>
        {(title || closeButton) && (
          <div className="flex justify-between items-center mb-4">
            {title && <h3 className="font-bold text-lg">{title}</h3>}
            {closeButton && (
              <button
                className="btn btn-sm btn-circle btn-ghost"
                onClick={onClose}
                aria-label="Close"
              >
                &times;
              </button>
            )}
          </div>
        )}
        {children}
        {actions && <div className="modal-action">{actions}</div>}
      </div>
      {/* backdrop */}
      <div className="modal-backdrop" onClick={onClose} />
    </div>
  );
}
