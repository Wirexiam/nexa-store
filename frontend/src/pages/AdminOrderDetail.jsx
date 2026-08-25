import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ExecutionBadge from "../components/ExecutionBadge";
import ServiceMark from "../components/ServiceMark";
import StatusSelect from "../components/StatusSelect";
import { api, copyText, formatDate, formatMoney, shortOrderId } from "../api/client";
import { serviceLogo, serviceSlug, workflowOf } from "../catalog";

export default function AdminOrderDetail() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [service, setService] = useState(null);
  const [error, setError] = useState("");
  const [statusBusy, setStatusBusy] = useState(false);
  const [executionBusy, setExecutionBusy] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([api.adminOrder(id), api.catalog()])
      .then(([nextOrder, catalog]) => {
        if (!active) return;
        setOrder(nextOrder);
        setService(catalog.find((item) => [item.id, item.key, item.slug].some((value) => String(value) === String(nextOrder.catalog_service_id || nextOrder.service_key)) || item.key === nextOrder.service_key) || null);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [id]);

  useEffect(() => {
    if (!order || order.execution_status !== "running") return undefined;
    let active = true;
    const timer = window.setInterval(() => {
      api.executionStatus(id)
        .then((status) => { if (active) setOrder((current) => ({ ...current, ...status, id: current.id })); })
        .catch(() => { /* Keep the last known state; manual refresh remains available. */ });
    }, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [id, order?.execution_status]);

  async function onStatus(nextStatus) {
    setStatusBusy(true);
    setError("");
    try {
      setOrder(await api.updateStatus(order.id, nextStatus));
    } catch (err) {
      setError(`Статус не изменён: ${err.message}`);
    } finally {
      setStatusBusy(false);
    }
  }

  async function copyLink() {
    setError("");
    try {
      await copyText(`${window.location.origin}/order/${order.id}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setError("Не удалось скопировать ссылку. Выделите её и скопируйте вручную.");
    }
  }

  async function runExecution(action) {
    setExecutionBusy(action);
    setError("");
    try {
      const methods = { execute: api.executeOrder, stop: api.stopExecution, retry: api.retryExecution };
      const result = await methods[action](order.id);
      setOrder((current) => ({ ...current, ...result, id: current.id }));
    } catch (executionError) {
      setError(`Команда выполнения не отправлена: ${executionError.message}`);
    } finally {
      setExecutionBusy("");
    }
  }

  if (error && !order) {
    return (
      <div className="detail-state card">
        <span aria-hidden="true">!</span>
        <h1>Не удалось открыть заказ</h1>
        <p>{error}</p>
        <Link className="btn secondary" to="/admin/orders">К списку заказов</Link>
      </div>
    );
  }

  if (!order) {
    return <div className="admin-boot"><span className="spinner" aria-hidden="true" /> Загружаем заказ…</div>;
  }

  const customerLink = `${window.location.origin}/order/${order.id}`;

  return (
    <>
      <div className="detail-breadcrumbs">
        <Link to="/admin/orders">Заказы</Link>
        <span>/</span>
        <span>{shortOrderId(order.id)}</span>
      </div>

      <div className="topbar detail-topbar">
        <div className="detail-title">
          <ServiceMark
            serviceKey={order.service_key}
            name={order.service}
            logoUrl={serviceLogo(service)}
            accent={service?.accent}
            size={54}
          />
          <div>
            <span className="page-eyebrow">Карточка заказа</span>
            <h1>{shortOrderId(order.id)}</h1>
            <p>{order.service} · {order.subscription_level}</p>
          </div>
        </div>
        <div className="detail-status-action">
          <label>Текущий статус</label>
          <StatusSelect
            value={order.status}
            onChange={onStatus}
            disabled={statusBusy}
            label={`Статус заказа ${shortOrderId(order.id)}`}
          />
        </div>
      </div>

      {error ? <div className="admin-alert" role="alert">{error}</div> : null}

      <div className="detail-grid detail-page-grid">
        <section className="detail-main-column">
          <article className="card panel order-info-card">
            <div className="panel-heading">
              <div>
                <span className="panel-icon" aria-hidden="true">◎</span>
                <div><h2>Детали заказа</h2><p>Клиент, сервис и выбранный тариф</p></div>
              </div>
            </div>
            <div className="order-info-grid">
              <div>
                <span>Email клиента</span>
                <strong>{order.customer_email || "Ожидает заполнения"}</strong>
              </div>
              <div>
                <span>Сервис</span>
                <strong>{order.service}</strong>
              </div>
              <div>
                <span>Тариф</span>
                <strong>{order.subscription_level || "—"}</strong>
              </div>
              <div>
                <span>Период</span>
                <strong>{order.payment_period || "—"}</strong>
              </div>
              <div>
                <span>Сумма</span>
                <strong className="detail-amount">{formatMoney(order.amount, order.currency)}</strong>
              </div>
              <div>
                <span>Данные доступа</span>
                <strong className={order.credentials_received ? "credential-yes" : "empty-value"}>
                  {order.credentials_received ? "Получены · значение удалено" : "Не требовались / не получены"}
                </strong>
              </div>
              <div>
                <span>Статус выполнения</span>
                <ExecutionBadge status={order.execution_status || "pending"} compact />
              </div>
              <div>
                <span>Исполнитель</span>
                <strong>{order.executor_name || "Назначится при запуске"}</strong>
              </div>
            </div>
          </article>

          {order.custom_data && Object.keys(order.custom_data).length ? (
            <article className="card panel order-custom-data-card">
              <div className="panel-heading"><div><span className="panel-icon" aria-hidden="true">≡</span><div><h2>Данные клиента</h2><p>Только разрешённые несекретные поля</p></div></div></div>
              <dl className="custom-data-list">
                {Object.entries(order.custom_data).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "boolean" ? (value ? "Да" : "Нет") : String(value)}</dd></div>)}
              </dl>
            </article>
          ) : null}

          <ExecutionPanel order={order} service={service} busy={executionBusy} onAction={runExecution} />

          <article className="card panel customer-link-card">
            <div className="panel-heading">
              <div>
                <span className="panel-icon" aria-hidden="true">↗</span>
                <div><h2>Ссылка клиента</h2><p>Персональная форма этого заказа</p></div>
              </div>
              <a href={customerLink} target="_blank" rel="noreferrer">Открыть ↗</a>
            </div>
            <div className="copy-row detail-copy-row">
              <input readOnly value={customerLink} aria-label="Ссылка клиента" />
              <button className="btn" type="button" onClick={copyLink}>{copied ? "Скопировано" : "Копировать"}</button>
            </div>
            <span className="sr-only" aria-live="polite">{copied ? "Ссылка скопирована" : ""}</span>
            <p className="security-copy"><span aria-hidden="true">◇</span> Доступ к форме есть у любого, кто получил эту уникальную ссылку.</p>
          </article>
        </section>

        <aside className="detail-side-column">
          <article className="card panel timeline-card">
            <div className="panel-heading">
              <div>
                <span className="panel-icon" aria-hidden="true">◷</span>
                <div><h2>История</h2><p>Основные события</p></div>
              </div>
            </div>
            <ol className="order-timeline">
              <li className="complete">
                <span aria-hidden="true">✓</span>
                <div><strong>Заказ создан</strong><small>{formatDate(order.created_at)}</small></div>
              </li>
              <li className={order.submitted_at ? "complete" : "pending"}>
                <span aria-hidden="true">{order.submitted_at ? "✓" : "2"}</span>
                <div><strong>Форма клиента</strong><small>{order.submitted_at ? formatDate(order.submitted_at) : "Ожидает заполнения"}</small></div>
              </li>
              <li className={order.status === "Оплачено" ? "complete" : "pending"}>
                <span aria-hidden="true">{order.status === "Оплачено" ? "✓" : "3"}</span>
                <div><strong>Оплата</strong><small>{order.status === "Оплачено" ? "Отмечено менеджером" : "Ожидается"}</small></div>
              </li>
              <li className={order.execution_status === "completed" ? "complete" : "pending"}>
                <span aria-hidden="true">{order.execution_status === "completed" ? "✓" : "4"}</span>
                <div><strong>Выполнение</strong><small>{order.execution_finished_at ? formatDate(order.execution_finished_at) : order.execution_started_at ? `Начато ${formatDate(order.execution_started_at)}` : "Ещё не запущено"}</small></div>
              </li>
            </ol>
          </article>

          <article className="card panel record-card">
            <h2>Системная информация</h2>
            <dl>
              <div><dt>Полный ID</dt><dd className="mono">{order.id}</dd></div>
              <div><dt>Обновлён</dt><dd>{formatDate(order.updated_at)}</dd></div>
              <div><dt>Валюта</dt><dd>{order.currency}</dd></div>
              <div><dt>Workflow</dt><dd>{order.workflow || workflowOf(service).execution_type || "manual"}</dd></div>
              <div><dt>Executor</dt><dd>{order.executor_name || "—"}</dd></div>
              <div><dt>Попытки</dt><dd>{order.execution_attempts ?? 0}</dd></div>
            </dl>
          </article>
        </aside>
      </div>
    </>
  );
}

function ExecutionPanel({ order, service, busy, onAction }) {
  const status = order.execution_status || "pending";
  const workflow = workflowOf(service);
  const isRunning = status === "running";
  const result = order.execution_result;

  return (
    <article className="card panel execution-panel">
      <div className="panel-heading">
        <div><span className="panel-icon" aria-hidden="true">⚙</span><div><h2>Выполнение заказа</h2><p>Workflow и состояние исполнителя</p></div></div>
        <ExecutionBadge status={status} />
      </div>
      <div className="execution-summary-grid">
        <div><span>Workflow</span><strong>{order.workflow || workflow.execution_type || "manual"}</strong></div>
        <div><span>Executor</span><strong>{order.executor_name || "Будет назначен при запуске"}</strong></div>
        <div><span>Начато</span><strong>{formatDate(order.execution_started_at)}</strong></div>
        <div><span>Завершено</span><strong>{formatDate(order.execution_finished_at)}</strong></div>
      </div>
      {workflow.description ? <p className="execution-description">{workflow.description}</p> : null}
      {order.execution_stop_requested ? <div className="execution-note">Запрошена остановка. Исполнитель завершает текущий безопасный шаг.</div> : null}
      {order.execution_error ? <div className="admin-alert execution-error" role="alert"><strong>Ошибка выполнения</strong><span>{order.execution_error}</span></div> : null}
      {result ? <details className="execution-result"><summary>Результат выполнения</summary><pre>{typeof result === "string" ? result : JSON.stringify(result, null, 2)}</pre></details> : null}
      <div className="execution-actions">
        {isRunning ? (
          <button className="btn danger-button" type="button" onClick={() => onAction("stop")} disabled={Boolean(busy)}>{busy === "stop" ? "Останавливаем…" : "Остановить"}</button>
        ) : (
          <button className="btn" type="button" onClick={() => onAction(status === "failed" || status === "completed" || status === "action_required" ? "retry" : "execute")} disabled={Boolean(busy) || !workflow.active}>
            {busy ? "Отправляем команду…" : status === "pending" || status === "stopped" ? "Запустить выполнение" : "Повторить выполнение"}
          </button>
        )}
        {!workflow.active ? <span>Workflow отключён в каталоге сервиса.</span> : null}
      </div>
    </article>
  );
}
