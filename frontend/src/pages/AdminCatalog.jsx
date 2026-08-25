import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, formatMoney } from "../api/client";
import {
  minimumServicePrice,
  serviceCategory,
  serviceLogo,
  servicePeriods,
  servicePlans,
  serviceSlug,
  workflowOf,
} from "../catalog";
import ConfirmDialog from "../components/ConfirmDialog";
import ServiceMark from "../components/ServiceMark";

function isActive(service) {
  return service.is_active ?? service.active ?? true;
}

function serviceDescription(service) {
  return service.description || service.tagline || "Описание пока не добавлено.";
}

function importSummary(report) {
  return {
    imported: Number(report?.imported ?? report?.created ?? 0),
    skipped: Number(report?.skipped ?? 0),
    duplicates: Number(report?.duplicates ?? report?.duplicate_count ?? 0),
    errors: Array.isArray(report?.errors) ? report.errors : report?.errors ? [String(report.errors)] : [],
  };
}

export default function AdminCatalog() {
  const location = useLocation();
  const [services, setServices] = useState([]);
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(location.state?.notice || "");
  const [actionBusy, setActionBusy] = useState({});
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importReport, setImportReport] = useState(null);

  async function loadCatalog() {
    setLoading(true);
    setError("");
    try {
      setServices(await api.adminCatalog());
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    api.adminCatalog()
      .then((rows) => { if (active) setServices(rows); })
      .catch((loadError) => { if (active) setError(loadError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const categories = useMemo(() => {
    const map = new Map();
    services.forEach((service) => {
      const category = serviceCategory(service);
      map.set(String(category.id), category);
    });
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }, [services]);

  const visibleServices = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("ru");
    return services.filter((service) => {
      const active = isActive(service);
      const category = serviceCategory(service);
      if (activeFilter === "active" && !active) return false;
      if (activeFilter === "archived" && active) return false;
      if (categoryFilter && String(category.id) !== categoryFilter) return false;
      if (!needle) return true;
      return [service.name, serviceSlug(service), serviceDescription(service), category.name]
        .filter(Boolean).join(" ").toLocaleLowerCase("ru").includes(needle);
    });
  }, [activeFilter, categoryFilter, query, services]);

  async function toggleActive(service) {
    const slug = serviceSlug(service);
    const nextActive = !isActive(service);
    setActionBusy((current) => ({ ...current, [slug]: true }));
    setError("");
    try {
      const updated = await api.setServiceActive(slug, nextActive);
      setServices((current) => current.map((item) => serviceSlug(item) === slug
        ? { ...item, ...(updated || {}), is_active: nextActive, active: nextActive }
        : item));
      setNotice(`Сервис «${service.name}» ${nextActive ? "возвращён на витрину" : "отключён"}.`);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionBusy((current) => ({ ...current, [slug]: false }));
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    const slug = serviceSlug(deleteTarget);
    setDeleteBusy(true);
    setDeleteError("");
    try {
      await api.deleteService(slug);
      setServices((current) => current.map((item) => serviceSlug(item) === slug
        ? { ...item, is_active: false, active: false, deleted_at: new Date().toISOString() }
        : item));
      setDeleteTarget(null);
      setNotice(`Сервис «${deleteTarget.name}» удалён с витрины. История заказов сохранена.`);
    } catch (actionError) {
      setDeleteError(actionError.message);
    } finally {
      setDeleteBusy(false);
    }
  }

  function onImportComplete(report) {
    setImportReport(importSummary(report));
    loadCatalog();
  }

  return (
    <>
      <div className="topbar catalog-admin-topbar">
        <div>
          <span className="page-eyebrow">CRM · Каталог</span>
          <h1>Сервисы</h1>
          <p>Управляйте каталогом, формами клиентов, ценами и сценариями выполнения</p>
        </div>
        <div className="catalog-top-actions">
          <button className="btn secondary" type="button" onClick={() => { setImportReport(null); setImportOpen(true); }}>
            Импорт JSON / CSV
          </button>
          <Link className="btn create-order-button" to="/admin/catalog/new"><span aria-hidden="true">＋</span> Добавить сервис</Link>
        </div>
      </div>

      {notice ? <div className="catalog-notice" role="status"><span>{notice}</span><button type="button" aria-label="Скрыть сообщение" onClick={() => setNotice("")}>×</button></div> : null}
      {importReport ? <ImportReport report={importReport} /> : null}
      {error ? <div className="admin-alert catalog-page-alert" role="alert"><span>{error}</span><button className="text-button" type="button" onClick={loadCatalog}>Повторить</button></div> : null}

      <section className="catalog-admin-section" aria-labelledby="admin-catalog-title" aria-busy={loading}>
        <div className="card catalog-admin-toolbar">
          <label className="catalog-admin-search">
            <span aria-hidden="true">⌕</span><span className="sr-only">Поиск по каталогу</span>
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, slug, описание или категория" />
          </label>
          <label className="catalog-filter-select">
            <span className="sr-only">Категория</span>
            <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="">Все категории</option>
              {categories.map((category) => <option key={category.id} value={String(category.id)}>{category.name}</option>)}
            </select>
          </label>
          <label className="catalog-filter-select">
            <span className="sr-only">Доступность</span>
            <select value={activeFilter} onChange={(event) => setActiveFilter(event.target.value)}>
              <option value="active">На витрине</option>
              <option value="archived">Отключённые</option>
              <option value="all">Все сервисы</option>
            </select>
          </label>
          <button className="icon-button" type="button" onClick={loadCatalog} disabled={loading} aria-label="Обновить каталог">↻</button>
        </div>

        <div className="catalog-admin-heading">
          <div><h2 id="admin-catalog-title">Каталог CRM</h2><p>{loading ? "Загружаем…" : `${visibleServices.length} из ${services.length} сервисов`}</p></div>
        </div>

        {loading && !services.length ? <div className="card catalog-admin-loading" aria-live="polite"><span className="spinner" aria-hidden="true" /> Загружаем каталог…</div> : null}

        <div className={`catalog-admin-grid ${loading ? "is-loading" : ""}`}>
          {visibleServices.map((service) => {
            const slug = serviceSlug(service);
            const active = isActive(service);
            const price = minimumServicePrice(service);
            const category = serviceCategory(service);
            const workflow = workflowOf(service);
            return (
              <article className={`card catalog-admin-card ${!active ? "is-archived" : ""}`} key={service.id || slug}>
                <div className="catalog-admin-card-head">
                  <ServiceMark serviceKey={slug} name={service.name} logoUrl={serviceLogo(service)} accent={service.accent} size={52} compact />
                  <div><span className="catalog-card-category">{category.name}</span><h3>{service.name}</h3><code>{slug}</code></div>
                  <span className={`catalog-state-badge ${active ? "active" : ""}`}>{active ? "Активен" : "Отключён"}</span>
                </div>
                <p>{serviceDescription(service)}</p>
                <dl className="catalog-admin-meta">
                  <div><dt>Тарифы</dt><dd>{servicePlans(service).length}</dd></div>
                  <div><dt>Периоды</dt><dd>{servicePeriods(service).length}</dd></div>
                  <div><dt>Цена</dt><dd>{price === null || price === 0 ? "По запросу" : `от ${formatMoney(price, service.currency || "RUB")}`}</dd></div>
                  <div><dt>Workflow</dt><dd>{workflow.execution_type || "manual"}</dd></div>
                </dl>
                <div className="catalog-admin-actions">
                  <Link className="btn secondary" to={`/admin/catalog/${encodeURIComponent(slug)}`}>Редактировать</Link>
                  <button className="text-button" type="button" onClick={() => toggleActive(service)} disabled={actionBusy[slug]}>{active ? "Отключить" : "Включить"}</button>
                  <button className="text-button danger-text-button" type="button" onClick={() => { setDeleteError(""); setDeleteTarget(service); }}>Удалить</button>
                </div>
              </article>
            );
          })}
        </div>

        {!loading && !visibleServices.length && !error ? (
          <div className="card empty-orders catalog-admin-empty">
            <span aria-hidden="true">◇</span><h3>{services.length ? "Ничего не найдено" : "Каталог пуст"}</h3>
            <p>{services.length ? "Измените фильтры или поисковый запрос." : "Создайте сервис или загрузите каталог из файла."}</p>
            {services.length ? <button className="btn secondary" type="button" onClick={() => { setQuery(""); setCategoryFilter(""); setActiveFilter("all"); }}>Сбросить фильтры</button> : <Link className="btn" to="/admin/catalog/new">Добавить сервис</Link>}
          </div>
        ) : null}
      </section>

      <ConfirmDialog open={Boolean(deleteTarget)} title="Удалить сервис с витрины?" confirmLabel="Удалить сервис" busy={deleteBusy} error={deleteError}
        onConfirm={confirmDelete} onClose={() => { if (!deleteBusy) { setDeleteTarget(null); setDeleteError(""); } }}>
        <p><strong>{deleteTarget?.name}</strong> станет недоступен для новых заказов. Существующие заказы и история CRM сохранятся.</p>
      </ConfirmDialog>

      <ImportDialog open={importOpen} onClose={() => setImportOpen(false)} onComplete={onImportComplete} />
    </>
  );
}

function ImportReport({ report }) {
  return (
    <section className="card import-report" aria-live="polite">
      <div><span>Импортировано</span><strong>{report.imported}</strong></div>
      <div><span>Пропущено</span><strong>{report.skipped}</strong></div>
      <div><span>Дубликаты</span><strong>{report.duplicates}</strong></div>
      {report.errors.length ? <details><summary>Ошибки: {report.errors.length}</summary><ul>{report.errors.slice(0, 20).map((error, index) => <li key={index}>{typeof error === "string" ? error : error.message || JSON.stringify(error)}</li>)}</ul></details> : null}
    </section>
  );
}

function ImportDialog({ open, onClose, onComplete }) {
  const [format, setFormat] = useState("json");
  const [data, setData] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const frame = window.requestAnimationFrame(() => dialogRef.current?.querySelector("textarea")?.focus());
    function onKeyDown(event) { if (event.key === "Escape" && !busy) onClose(); }
    window.addEventListener("keydown", onKeyDown);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener("keydown", onKeyDown); previous?.focus?.(); };
  }, [busy, onClose, open]);

  if (!open) return null;

  async function readFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const detected = file.name.toLowerCase().endsWith(".csv") ? "csv" : "json";
    setFormat(detected);
    setData(await file.text());
    setError("");
  }

  async function submit(event) {
    event.preventDefault();
    let payloadData = data;
    if (!data.trim()) { setError("Выберите файл или вставьте данные."); return; }
    if (format === "json") {
      try {
        payloadData = JSON.parse(data);
        if (!Array.isArray(payloadData)) throw new Error();
      } catch {
        setError("JSON должен содержать массив сервисов.");
        return;
      }
    }
    setBusy(true);
    setError("");
    try {
      const report = await api.importCatalog({ format, data: payloadData });
      onComplete(report || {});
      setData("");
      onClose();
    } catch (importError) {
      setError(importError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <form className="card modal import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-title" onSubmit={submit} ref={dialogRef}>
        <button className="modal-close" type="button" onClick={onClose} disabled={busy} aria-label="Закрыть">×</button>
        <span className="page-eyebrow">Массовое добавление</span><h2 id="import-title">Импорт каталога</h2>
        <p className="muted">Загрузите JSON-массив или CSV с заголовками. Slug используется для поиска дубликатов.</p>
        <div className="import-format-tabs" role="group" aria-label="Формат импорта">
          {['json', 'csv'].map((value) => <button key={value} type="button" className={format === value ? "active" : ""} onClick={() => setFormat(value)}>{value.toUpperCase()}</button>)}
        </div>
        <label className="import-file-control">Файл .{format}<input type="file" accept={format === "json" ? ".json,application/json" : ".csv,text/csv"} onChange={readFile} disabled={busy} /></label>
        <div className="field"><label htmlFor="import-data">Содержимое</label><textarea id="import-data" rows="12" value={data} onChange={(event) => { setData(event.target.value); setError(""); }} spellCheck="false" placeholder={format === "json" ? '[{"name":"RunPod","slug":"runpod","category":"Developer Tools"}]' : "name,slug,category,logo_url,active"} disabled={busy} /></div>
        {error ? <div className="admin-alert" role="alert">{error}</div> : null}
        <div className="modal-actions"><button className="btn secondary" type="button" onClick={onClose} disabled={busy}>Отмена</button><button className="btn" type="submit" disabled={busy}>{busy ? "Импортируем…" : "Импортировать"}</button></div>
      </form>
    </div>
  );
}
