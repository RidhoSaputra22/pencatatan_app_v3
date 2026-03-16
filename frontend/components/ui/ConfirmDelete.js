import React from "react";
import Modal from "./Modal";

/**
 * ConfirmDelete modal styled after ui-laravel/confirm-delete.blade.php
 * @param {object} props
 * @param {boolean} props.open
 * @param {function} props.onCancel
 * @param {function} props.onConfirm
 * @param {string} props.message
 * @param {string} props.title
 * @param {string} props.confirmText
 * @param {string} props.cancelText
 */
export default function ConfirmDelete({
  open,
  onCancel,
  onConfirm,
  message = "Apakah Anda yakin ingin menghapus data ini?",
  title = "Konfirmasi Hapus",
  confirmText = "Hapus",
  cancelText = "Batal",
}) {
  return (
    <Modal open={open} onClose={onCancel} title={title} size="sm">
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-error/10 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-error"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div>
          <p className="py-2 text-base-content/70">{message}</p>
        </div>
      </div>
      <div className="modal-action">
        <button type="button" className="btn" onClick={onCancel}>
          {cancelText}
        </button>
        <button type="button" className="btn btn-error" onClick={onConfirm}>
          {confirmText}
        </button>
      </div>
    </Modal>
  );
}
