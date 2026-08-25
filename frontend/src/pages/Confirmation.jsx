import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Logo from "../components/Logo";
import ServiceMark from "../components/ServiceMark";
import StatusBadge from "../components/StatusBadge";
import { api, formatMoney, shortOrderId } from "../api/client";
import { serviceLogo, serviceSlug } from "../catalog";

export default function Confirmation() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [service, setService] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.publicOrder(id)
      .then(async (nextOrder) => {
        let nextService = nextOrder.catalog_service || nextOrder.service_config || null;
        if (!nextService) {
          try {
            nextService = await api.catalogService(nextOrder.catalog_service_id || nextOrder.service_key);
          } catch {
            const catalog = await api.catalog();
            nextService = catalog.find((item) => [item.id, item.key, item.slug].includes(nextOrder.service_key)) || null;
          }
        }
        if (active) {
          setOrder(nextOrder);
          setService(nextService);
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <div className="checkout confirmation-page">
      <header className="checkout-header">
        <Link to="/" aria-label="Nexa Store — в каталог">
          <Logo light />
        </Link>
        <span className="secure-header-note">Данные успешно переданы</span>
      </header>
      <main className="checkout-main">
        {error ? (
          <div className="checkout-card order-error-state">
            <span className="state-symbol" aria-hidden="true">!</span>
            <h1>Не удалось загрузить подтверждение</h1>
            <p>{error}</p>
            <Link className="btn secondary light-button" to={`/order/${id}`}>
              Вернуться к заказу
            </Link>
          </div>
        ) : null}

        {!error && (!order || !service) ? (
          <div className="checkout-card order-loading" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <p>Подтверждаем заказ…</p>
          </div>
        ) : null}

        {order && service ? (
          <div className="checkout-card confirmation-card">
            <div className="success-mark" aria-hidden="true">
              <span>✓</span>
            </div>
            <span className="eyebrow">Заказ {shortOrderId(order.id)}</span>
            <h1>Спасибо, заказ принят</h1>
            <p className="confirmation-lead">
              Данные уже в CRM Nexa Store. Менеджер проверит их и продолжит оформление подписки.
            </p>

            <div className="confirmation-summary">
              <div className="confirmation-service">
                <ServiceMark serviceKey={serviceSlug(service)} name={service.name} logoUrl={serviceLogo(service)} accent={service.accent} size={52} />
                <div>
                  <strong>{service.name} · {order.subscription_level}</strong>
                  <span>{order.payment_period}</span>
                </div>
              </div>
              <div className="confirmation-price">
                <span>Сумма</span>
                <strong>{formatMoney(order.amount, order.currency)}</strong>
              </div>
              <div className="confirmation-status">
                <span>Статус</span>
                <StatusBadge status={order.status} />
              </div>
            </div>

            <div className="next-steps">
              <h2>Что дальше</h2>
              <div>
                <span className="done">✓</span>
                <p><strong>Данные получены</strong><small>Секретные поля удалены после отправки.</small></p>
              </div>
              <div>
                <span>2</span>
                <p><strong>Проверка менеджером</strong><small>Менеджер сверит тариф и данные аккаунта.</small></p>
              </div>
              <div>
                <span>3</span>
                <p><strong>Активация подписки</strong><small>После оплаты статус заказа изменится.</small></p>
              </div>
            </div>

            <div className="confirmation-actions">
              <Link className="btn" to="/">
                В каталог
              </Link>
              <Link className="btn secondary light-button" to={`/order/${id}`}>
                Открыть заказ
              </Link>
            </div>
          </div>
        ) : null}
      </main>
      <footer className="checkout-footer">Сохраните ссылку, чтобы позже проверить статус заказа</footer>
    </div>
  );
}
