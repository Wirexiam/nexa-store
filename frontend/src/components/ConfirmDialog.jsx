import { useEffect, useRef } from "react";

export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = "Подтвердить",
  busy = false,
  error = "",
  onConfirm,
  onClose,
}) {
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);
  const returnFocusRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    returnFocusRef.current = document.activeElement;
    const frame = window.requestAnimationFrame(() => cancelRef.current?.focus());

    function onKeyDown(event) {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll("button, a[href], input, select, textarea")]
        .filter((element) => !element.disabled);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKeyDown);
      returnFocusRef.current?.focus?.();
    };
  }, [open, busy, onClose]);

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}
    >
      <section
        className="card modal confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-copy"
        aria-busy={busy}
        ref={dialogRef}
      >
        <span className="confirm-dialog-icon" aria-hidden="true">!</span>
        <h2 id="confirm-dialog-title">{title}</h2>
        <div id="confirm-dialog-copy" className="confirm-dialog-copy">{children}</div>
        {error ? <div className="admin-alert" role="alert">{error}</div> : null}
        <div className="modal-actions">
          <button className="btn secondary" type="button" onClick={onClose} disabled={busy} ref={cancelRef}>
            Отмена
          </button>
          <button className="btn danger-button" type="button" onClick={onConfirm} disabled={busy}>
            {busy ? "Удаляем…" : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
