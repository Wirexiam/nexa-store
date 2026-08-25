import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import ExecutionBadge from "../components/ExecutionBadge";
import ServiceMark from "../components/ServiceMark";
import StatusSelect from "../components/StatusSelect";
import {
  STATUSES,
  api,
  copyText,
  formatDate,
  formatMoney,
  shortOrderId,
} from "../api/client";
import {
  priceFor,
  serviceCategory,
  serviceLogo,
  servicePeriods,
  servicePlans,
  serviceSlug,
} from "../catalog";

const EMPTY_FILTERS = { q: "", status: "" };
const INITIAL_FORM = {
  service_key: "",
  level_id: "",
  period_id: "",
  customer_email: "",
};

function matchesFilters(order, filters) {
  if (filters.status && order.status !== filters.status) return false;
  if (!filters.q.trim()) return true;
  const haystack = [order.id, order.customer_email, order.service, order.subscription_level]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("ru");
  return haystack.includes(filters.q.trim().toLocaleLowerCase("ru"));
}

export default function AdminOrders() {
  const [orders, setOrders] = useState([]);
  const [allOrders, setAllOrders] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS);
  const [activeFilters, setActiveFilters] = useState(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusBusy, setStatusBusy] = useState({});
  const [open, setOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createdOrder, setCreatedOrder] = useState(null);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState(INITIAL_FORM);
  const [serviceSearch, setServiceSearch] = useState("");
  const [serviceCategoryFilter, setServiceCategoryFilter] = useState("");
  const modalRef = useRef(null);
  const createButtonRef = useRef(null);

  async function load(nextFilters = activeFilters) {
    setLoading(true);
    setError("");
    try {
      const hasFilters = Boolean(nextFilters.q || nextFilters.status);
      const visibleRequest = api.adminOrders(nextFilters);
      const summaryRequest = hasFilters ? api.adminOrders() : visibleRequest;
      const [visible, summary] = await Promise.all([visibleRequest, summaryRequest]);
      setOrders(visible);
      setAllOrders(summary);
      setActiveFilters(nextFilters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([api.adminOrders(), api.catalog()])
      .then(([nextOrders, services]) => {
        if (!active) return;
        setOrders(nextOrders);
        setAllOrders(nextOrders);
        setCatalog(services);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const service = catalog.find((item) => serviceSlug(item) === form.service_key);
  const serviceByKey = useMemo(
    () => Object.fromEntries(catalog.flatMap((item) => [[serviceSlug(item), item], [item.id, item]])),
    [catalog]
  );

  const serviceCategories = useMemo(() => {
    const map = new Map();
    catalog.forEach((item) => {
      const category = serviceCategory(item);
      map.set(String(category.id), category);
    });
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }, [catalog]);
  const visibleServices = useMemo(() => {
    const needle = serviceSearch.trim().toLocaleLowerCase("ru");
    return catalog.filter((item) => {
      const category = serviceCategory(item);
      if (serviceCategoryFilter && String(category.id) !== serviceCategoryFilter) return false;
      return !needle || [item.name, serviceSlug(item), category.name].join(" ").toLocaleLowerCase("ru").includes(needle);
    });
  }, [catalog, serviceCategoryFilter, serviceSearch]);

  useEffect(() => {
    if (!service) return;
    const levels = servicePlans(service);
    const periods = servicePeriods(service);
    setForm((current) => ({
      ...current,
      level_id: levels.some((item) => item.id === current.level_id) ? current.level_id : levels[0]?.id || "",
      period_id: periods.some((item) => item.id === current.period_id) ? current.period_id : periods[0]?.id || "",
    }));
  }, [service]);

  useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event) {
      if (event.key === "Escape") {
        closeModal();
        return;
      }
      if (event.key !== "Tab" || !modalRef.current) return;
      const focusable = [...modalRef.current.querySelectorAll("button, a[href], input, select")].filter(
        (element) => !element.disabled
      );
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
    window.requestAnimationFrame(() => modalRef.current?.querySelector("button")?.focus());
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      createButtonRef.current?.focus();
    };
  }, [open]);

  const stats = useMemo(() => {
    const paidOrders = allOrders.filter((item) => item.status === "Оплачено");
    return [
      { label: "Все заказы", value: allOrders.length, hint: "за всё время", tone: "neutral", icon: "□" },
      {
        label: "В работе",
        value: allOrders.filter((item) => item.status === "В работе").length,
        hint: "требуют внимания",
        tone: "warning",
        icon: "↗",
      },
      {
        label: "Оплачено",
        value: paidOrders.length,
        hint: allOrders.length ? `${Math.round((paidOrders.length / allOrders.length) * 100)}% заказов` : "0% заказов",
        tone: "success",
        icon: "✓",
      },
      {
        label: "Выручка",
        value: formatMoney(paidOrders.reduce((sum, item) => sum + Number(item.amount), 0)),
        hint: "по оплаченным",
        tone: "accent",
        icon: "₽",
      },
    ];
  }, [allOrders]);

  const levels = servicePlans(service);
  const periods = servicePeriods(service);
  const selectedLevel = levels.find((item) => item.id === form.level_id);
  const selectedPeriod = periods.find((item) => item.id === form.period_id);
  const formAmount = priceFor(service, selectedLevel, selectedPeriod);

  function onFilterSubmit(event) {
    event.preventDefault();
    load({ ...draftFilters });
  }

  function onStatusFilter(nextStatus) {
    const next = { ...draftFilters, status: nextStatus };
    setDraftFilters(next);
    load(next);
  }

  function clearFilters() {
    setDraftFilters(EMPTY_FILTERS);
    load(EMPTY_FILTERS);
  }

  async function onStatus(id, nextStatus) {
    setStatusBusy((current) => ({ ...current, [id]: true }));
    setError("");
    try {
      const updated = await api.updateStatus(id, nextStatus);
      setAllOrders((rows) => rows.map((row) => (row.id === id ? updated : row)));
      setOrders((rows) => {
        const nextRows = rows.map((row) => (row.id === id ? updated : row));
        return nextRows.filter((row) => matchesFilters(row, activeFilters));
      });
    } catch (err) {
      setError(`Статус не изменён: ${err.message}`);
    } finally {
      setStatusBusy((current) => ({ ...current, [id]: false }));
    }
  }

  async function onCreate(event) {
    event.preventDefault();
    setCreateBusy(true);
    setCreateError("");
    try {
      const created = await api.createOrder({
        service_key: form.service_key,
        level_id: form.level_id,
        period_id: form.period_id,
        customer_email: form.customer_email || null,
      });
      setCreatedOrder(created);
      setAllOrders((rows) => [created, ...rows]);
      if (matchesFilters(created, activeFilters)) setOrders((rows) => [created, ...rows]);
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreateBusy(false);
    }
  }

  function openModal() {
    const first = catalog[0];
    const firstLevels = servicePlans(first);
    const firstPeriods = servicePeriods(first);
    setForm({ ...INITIAL_FORM, service_key: first ? serviceSlug(first) : "", level_id: firstLevels[0]?.id || "", period_id: firstPeriods[0]?.id || "" });
    setServiceSearch("");
    setServiceCategoryFilter("");
    setCreatedOrder(null);
    setCreateError("");
    setCopied(false);
    setOpen(true);
  }

  function closeModal() {
    setOpen(false);
    setCreatedOrder(null);
    setCreateError("");
  }

  async function copyCustomerLink() {
    try {
      await copyText(`${window.location.origin}/order/${createdOrder.id}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCreateError("Не удалось скопировать ссылку. Выделите её и скопируйте вручную.");
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <span className="page-eyebrow">CRM · Продажи</span>
          <h1>Заказы</h1>
          <p>Управляйте подписками, оплатами и ссылками клиентов</p>
        </div>
        <button
          className="btn create-order-button"
          onClick={openModal}
          disabled={!catalog.length}
          title={!catalog.length ? "Каталог пока недоступен" : undefined}
          ref={createButtonRef}
        >
          <span aria-hidden="true">＋</span> Новый заказ
        </button>
      </div>

      <section className="stats" aria-label="Сводка по заказам">
        {stats.map((item) => (
          <article className={`card stat ${item.tone}`} key={item.label}>
            <div className="stat-head">
              <span>{item.label}</span>
              <i aria-hidden="true">{item.icon}</i>
            </div>
            <div className="n">{item.value}</div>
            <small>{item.hint}</small>
          </article>
        ))}
      </section>

      <section className="orders-section">
        <div className="orders-heading">
          <div>
            <h2>Все заказы</h2>
            <p>{loading ? "Обновляем список…" : `${orders.length} найдено`}</p>
          </div>
          <button className="icon-button" type="button" onClick={() => load(activeFilters)} disabled={loading} aria-label="Обновить список">
            ↻
          </button>
        </div>

        <form className="card filters" onSubmit={onFilterSubmit}>
          <label className="search-control">
            <span aria-hidden="true">⌕</span>
            <span className="sr-only">Поиск заказов</span>
            <input
              placeholder="Поиск по email, ID или сервису"
              value={draftFilters.q}
              onChange={(event) => setDraftFilters((current) => ({ ...current, q: event.target.value }))}
            />
          </label>
          <label className="filter-select">
            <span className="sr-only">Фильтр по статусу</span>
            <select value={draftFilters.status} onChange={(event) => onStatusFilter(event.target.value)}>
              <option value="">Все статусы</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
          <button className="btn secondary" type="submit" disabled={loading}>Найти</button>
          {activeFilters.q || activeFilters.status ? (
            <button className="text-button" type="button" onClick={clearFilters}>Сбросить</button>
          ) : null}
        </form>

        {error ? <div className="admin-alert" role="alert">{error}</div> : null}

        <div className={`card table-wrap ${loading ? "is-loading" : ""}`}>
          <table>
            <thead>
              <tr>
                <th>Заказ</th>
                <th>Клиент</th>
                <th>Сервис</th>
                <th>Тариф</th>
                <th>Сумма</th>
                <th>Создан</th>
                <th>Выполнение</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const rowService = serviceByKey[order.service_key];
                return (
                  <tr key={order.id}>
                    <td data-label="Заказ">
                      <Link className="order-link" to={`/admin/orders/${order.id}`}>
                        {shortOrderId(order.id)}
                        <span>Открыть →</span>
                      </Link>
                    </td>
                    <td data-label="Клиент">
                      <span className={order.customer_email ? "customer-email" : "empty-value"}>
                        {order.customer_email || "Ожидает заполнения"}
                      </span>
                    </td>
                    <td data-label="Сервис">
                      <span className="table-service">
                        <ServiceMark
                          serviceKey={order.service_key}
                          name={order.service}
                          logoUrl={serviceLogo(rowService)}
                          accent={rowService?.accent}
                          size={36}
                          compact
                        />
                        <strong>{order.service}</strong>
                      </span>
                    </td>
                    <td data-label="Тариф">
                      <strong>{order.subscription_level || "—"}</strong>
                      <small>{order.payment_period || "—"}</small>
                    </td>
                    <td data-label="Сумма" className="money-cell">{formatMoney(order.amount, order.currency)}</td>
                    <td data-label="Создан" className="date-cell">{formatDate(order.created_at)}</td>
                    <td data-label="Выполнение">
                      <ExecutionBadge status={order.execution_status || "pending"} compact />
                      <small>{order.executor_name || order.workflow || "Исполнитель не назначен"}</small>
                    </td>
                    <td data-label="Статус">
                      <StatusSelect
                        value={order.status}
                        onChange={(next) => onStatus(order.id, next)}
                        disabled={Boolean(statusBusy[order.id])}
                        label={`Статус заказа ${shortOrderId(order.id)}`}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!loading && orders.length === 0 ? (
            <div className="empty-orders">
              <span aria-hidden="true">⌕</span>
              <h3>Заказы не найдены</h3>
              <p>Измените запрос или сбросьте фильтры.</p>
              <button className="btn secondary" type="button" onClick={clearFilters}>Сбросить фильтры</button>
            </div>
          ) : null}
        </div>
      </section>

      {open ? (
        <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closeModal()}>
          <div className="card modal" role="dialog" aria-modal="true" aria-labelledby="create-order-title" ref={modalRef}>
            <button className="modal-close" type="button" onClick={closeModal} aria-label="Закрыть">×</button>
            {createdOrder ? (
              <div className="created-order-result">
                <span className="success-mark small" aria-hidden="true"><span>✓</span></span>
                <span className="page-eyebrow">Готово</span>
                <h2 id="create-order-title">Ссылка создана</h2>
                <p>Отправьте её клиенту — форма уже настроена под выбранный сервис.</p>
                <label htmlFor="created-order-link">Ссылка клиента</label>
                <div className="copy-row">
                  <input id="created-order-link" readOnly value={`${window.location.origin}/order/${createdOrder.id}`} />
                  <button className="btn" type="button" onClick={copyCustomerLink}>{copied ? "Готово" : "Копировать"}</button>
                </div>
                <span className="sr-only" aria-live="polite">{copied ? "Ссылка скопирована" : ""}</span>
                {createError ? <div className="admin-alert" role="alert">{createError}</div> : null}
                <Link className="btn secondary result-detail-link" to={`/admin/orders/${createdOrder.id}`} onClick={closeModal}>
                  Открыть карточку заказа
                </Link>
              </div>
            ) : (
              <form onSubmit={onCreate}>
                <span className="page-eyebrow">Новый заказ</span>
                <h2 id="create-order-title">Настройте ссылку клиента</h2>
                <p className="muted">Сервис, тариф и период уже будут выбраны в форме заказа.</p>

                <fieldset className="modal-fieldset">
                  <legend>Сервис</legend>
                  <div className="service-picker-toolbar">
                    <label className="search-control">
                      <span aria-hidden="true">⌕</span><span className="sr-only">Найти сервис</span>
                      <input type="search" value={serviceSearch} onChange={(event) => setServiceSearch(event.target.value)} placeholder="Поиск по 100+ сервисам" />
                    </label>
                    <label className="filter-select">
                      <span className="sr-only">Категория сервиса</span>
                      <select value={serviceCategoryFilter} onChange={(event) => setServiceCategoryFilter(event.target.value)}>
                        <option value="">Все категории</option>
                        {serviceCategories.map((category) => <option key={category.id} value={String(category.id)}>{category.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="scalable-service-picker">
                    <select
                      value={form.service_key}
                      size={Math.min(Math.max(visibleServices.length, 3), 8)}
                      onChange={(event) => {
                        const item = catalog.find((candidate) => serviceSlug(candidate) === event.target.value);
                        setForm((current) => ({ ...current, service_key: event.target.value, level_id: servicePlans(item)[0]?.id || "", period_id: servicePeriods(item)[0]?.id || "" }));
                      }}
                      aria-label="Сервис заказа"
                    >
                      {visibleServices.map((item) => <option key={item.id || serviceSlug(item)} value={serviceSlug(item)}>{item.name} · {serviceCategory(item).name}</option>)}
                    </select>
                    {service ? <div className="selected-service-preview"><ServiceMark serviceKey={serviceSlug(service)} name={service.name} logoUrl={serviceLogo(service)} accent={service.accent} size={48} compact /><div><strong>{service.name}</strong><span>{serviceCategory(service).name}</span></div></div> : <p className="picker-empty">По фильтрам ничего не найдено.</p>}
                  </div>
                </fieldset>

                {service ? (
                  <div className="modal-two-columns">
                    <div className="field">
                      <label htmlFor="new-order-level">Тариф</label>
                      <select id="new-order-level" value={form.level_id} onChange={(event) => setForm((current) => ({ ...current, level_id: event.target.value }))}>
                        {levels.map((item) => (
                          <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label htmlFor="new-order-period">Период</label>
                      <select id="new-order-period" value={form.period_id} onChange={(event) => setForm((current) => ({ ...current, period_id: event.target.value }))}>
                        {periods.map((item) => (
                          <option key={item.id} value={item.id}>{item.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                ) : null}

                <div className="field">
                  <label htmlFor="new-order-email">Email клиента <span>необязательно</span></label>
                  <input
                    id="new-order-email"
                    type="email"
                    placeholder="client@example.com"
                    value={form.customer_email}
                    onChange={(event) => setForm((current) => ({ ...current, customer_email: event.target.value }))}
                  />
                </div>

                <div className="modal-total">
                  <span>Сумма заказа</span>
                  <strong>{formAmount === 0 || formAmount === null ? "По запросу" : formatMoney(formAmount, service?.currency || "RUB")}</strong>
                </div>
                {createError ? <div className="admin-alert" role="alert">{createError}</div> : null}
                <div className="modal-actions">
                  <button className="btn secondary" type="button" onClick={closeModal}>Отмена</button>
                  <button className="btn" type="submit" disabled={createBusy || !service || !selectedLevel || !selectedPeriod}>
                    {createBusy ? "Создаём…" : "Создать ссылку"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}
