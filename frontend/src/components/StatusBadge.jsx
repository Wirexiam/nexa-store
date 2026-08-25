const CLASS_MAP = {
  "В работе": "st-work",
  "Оплачено": "st-paid",
  "Отменено": "st-cancel",
  "Ошибка": "st-error",
};

export default function StatusBadge({ status, children }) {
  return <span className={`badge ${CLASS_MAP[status] || "st-cancel"}`}>{children || status}</span>;
}
