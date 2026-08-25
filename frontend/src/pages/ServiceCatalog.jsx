import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import ServiceMark from "../components/ServiceMark";
import { api, formatMoney } from "../api/client";
import {
  priceFor,
  serviceCategory,
  serviceLogo,
  servicePeriods,
  servicePlans,
  serviceSlug,
} from "../catalog";

function lowestPrice(service) {
  const options = servicePlans(service).flatMap((level) =>
    servicePeriods(service).map((period) => ({
      amount: priceFor(service, level, period),
      period,
    }))
  ).filter((option) => option.amount !== null && option.amount >= 0);
  if (!options.length) return null;
  return options.reduce((minimum, option) => option.amount < minimum.amount ? option : minimum);
}

function orderIdFromInput(value) {
  const input = value.trim();
  if (!input) return "";

  const match = input.match(/(?:^|\/order\/)([0-9a-f-]{8,})(?=[/?#]|$)/i);
  return match?.[1] || "";
}

export default function ServiceCatalog() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState([]);
  const [serviceQuery, setServiceQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [orderLink, setOrderLink] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [linkError, setLinkError] = useState("");

  useEffect(() => {
    let active = true;
    api
      .catalog()
      .then((services) => {
        if (active) setCatalog(services);
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

  function loadCatalog() {
    setLoading(true);
    setError("");
    api.catalog()
      .then(setCatalog)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  const planCount = useMemo(
    () => catalog.reduce((total, service) => total + servicePlans(service).length, 0),
    [catalog]
  );
  const categories = useMemo(() => {
    const byId = new Map();
    catalog.forEach((service) => {
      const category = serviceCategory(service);
      byId.set(String(category.id), category);
    });
    return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }, [catalog]);
  const visibleCatalog = useMemo(() => {
    const needle = serviceQuery.trim().toLocaleLowerCase("ru");
    return catalog.filter((service) => {
      const category = serviceCategory(service);
      if (categoryFilter && String(category.id) !== categoryFilter) return false;
      if (!needle) return true;
      return [service.name, serviceSlug(service), service.description, service.tagline, category.name]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("ru")
        .includes(needle)
    });
  }, [catalog, categoryFilter, serviceQuery]);

  function openOrder(event) {
    event.preventDefault();
    const orderId = orderIdFromInput(orderLink);
    if (!orderId) {
      setLinkError("Вставьте ссылку формата /order/… или номер заказа.");
      return;
    }
    navigate(`/order/${orderId}`);
  }

  return (
    <div className="storefront">
      <header className="store-header">
        <Link to="/" aria-label="Nexa Store — главная">
          <Logo light />
        </Link>
        <nav aria-label="Основная навигация">
          <a href="#services">Сервисы</a>
          <a href="#how-it-works">Как это работает</a>
          <Link className="header-admin-link" to="/admin/orders">
            CRM
          </Link>
        </nav>
      </header>

      <main>
        <section className="catalog-hero">
          <div className="hero-copy">
            <span className="eyebrow">Nexa Store · подписки без границ</span>
            <h1>Нужные digital-сервисы в одном аккуратном заказе</h1>
            <p>
              Выберите тариф по персональной ссылке, безопасно передайте необходимые данные и отслеживайте
              оформление заказа.
            </p>
            <div className="hero-facts" aria-label="Преимущества">
              <span>Прозрачная цена</span>
              <span>Защищённая форма</span>
              <span>Статус заказа</span>
            </div>
          </div>

          <form className="order-finder" onSubmit={openOrder} noValidate>
            <span className="finder-icon" aria-hidden="true">
              ↗
            </span>
            <div>
              <h2>Уже получили ссылку?</h2>
              <p>Откройте персональный заказ по ссылке или его ID.</p>
            </div>
            <label htmlFor="order-link">Ссылка или ID заказа</label>
            <div className="finder-input-row">
              <input
                id="order-link"
                value={orderLink}
                onChange={(event) => {
                  setOrderLink(event.target.value);
                  setLinkError("");
                }}
                placeholder="https://…/order/xxxxxxxx-…"
                autoComplete="off"
              />
              <button className="btn" type="submit">
                Открыть
              </button>
            </div>
            {linkError ? <p className="form-error">{linkError}</p> : null}
          </form>
        </section>

        <section className="catalog-section" id="services">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Каталог</span>
              <h2>Сервисы и тарифы</h2>
            </div>
            {!loading && !error ? (
              <p>
                {catalog.length} сервиса · {planCount} тарифов
              </p>
            ) : null}
          </div>

          {!loading && !error && catalog.length ? (
            <div className="store-catalog-toolbar">
              <label className="store-catalog-search">
                <span aria-hidden="true">⌕</span>
                <span className="sr-only">Поиск сервиса</span>
                <input
                  type="search"
                  value={serviceQuery}
                  onChange={(event) => setServiceQuery(event.target.value)}
                  placeholder="Найти среди всех сервисов"
                />
              </label>
              <label className="store-category-filter">
                <span className="sr-only">Категория сервиса</span>
                <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                  <option value="">Все категории</option>
                  {categories.map((category) => (
                    <option key={category.id} value={String(category.id)}>{category.name}</option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}

          {loading ? <div className="catalog-state">Загружаем каталог…</div> : null}
          {error ? (
            <div className="catalog-state error-state">
              <p>{error}</p>
              <button className="btn secondary" type="button" onClick={loadCatalog}>Повторить</button>
            </div>
          ) : null}

          <div className="service-grid">
            {visibleCatalog.map((service, index) => {
              const slug = serviceSlug(service);
              const price = lowestPrice(service);
              const category = serviceCategory(service);
              const plans = servicePlans(service);
              return (
              <article className="service-card" key={service.id || slug} style={{ "--card-index": Math.min(index, 12) }}>
                <div className="service-card-top">
                  <ServiceMark
                    serviceKey={slug}
                    name={service.name}
                    logoUrl={serviceLogo(service)}
                    accent={service.accent}
                    size={58}
                  />
                  <span className="service-number">{String(index + 1).padStart(2, "0")}</span>
                </div>
                <span className="service-category-label">{category.name}</span>
                <h3>{service.name}</h3>
                <p>{service.description || service.tagline}</p>
                <div className="plan-pills" aria-label={`Тарифы ${service.name}`}>
                  {plans.slice(0, 3).map((level) => (
                    <span key={level.id}>{level.name}</span>
                  ))}
                  {plans.length > 3 ? <span>+{plans.length - 3}</span> : null}
                </div>
                <div className="service-card-footer">
                  <span>{!price || price.amount === 0 ? "Цена по запросу" : `от ${formatMoney(price.amount, service.currency || "RUB")}`}</span>
                  <small>{price?.amount > 0 ? price.period.name : "уточнит менеджер"}</small>
                </div>
              </article>
              );
            })}
          </div>
          {!loading && !error && catalog.length > 0 && visibleCatalog.length === 0 ? (
            <div className="catalog-state">
              Сервисы не найдены. <button className="catalog-reset-search" type="button" onClick={() => { setServiceQuery(""); setCategoryFilter(""); }}>Сбросить фильтры</button>
            </div>
          ) : null}
        </section>

        <section className="steps-section" id="how-it-works">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Процесс</span>
              <h2>Три понятных шага</h2>
            </div>
          </div>
          <div className="steps-grid">
            <article>
              <span>01</span>
              <h3>Получите ссылку</h3>
              <p>Менеджер создаёт персональный заказ с выбранным сервисом.</p>
            </article>
            <article>
              <span>02</span>
              <h3>Проверьте детали</h3>
              <p>Выберите тариф и период, затем заполните поля именно для вашего сервиса.</p>
            </article>
            <article>
              <span>03</span>
              <h3>Отправьте заказ</h3>
              <p>Данные попадут в CRM, а временные секреты не сохранятся в базе.</p>
            </article>
          </div>
        </section>
      </main>

      <footer className="store-footer">
        <Logo light size={28} />
        <p>Персональные заказы цифровых подписок</p>
        <Link to="/admin/orders">Вход для менеджера</Link>
      </footer>
    </div>
  );
}
