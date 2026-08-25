import { STATUSES } from "../api/client";

const CLASS_MAP = {
  "В работе": "st-work",
  "Оплачено": "st-paid",
  "Отменено": "st-cancel",
  "Ошибка": "st-error",
};

export default function StatusSelect({ value, onChange, disabled = false, label = "Статус заказа" }) {
  return (
    <span className={`status-control ${CLASS_MAP[value] || "st-cancel"} ${disabled ? "is-busy" : ""}`}>
      <span className="status-dot" aria-hidden="true" />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        aria-label={label}
      >
        {STATUSES.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>
      <span className="select-chevron" aria-hidden="true">⌄</span>
    </span>
  );
}
