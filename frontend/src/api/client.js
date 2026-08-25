const ADMIN_STORAGE_KEY = "nexa_admin_key";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const ERROR_MESSAGES = {
  "Order not found": "Заказ не найден. Проверьте ссылку или номер заказа.",
  "Unknown service": "Сервис этого заказа больше не доступен.",
  "Invalid plan selection": "Выбранный тариф или период недоступен.",
  "Unknown status": "Неизвестный статус заказа.",
  "Invalid admin key": "Неверный ключ администратора.",
  "Service not found": "Сервис не найден.",
  "Service slug already exists": "Сервис с таким slug уже существует.",
  "A service with this slug already exists": "Сервис с таким slug уже существует.",
  "Catalog changed": "Каталог был обновлён. Проверьте тариф и период ещё раз.",
  "Access token is required for this service and is not stored after validation":
    "Для этого сервиса нужны временные данные доступа. Они используются только при отправке и не сохраняются.",
};

export const STATUSES = ["В работе", "Оплачено", "Отменено", "Ошибка"];

export const EXECUTION_STATUSES = {
  pending: "Ожидает выполнения",
  running: "Выполняется",
  action_required: "Требует действия",
  completed: "Завершено",
  failed: "Ошибка выполнения",
  stopped: "Остановлено",
};

export function getAdminKey() {
  return sessionStorage.getItem(ADMIN_STORAGE_KEY) || "";
}

export function setAdminKey(key) {
  if (key) sessionStorage.setItem(ADMIN_STORAGE_KEY, key);
  else sessionStorage.removeItem(ADMIN_STORAGE_KEY);
}

function errorMessage(detail) {
  if (typeof detail === "string") return ERROR_MESSAGES[detail] || detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg || item?.message).filter(Boolean);
    if (messages.length) return messages.join(" · ");
  }
  if (detail && typeof detail === "object") {
    return detail.message || detail.error || "Проверьте заполнение формы.";
  }
  return "Не удалось выполнить запрос.";
}

async function request(path, { method = "GET", body, admin = false, signal } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (admin) headers["X-Admin-Key"] = getAdminKey();

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new Error("Не удалось связаться с сервером. Проверьте, запущен ли API.");
  }

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const data = await response.json();
      detail = data.detail ?? data.error ?? data.message ?? detail;
    } catch {
      /* The status code is still retained below. */
    }
    const error = new Error(errorMessage(detail));
    error.status = response.status;
    error.detail = detail;
    throw error;
  }

  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function requestAny(paths, options) {
  let lastError;
  for (const path of paths) {
    try {
      return await request(path, options);
    } catch (error) {
      lastError = error;
      if (![404, 405].includes(error.status)) throw error;
    }
  }
  throw lastError;
}

function listFrom(data, keys = ["items", "services", "orders", "categories"]) {
  if (Array.isArray(data)) return data;
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key];
  }
  return [];
}

const publicServicePaths = (identifier, tail = "") => {
  const value = encodeURIComponent(identifier);
  return [
    `/api/catalog/services/${value}${tail}`,
    `/api/services/${value}${tail}`,
    `/services/${value}${tail}`,
  ];
};

const adminServicePaths = (identifier = "") => {
  const suffix = identifier ? `/${encodeURIComponent(identifier)}` : "";
  return [`/api/admin/services${suffix}`, `/api/admin/catalog/services${suffix}`];
};

export const api = {
  catalog: async () => listFrom(await request("/api/catalog/services")),
  catalogService: (identifier, options) => requestAny(publicServicePaths(identifier), options),
  catalogFields: async (identifier, options) =>
    listFrom(await requestAny(publicServicePaths(identifier, "/fields"), options), ["fields", "items"]),
  categories: async () =>
    listFrom(await requestAny(["/api/categories", "/api/catalog/categories"])),

  publicOrder: (id, options) => request(`/api/orders/${encodeURIComponent(id)}`, options),
  submitOrder: (id, payload) =>
    request(`/api/orders/${encodeURIComponent(id)}/submit`, { method: "POST", body: payload }),

  adminHealth: () => request("/api/admin/health", { admin: true }),
  adminOrders: async (params = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.status) query.set("status", params.status);
    const suffix = query.toString() ? `?${query}` : "";
    return listFrom(await request(`/api/admin/orders${suffix}`, { admin: true }), ["orders", "items"]);
  },
  adminOrder: (id) => request(`/api/admin/orders/${encodeURIComponent(id)}`, { admin: true }),
  updateStatus: (id, status) =>
    request(`/api/admin/orders/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: { status },
      admin: true,
    }),
  createOrder: (payload) => request("/api/admin/orders", { method: "POST", body: payload, admin: true }),

  adminCatalog: async () =>
    listFrom(await requestAny(adminServicePaths(), { admin: true })),
  adminService: (identifier) => requestAny(adminServicePaths(identifier), { admin: true }),
  createService: (payload) =>
    requestAny(adminServicePaths(), { method: "POST", body: payload, admin: true }),
  updateService: (identifier, payload) =>
    requestAny(adminServicePaths(identifier), { method: "PUT", body: payload, admin: true }),
  setServiceActive: (identifier, active) =>
    requestAny(
      adminServicePaths(identifier).map((path) => `${path}/active`),
      { method: "PATCH", body: { active }, admin: true }
    ),
  deleteService: (identifier) =>
    requestAny(adminServicePaths(identifier), { method: "DELETE", admin: true }),
  importCatalog: (payload) =>
    requestAny(["/api/admin/services/import", "/api/admin/catalog/import"], {
      method: "POST",
      body: payload,
      admin: true,
    }),
  adminCategories: async () =>
    listFrom(await requestAny(["/api/admin/categories", "/api/categories"], { admin: true })),

  executionStatus: (id) =>
    request(`/api/admin/orders/${encodeURIComponent(id)}/execution-status`, { admin: true }),
  executeOrder: (id) =>
    request(`/api/admin/orders/${encodeURIComponent(id)}/execute`, { method: "POST", admin: true }),
  stopExecution: (id) =>
    request(`/api/admin/orders/${encodeURIComponent(id)}/stop`, { method: "POST", admin: true }),
  retryExecution: (id) =>
    request(`/api/admin/orders/${encodeURIComponent(id)}/retry`, { method: "POST", admin: true }),
};

export function formatMoney(amount, currency = "RUB") {
  const value = Number(amount);
  if (!Number.isFinite(value)) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: currency || "RUB",
      maximumFractionDigits: value % 1 ? 2 : 0,
    }).format(value);
  } catch {
    return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value)} ${currency || ""}`.trim();
  }
}

export function shortOrderId(id) {
  return id ? `#${String(id).slice(0, 8).toUpperCase()}` : "—";
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function executionLabel(value) {
  return EXECUTION_STATUSES[value] || value || EXECUTION_STATUSES.pending;
}

export async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const input = document.createElement("textarea");
  input.value = value;
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.appendChild(input);
  input.select();
  document.execCommand("copy");
  input.remove();
}
