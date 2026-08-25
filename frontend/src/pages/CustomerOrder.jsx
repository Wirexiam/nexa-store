import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Logo from "../components/Logo";
import ServiceFields, { normalizeServiceFields } from "../components/ServiceFields";
import ServiceMark from "../components/ServiceMark";
import StatusBadge from "../components/StatusBadge";
import { api, formatMoney, shortOrderId } from "../api/client";
import {
  optionMatches,
  priceFor,
  serviceInstructions,
  serviceLogo,
  servicePeriods,
  servicePlans,
  serviceSlug,
} from "../catalog";

function instructionLines(value) {
  const lines = String(value || "")
    .split("\n")
    .map((line) => line.replace(/^\d+[.)]\s*/, "").trim())
    .filter(Boolean);
  return lines.length ? lines : ["Проверьте тариф и период.", "Заполните данные ниже и отправьте форму."];
}

function selectedOption(items, ...values) {
  return values.reduce((result, value) => result || items.find((item) => optionMatches(item, value)), null) || items[0];
}

function initialFieldValues(service, order) {
  return Object.fromEntries(normalizeServiceFields(service).map((field) => {
    const isEmail = field.type === "email" || ["email", "customer_email"].includes(field.name);
    return [field.name, field.type === "checkbox" ? false : isEmail ? order.customer_email || "" : ""];
  }));
}

function withoutSensitive(values, service) {
  const sensitiveNames = new Set(normalizeServiceFields(service)
    .filter((field) => field.sensitive || field.temporary_only || field.type === "secure_textarea")
    .map((field) => field.name));
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [key, sensitiveNames.has(key) ? "" : value]));
}

export default function CustomerOrder() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [service, setService] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [levelId, setLevelId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function loadOrder() {
      setLoading(true);
      setError("");
      try {
        const nextOrder = await api.publicOrder(id, { signal: controller.signal });
        let nextService = nextOrder.catalog_service || nextOrder.service_config || null;
        const identifier = nextOrder.catalog_service_id || nextService?.id || nextOrder.service_key;

        if (identifier) {
          try {
            nextService = await api.catalogService(identifier, { signal: controller.signal });
          } catch (serviceError) {
            if (!nextService && serviceError.status !== 404) throw serviceError;
          }
        }
        if (!nextService) {
          const catalog = await api.catalog();
          nextService = catalog.find((item) =>
            [item.id, item.key, item.slug].some((value) => String(value) === String(identifier || nextOrder.service_key))
          );
        }
        if (!nextService) throw new Error("Сервис этого заказа больше не доступен.");

        if (!(nextService.fields || nextService.service_fields) && identifier) {
          try {
            const fields = await api.catalogFields(identifier, { signal: controller.signal });
            nextService = { ...nextService, fields };
          } catch (fieldsError) {
            if (![404, 405].includes(fieldsError.status)) throw fieldsError;
          }
        }

        if (!active) return;
        const plans = servicePlans(nextService);
        const periods = servicePeriods(nextService);
        const plan = selectedOption(
          plans,
          nextOrder.level_id,
          nextOrder.catalog_plan_id,
          nextOrder.subscription_level
        );
        const period = selectedOption(
          periods,
          nextOrder.period_id,
          nextOrder.catalog_period_id,
          nextOrder.payment_period
        );

        setOrder(nextOrder);
        setService(nextService);
        setLevelId(plan?.id || "");
        setPeriodId(period?.id || "");
        setFormValues(initialFieldValues(nextService, nextOrder));
      } catch (loadError) {
        if (loadError.name !== "AbortError" && active) setError(loadError.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadOrder();
    return () => {
      active = false;
      controller.abort();
    };
  }, [id]);

  const plans = useMemo(() => servicePlans(service), [service]);
  const periods = useMemo(() => servicePeriods(service), [service]);
  const level = selectedOption(plans, levelId);
  const period = selectedOption(periods, periodId);
  const amount = useMemo(() => priceFor(service, level, period), [level, period, service]);
  const fields = useMemo(() => normalizeServiceFields(service), [service]);
  const isClosed = order && ["Оплачено", "Отменено"].includes(order.status);

  function updateField(name, value) {
    setError("");
    setFormValues((current) => ({ ...current, [name]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!service || !level || !period || isClosed) return;

    setBusy(true);
    setError("");
    const emailField = fields.find((field) =>
      field.type === "email" || ["email", "customer_email"].includes(field.name)
    );
    const sensitiveField = fields.find((field) =>
      field.name === "access_token" || field.sensitive || field.temporary_only
    );
    const payload = {
      email: emailField ? formValues[emailField.name] : order.customer_email || null,
      level_id: level.id,
      period_id: period.id,
      fields: { ...formValues },
    };
    if (sensitiveField?.name === "access_token" && formValues.access_token) {
      payload.access_token = formValues.access_token;
    }

    try {
      await api.submitOrder(id, payload);
      setFormValues((current) => withoutSensitive(current, service));
      navigate(`/order/${id}/confirmation`, { replace: true });
    } catch (submitError) {
      setFormValues((current) => withoutSensitive(current, service));
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <OrderPageShell>
        <div className="checkout-card order-loading" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <p>Загружаем актуальные настройки заказа…</p>
        </div>
      </OrderPageShell>
    );
  }

  if (error && (!order || !service)) {
    return (
      <OrderPageShell>
        <div className="checkout-card order-error-state">
          <span className="state-symbol" aria-hidden="true">!</span>
          <h1>Не удалось открыть заказ</h1>
          <p>{error}</p>
          <Link className="btn secondary light-button" to="/">На главную</Link>
        </div>
      </OrderPageShell>
    );
  }

  if (!order || !service) return null;
  const slug = serviceSlug(service);

  if (isClosed) {
    return (
      <OrderPageShell>
        <div className="checkout-card closed-order-card">
          <ServiceMark serviceKey={slug} name={service.name} logoUrl={serviceLogo(service)} accent={service.accent} size={72} />
          <span className="order-kicker">Заказ {shortOrderId(order.id)}</span>
          <h1>{order.status === "Оплачено" ? "Заказ уже оплачен" : "Заказ отменён"}</h1>
          <p>{order.status === "Оплачено"
            ? "Данные приняты, выполнение заказа уже контролируется менеджером."
            : "Эта ссылка больше не принимает данные. Обратитесь к менеджеру за новым заказом."}</p>
          <StatusBadge status={order.status} />
          <div className="closed-order-summary">
            <span>{service.name}</span>
            <strong>{formatMoney(order.amount, order.currency)}</strong>
          </div>
          <Link className="btn secondary light-button" to="/">Вернуться в каталог</Link>
        </div>
      </OrderPageShell>
    );
  }

  return (
    <OrderPageShell>
      <form className="checkout-card order-card" onSubmit={onSubmit}>
        <div className="order-card-head">
          <div className="service-title-row">
            <ServiceMark serviceKey={slug} name={service.name} logoUrl={serviceLogo(service)} accent={service.accent} size={72} />
            <div>
              <span className="order-kicker">Заказ {shortOrderId(order.id)}</span>
              <h1>{service.name}</h1>
              <p>{service.description || service.tagline}</p>
            </div>
          </div>
          <StatusBadge status={order.status} />
        </div>

        <div className="order-divider" />

        <section className="order-section" aria-labelledby="instructions-title">
          <div className="section-label"><span>01</span><div><h2 id="instructions-title">Перед началом</h2><p>Следуйте инструкции для выбранного сервиса.</p></div></div>
          <ol className="instructions-list">
            {instructionLines(serviceInstructions(service)).map((line, index) => <li key={`${index}-${line}`}>{line}</li>)}
          </ol>
        </section>

        <section className="order-section" aria-labelledby="plan-title">
          <div className="section-label"><span>02</span><div><h2 id="plan-title">Тариф и период</h2><p>Конфигурация загружена из актуального каталога.</p></div></div>

          <fieldset className="choice-fieldset">
            <legend>Тариф</legend>
            <div className="choice-grid">
              {plans.map((item) => {
                const itemPrice = priceFor(service, item, period);
                return (
                  <button type="button" key={item.id} className={`choice ${item.id === level?.id ? "selected" : ""}`}
                    onClick={() => { setLevelId(item.id); setError(""); }} aria-pressed={item.id === level?.id} disabled={busy}>
                    <strong>{item.name}</strong>
                    {item.description ? <small>{item.description}</small> : null}
                    <span>{itemPrice === 0 || itemPrice === null ? "Цена по запросу" : formatMoney(itemPrice, service.currency || order.currency)}</span>
                    <i aria-hidden="true">✓</i>
                  </button>
                );
              })}
            </div>
          </fieldset>

          <fieldset className="choice-fieldset period-fieldset">
            <legend>Период оплаты</legend>
            <div className="period-grid">
              {periods.map((item) => (
                <button type="button" key={item.id} className={`period-choice ${item.id === period?.id ? "selected" : ""}`}
                  onClick={() => { setPeriodId(item.id); setError(""); }} aria-pressed={item.id === period?.id} disabled={busy}>
                  {item.name}
                </button>
              ))}
            </div>
          </fieldset>
        </section>

        <section className="order-section" aria-labelledby="details-title">
          <div className="section-label"><span>03</span><div><h2 id="details-title">Данные для выполнения</h2><p>Набор полей настроен специально для этого сервиса.</p></div></div>
          <ServiceFields service={service} values={formValues} onChange={updateField} disabled={busy} />
        </section>

        {error ? <div className="submit-error" role="alert"><strong>Не удалось отправить данные</strong><span>{error}</span></div> : null}

        <div className="pay-bar">
          <div><span>Итого к оплате</span><div className="amount">{amount === 0 || amount === null ? "По запросу" : formatMoney(amount, service.currency || order.currency)}</div></div>
          <button className="btn submit-order-button" type="submit" disabled={busy || !level || !period}>
            {busy ? <><span className="button-spinner" aria-hidden="true" /> Отправляем…</> : "Отправить данные"}
          </button>
        </div>
        <p className="form-footnote">Временные секреты очищаются из формы после каждой попытки отправки.</p>
      </form>
    </OrderPageShell>
  );
}

function OrderPageShell({ children }) {
  return (
    <div className="checkout">
      <header className="checkout-header">
        <Link to="/" aria-label="Nexa Store — в каталог"><Logo light /></Link>
        <span className="secure-header-note"><span aria-hidden="true">◇</span> Защищённая форма заказа</span>
      </header>
      <main className="checkout-main">{children}</main>
      <footer className="checkout-footer">© Nexa Store · Секретные данные не сохраняются</footer>
    </div>
  );
}
