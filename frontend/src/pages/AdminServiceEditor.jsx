import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, formatMoney } from "../api/client";
import {
  priceFor,
  serviceCategory,
  serviceInstructions,
  serviceLogo,
  servicePeriods,
  servicePlans,
  serviceSlug,
  workflowOf,
} from "../catalog";
import { normalizeServiceFields } from "../components/ServiceFields";
import ServiceMark from "../components/ServiceMark";
import ServiceLivePreview from "../components/ServiceLivePreview";

const KEY_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const FIELD_PATTERN = /^[a-z][a-z0-9_]*$/;
const FIELD_TYPES = [
  ["text", "Короткий текст"],
  ["email", "Email"],
  ["textarea", "Многострочный текст"],
  ["secure_textarea", "Защищённый текст"],
  ["select", "Список"],
  ["checkbox", "Флажок"],
];
const WORKFLOW_TYPES = [
  ["manual", "Ручное выполнение"],
  ["browser_session", "Изолированная браузерная сессия"],
  ["uid_topup", "Пополнение по UID"],
  ["gift_code", "Подарочный код"],
  ["api", "API-интеграция"],
];

let localKey = 0;
function draftKey(prefix) {
  localKey += 1;
  return `${prefix}-${Date.now()}-${localKey}`;
}

function slugify(value) {
  return value.trim().toLocaleLowerCase("en").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64);
}

function createPeriod(source = {}) {
  return {
    _key: draftKey("period"),
    _persisted: Boolean(source.record_id || source.db_id || source._persisted),
    id: source.key || source.public_id || source.id || "",
    name: source.name || "",
    duration: source.duration ?? "",
    is_active: source.is_active ?? source.active ?? true,
  };
}

function createPlan(periods, source = {}) {
  const plan = {
    _key: draftKey("plan"),
    _persisted: Boolean(source.record_id || source.db_id || source._persisted),
    id: source.key || source.public_id || source.id || "",
    name: source.name || "",
    description: source.description || "",
    currency: source.currency || "",
    is_active: source.is_active ?? source.active ?? true,
    prices: {},
  };
  periods.forEach((period) => {
    const amount = priceFor(null, { ...source, prices: source.prices || {} }, period);
    plan.prices[period._key] = amount ?? "";
  });
  return plan;
}

function createField(source = {}, index = 0) {
  const options = Array.isArray(source.options) ? source.options : [];
  return {
    _key: draftKey("field"),
    id: source.id || null,
    field_name: source.field_name || source.name || "",
    field_label: source.field_label || source.label || "",
    field_type: source.field_type || source.type || "text",
    required: Boolean(source.required),
    placeholder: source.placeholder || "",
    help_text: source.help_text || source.hint || "",
    validation_rules: JSON.stringify(source.validation_rules || source.validation || {}, null, 2),
    options_text: options.map((option) => typeof option === "string" ? option : option.label || option.value).filter(Boolean).join("\n"),
    order: Number(source.order ?? source.sort_order ?? index),
    sensitive: Boolean(source.sensitive),
    temporary_only: Boolean(source.temporary_only),
    is_active: source.is_active ?? source.active ?? true,
  };
}

function emptyService() {
  const periods = [createPeriod({ id: "1m", name: "1 месяц", duration: 30 })];
  return {
    name: "",
    slug: "",
    category_id: "",
    category_name: "",
    category_mode: "__new__",
    logo: "",
    description: "",
    accent: "#18bda5",
    currency: "RUB",
    instructions: "",
    is_active: true,
    periods,
    levels: [createPlan(periods, { id: "basic", name: "Базовый", currency: "RUB", prices: { "1m": 0 } })],
    fields: [createField({ field_name: "email", field_label: "Email аккаунта", field_type: "email", required: true, placeholder: "name@example.com" })],
    workflow: { execution_type: "manual", active: true, requires_manual_action: true, description: "" },
  };
}

const SERVICE_TEMPLATES = [
  {
    id: "ai",
    name: "AI подписка",
    description: "Шаблон для продажи цифровой AI-подписки.",
    build: () => ({
      ...emptyService(),
      name: "Новая AI подписка",
      slug: "new-ai-service",
      category_name: "AI", category_mode: "__new__",
      description: "Доступ к цифровому AI-сервису.",
      fields: [createField({ field_name: "email", field_label: "Email аккаунта", field_type: "email", required: true })],
      workflow: { execution_type: "browser_session", active: true, requires_manual_action: true, description: "Активация через временную сессию." },
    }),
  },
  {
    id: "game",
    name: "Игровая валюта",
    description: "UID пополнение игр.",
    build: () => ({
      ...emptyService(),
      name: "Новое пополнение",
      slug: "new-topup",
      category_name: "Gaming", category_mode: "__new__",
      fields: [
        createField({ field_name: "uid", field_label: "UID игрока", field_type: "text", required: true }),
        createField({ field_name: "server", field_label: "Сервер", field_type: "select", required: true, options: ["Europe", "America", "Asia"] }),
      ],
      workflow: { execution_type: "uid_topup", active: true, requires_manual_action: true, description: "Пополнение по игровому UID." },
    }),
  },
  {
    id: "gift",
    name: "Gift Code",
    description: "Продажа цифровых кодов.",
    build: () => ({
      ...emptyService(),
      name: "Новый Gift Code",
      slug: "new-gift-code",
      category_name: "Software", category_mode: "__new__",
      fields: [createField({ field_name: "email", field_label: "Email клиента", field_type: "email", required: true })],
      workflow: { execution_type: "gift_code", active: true, requires_manual_action: false, description: "Выдача кода после оплаты." },
    }),
  },
  {
    id: "api",
    name: "API сервис",
    description: "Продажа доступа к API.",
    build: () => ({
      ...emptyService(),
      name: "Новый API сервис",
      slug: "new-api-service",
      category_name: "Developer Tools", category_mode: "__new__",
      fields: [createField({ field_name: "email", field_label: "Email аккаунта", field_type: "email", required: true })],
      workflow: { execution_type: "api", active: true, requires_manual_action: false, description: "Автоматическая выдача API доступа." },
    }),
  },
];

function serviceToDraft(service) {
  const periods = servicePeriods(service).map(createPeriod);
  const category = serviceCategory(service);
  const configuredFields = normalizeServiceFields(service);
  return {
    name: service.name || "",
    slug: serviceSlug(service),
    category_id: service.category_id || category.id || "",
    category_name: category.name === "Без категории" ? "" : category.name,
    category_mode: service.category_id || category.id ? String(service.category_id || category.id) : "__new__",
    logo: serviceLogo(service),
    description: service.description || service.tagline || "",
    accent: service.accent || "#18bda5",
    currency: service.currency || "RUB",
    instructions: serviceInstructions(service),
    is_active: service.is_active ?? service.active ?? true,
    periods,
    levels: servicePlans(service).map((plan) => createPlan(periods, plan)),
    fields: configuredFields.map(createField),
    workflow: { ...workflowOf(service) },
  };
}

function parseValidationRules(value) {
  if (!value.trim()) return {};
  const parsed = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error();
  return parsed;
}


function readFieldSchema(field) {
  try {
    return JSON.parse(field.validation_rules || "{}");
  } catch {
    return {};
  }
}

function updateFieldSchema(field, patch) {
  const schema = { ...readFieldSchema(field), ...patch };
  return JSON.stringify(schema, null, 2);
}

function validateService(form) {
  const errors = {};
  if (!form.name.trim()) errors.name = "Введите название сервиса.";
  if (!KEY_PATTERN.test(form.slug.trim())) errors.slug = "Используйте строчные латинские буквы, цифры и дефисы.";
  if (!form.description.trim()) errors.description = "Добавьте описание для витрины.";
  if (form.category_mode === "__new__" && !form.category_name.trim()) errors.category = "Выберите или введите категорию.";
  if (form.logo.trim()) {
    const local = form.logo.startsWith("/uploads/") && !form.logo.includes("..");
    try {
      const url = new URL(form.logo);
      if (url.protocol !== "https:" || url.username || url.password) throw new Error();
      if (!url.hostname) throw new Error();
    } catch {
      if (!local) errors.logo = "Нужен HTTPS URL или путь /uploads/…";
    }
  }
  if (!/^[A-Z]{3,8}$/.test(form.currency)) errors.currency = "Например, RUB или USD.";
  if (!form.periods.length) errors.periods = "Добавьте хотя бы один период.";
  if (!form.levels.length) errors.levels = "Добавьте хотя бы один тариф.";
  if (form.is_active && !form.periods.some((item) => item.is_active)) errors.periods = "Активному сервису нужен активный период.";
  if (form.is_active && !form.levels.some((item) => item.is_active)) errors.levels = "Активному сервису нужен активный тариф.";

  const periodIds = new Set();
  form.periods.forEach((period) => {
    if (!period.name.trim()) errors[`period:${period._key}:name`] = "Введите название.";
    if (!KEY_PATTERN.test(period.id.trim())) errors[`period:${period._key}:id`] = "Нужен код вида 1-month.";
    else if (periodIds.has(period.id.trim())) errors[`period:${period._key}:id`] = "Код уже используется.";
    if (period.duration !== "" && (!Number.isInteger(Number(period.duration)) || Number(period.duration) < 1)) errors[`period:${period._key}:duration`] = "Введите целое число дней.";
    periodIds.add(period.id.trim());
  });

  const planIds = new Set();
  form.levels.forEach((plan) => {
    if (!plan.name.trim()) errors[`plan:${plan._key}:name`] = "Введите название.";
    if (!KEY_PATTERN.test(plan.id.trim())) errors[`plan:${plan._key}:id`] = "Нужен код вида premium.";
    else if (planIds.has(plan.id.trim())) errors[`plan:${plan._key}:id`] = "Код уже используется.";
    planIds.add(plan.id.trim());
    form.periods.forEach((period) => {
      const raw = String(plan.prices[period._key] ?? "").trim();
      const value = Number(raw);
      if (!raw || !Number.isFinite(value) || value < 0) errors[`price:${plan._key}:${period._key}`] = "Цена 0 или больше.";
    });
  });

  const fieldNames = new Set();
  form.fields.forEach((field) => {
    if (!FIELD_PATTERN.test(field.field_name.trim())) errors[`field:${field._key}:name`] = "Латиница, цифры и _; начните с буквы.";
    else if (fieldNames.has(field.field_name.trim())) errors[`field:${field._key}:name`] = "Имя уже используется.";
    if (!field.field_label.trim()) errors[`field:${field._key}:label`] = "Введите подпись.";
    if (field.field_type === "select" && !field.options_text.split(/\r?\n/).some((item) => item.trim())) errors[`field:${field._key}:options`] = "Добавьте варианты, каждый с новой строки.";
    try { parseValidationRules(field.validation_rules); } catch { errors[`field:${field._key}:validation`] = "Введите JSON-объект, например {\"min_length\": 3}."; }
    fieldNames.add(field.field_name.trim());
  });
  return errors;
}

function toPayload(form, categories) {
  const category = categories.find((item) => String(item.id) === String(form.category_mode));
  const sensitiveField = form.fields.find((field) => field.sensitive || field.temporary_only || field.field_type === "secure_textarea");
  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    logo: form.logo.trim(),
    description: form.description.trim(),
    accent: form.accent.toUpperCase(),
    currency: form.currency.trim().toUpperCase(),
    category_id: form.category_mode === "__new__" ? null : category?.id || form.category_id || null,
    category: form.category_mode === "__new__" ? form.category_name.trim() : category?.name || form.category_name || null,
    requires_access_token: Boolean(sensitiveField),
    token_label: sensitiveField?.field_label || null,
    token_hint: sensitiveField?.help_text || null,
    instructions: form.instructions.trim(),
    is_active: form.is_active,
    periods: form.periods.map((period, index) => ({
      id: period.id.trim(), name: period.name.trim(), duration: period.duration === "" ? null : Number(period.duration),
      is_active: period.is_active, sort_order: index,
    })),
    levels: form.levels.map((plan, index) => ({
      id: plan.id.trim(), name: plan.name.trim(), description: plan.description.trim(),
      currency: (plan.currency || form.currency).trim().toUpperCase(), is_active: plan.is_active, sort_order: index,
      prices: Object.fromEntries(form.periods.map((period) => [period.id.trim(), String(plan.prices[period._key]).trim()])),
    })),
    fields: form.fields.map((field, index) => ({
      ...(field.id ? { id: field.id } : {}),
      field_name: field.field_name.trim(), field_label: field.field_label.trim(), field_type: field.field_type,
      required: field.required, placeholder: field.placeholder.trim() || null, help_text: field.help_text.trim() || null,
      validation_rules: parseValidationRules(field.validation_rules),
      options: field.field_type === "select" ? field.options_text.split(/\r?\n/).map((item) => item.trim()).filter(Boolean) : [],
      order: index, sensitive: field.field_type === "secure_textarea" || field.sensitive,
      temporary_only: field.field_type === "secure_textarea" || field.temporary_only,
      is_active: field.is_active,
    })),
    workflow: {
      execution_type: form.workflow.execution_type,
      active: form.workflow.active,
      requires_manual_action: form.workflow.requires_manual_action,
      description: form.workflow.description.trim(),
    },
  };
}

function FieldError({ message }) {
  return message ? <span className="field-error">{message}</span> : null;
}

export default function AdminServiceEditor() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const isNew = !slug;
  const [form, setForm] = useState(emptyService);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [slugTouched, setSlugTouched] = useState(!isNew);
  const errorSummaryRef = useRef(null);

  async function loadData() {
    setLoading(true);
    setLoadError("");
    try {
      const [categoryResult, serviceResult] = await Promise.allSettled([
        api.adminCategories(),
        isNew ? Promise.resolve(null) : api.adminService(slug),
      ]);
      const nextCategories = categoryResult.status === "fulfilled" ? categoryResult.value : [];
      setCategories(nextCategories);
      if (!isNew) {
        if (serviceResult.status === "rejected") throw serviceResult.reason;
        const draft = serviceToDraft(serviceResult.value);
        const matching = nextCategories.find((item) => String(item.id) === String(draft.category_id) || item.name === draft.category_name);
        draft.category_mode = matching ? String(matching.id) : "__new__";
        setForm(draft);
      }
      setDirty(false);
    } catch (loadFailure) {
      setLoadError(loadFailure.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [slug]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    function beforeUnload(event) { if (dirty) { event.preventDefault(); event.returnValue = ""; } }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const categoryOptions = useMemo(() => {
    const list = [...categories];
    if (form.category_id && !list.some((item) => String(item.id) === String(form.category_id))) {
      list.push({ id: form.category_id, name: form.category_name || "Текущая категория" });
    }
    return list.sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }, [categories, form.category_id, form.category_name]);
  const previewPrice = useMemo(() => {
    const values = form.levels.flatMap((plan) => form.periods.map((period) => Number(plan.prices[period._key])))
      .filter((value) => Number.isFinite(value) && value > 0);
    return values.length ? Math.min(...values) : 0;
  }, [form.levels, form.periods]);

  function change(updater) {
    setForm((current) => typeof updater === "function" ? updater(current) : { ...current, ...updater });
    setDirty(true); setSaveError(""); setErrors({});
  }
  function updatePeriod(key, patch) { change((current) => ({ ...current, periods: current.periods.map((item) => item._key === key ? { ...item, ...patch } : item) })); }
  function updatePlan(key, patch) { change((current) => ({ ...current, levels: current.levels.map((item) => item._key === key ? { ...item, ...patch } : item) })); }
  function updateField(key, patch) { change((current) => ({ ...current, fields: current.fields.map((item) => item._key === key ? { ...item, ...patch } : item) })); }

  function addPeriod() {
    const period = createPeriod();
    change((current) => ({ ...current, periods: [...current.periods, period], levels: current.levels.map((plan) => ({ ...plan, prices: { ...plan.prices, [period._key]: "" } })) }));
  }
  function removePeriod(period) {
    if (form.periods.length === 1 || !window.confirm(`Удалить период «${period.name || period.id}» и его цены?`)) return;
    change((current) => ({ ...current, periods: current.periods.filter((item) => item._key !== period._key), levels: current.levels.map((plan) => { const prices = { ...plan.prices }; delete prices[period._key]; return { ...plan, prices }; }) }));
  }
  function addPlan() { change((current) => ({ ...current, levels: [...current.levels, createPlan(current.periods, { currency: current.currency })] })); }
  function removePlan(plan) {
    if (form.levels.length === 1 || !window.confirm(`Удалить тариф «${plan.name || plan.id}» и его цены?`)) return;
    change((current) => ({ ...current, levels: current.levels.filter((item) => item._key !== plan._key) }));
  }
  function addField() { change((current) => ({ ...current, fields: [...current.fields, createField({}, current.fields.length)] })); }
  function removeField(field) {
    if (!window.confirm(`Удалить поле «${field.field_label || field.field_name || "без названия"}»?`)) return;
    change((current) => ({ ...current, fields: current.fields.filter((item) => item._key !== field._key) }));
  }
  function cancel() { if (!dirty || window.confirm("Отменить несохранённые изменения?")) navigate("/admin/catalog"); }

  function applyTemplate(template) {
    if (dirty && !window.confirm("Заменить текущую конфигурацию шаблоном?")) return;
    setForm(template.build());
    setDirty(true);
    setErrors({});
    setSaveError("");
  }

  async function onSubmit(event) {
    event.preventDefault();
    const nextErrors = validateService(form);
    setErrors(nextErrors); setSaveError("");
    if (Object.keys(nextErrors).length) { window.requestAnimationFrame(() => errorSummaryRef.current?.focus()); return; }
    setBusy(true);
    try {
      const payload = toPayload(form, categoryOptions);
      const saved = isNew ? await api.createService(payload) : await api.updateService(slug, payload);
      setDirty(false);
      navigate("/admin/catalog", { replace: true, state: { notice: `Сервис «${saved?.name || payload.name}» ${isNew ? "добавлен" : "обновлён"}.` } });
    } catch (saveFailure) {
      setSaveError(saveFailure.message);
      window.requestAnimationFrame(() => errorSummaryRef.current?.focus());
    } finally { setBusy(false); }
  }

  if (loading) return <div className="admin-boot"><span className="spinner" aria-hidden="true" /> Загружаем редактор…</div>;
  if (loadError) return <div className="detail-state card"><span aria-hidden="true">!</span><h1>Не удалось открыть сервис</h1><p>{loadError}</p><div className="service-editor-state-actions"><button className="btn" type="button" onClick={loadData}>Повторить</button><Link className="btn secondary" to="/admin/catalog">К каталогу</Link></div></div>;

  return (
    <form className="service-editor" onSubmit={onSubmit} noValidate aria-busy={busy}>
      <div className="detail-breadcrumbs"><Link to="/admin/catalog">Каталог</Link><span>/</span><span>{isNew ? "Новый сервис" : form.name}</span></div>
      <div className="topbar service-editor-topbar">
        <div><span className="page-eyebrow">CRM · Каталог</span><h1>{isNew ? "Новый сервис" : "Редактирование сервиса"}</h1><p>Сохранённая конфигурация сразу используется витриной и страницами заказов</p></div>
        <div className="service-editor-top-actions"><button className="btn secondary" type="button" onClick={cancel} disabled={busy}>Отмена</button><button className="btn" type="submit" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить"}</button></div>
      </div>
      {!form.is_active ? <div className="catalog-notice archive-notice" role="status">Сервис отключён и не показывается на витрине.</div> : null}
      {isNew ? <section className="card editor-section template-picker" aria-labelledby="templates-title">
        <EditorHeading icon="✦" id="templates-title" title="Шаблоны услуг" copy="Создайте сервис с готовой структурой полей и workflow" />
        <div className="template-grid">
          {SERVICE_TEMPLATES.map((template) => <button key={template.id} className="template-card" type="button" onClick={() => applyTemplate(template)} disabled={busy}>
            <strong>{template.name}</strong><span>{template.description}</span>
          </button>)}
        </div>
      </section> : null}
      {Object.keys(errors).length || saveError ? <div className="admin-alert editor-error-summary" role="alert" tabIndex="-1" ref={errorSummaryRef}><strong>Не удалось сохранить сервис</strong><span>{saveError || `Исправьте ошибки: ${Object.keys(errors).length}.`}</span></div> : null}

      <div className="service-editor-layout">
        <div className="service-editor-main">
          <section className="card editor-section" aria-labelledby="service-basic-title">
            <EditorHeading icon="◇" id="service-basic-title" title="Карточка сервиса" copy="Основные данные для витрины и CRM" />
            <div className="service-basic-grid">
              <div className="service-logo-preview"><ServiceMark serviceKey={form.slug} name={form.name || "Новый сервис"} logoUrl={form.logo} accent={form.accent} size={92} /><span>{previewPrice ? `от ${formatMoney(previewPrice, form.currency)}` : "Цена по запросу"}</span></div>
              <div>
                <div className="field"><label htmlFor="service-name">Название</label><input id="service-name" value={form.name} onChange={(event) => { const name = event.target.value; change((current) => ({ ...current, name, slug: isNew && !slugTouched ? slugify(name) : current.slug })); }} disabled={busy} aria-invalid={Boolean(errors.name)} /><FieldError message={errors.name} /></div>
                <div className="field"><label htmlFor="service-slug">Slug <span>стабильный адрес сервиса</span></label><input id="service-slug" className="mono" value={form.slug} onChange={(event) => { setSlugTouched(true); change({ slug: event.target.value.toLowerCase() }); }} disabled={busy || (!isNew && false)} aria-invalid={Boolean(errors.slug)} placeholder="example-service" /><FieldError message={errors.slug} /></div>
              </div>
            </div>
            <div className="field"><label htmlFor="service-description">Описание</label><textarea id="service-description" rows="4" value={form.description} onChange={(event) => change({ description: event.target.value })} disabled={busy} aria-invalid={Boolean(errors.description)} /><FieldError message={errors.description} /></div>
            <div className="field"><label htmlFor="service-logo">Логотип <span>HTTPS URL или подготовленный путь /uploads/…</span></label><input id="service-logo" type="text" value={form.logo} onChange={(event) => change({ logo: event.target.value })} disabled={busy} aria-invalid={Boolean(errors.logo)} placeholder="https://cdn.example.com/logo.svg" /><FieldError message={errors.logo} /><small className="field-hint">Если изображение недоступно, интерфейс автоматически покажет монограмму сервиса.</small></div>
            <div className="editor-two-columns">
              <div className="field"><label htmlFor="service-category">Категория</label><select id="service-category" value={form.category_mode} onChange={(event) => change({ category_mode: event.target.value })} disabled={busy}>{categoryOptions.map((item) => <option key={item.id} value={String(item.id)}>{item.name}</option>)}<option value="__new__">Новая категория…</option></select>{form.category_mode === "__new__" ? <><input value={form.category_name} onChange={(event) => change({ category_name: event.target.value })} placeholder="Например, Developer Tools" aria-label="Название новой категории" aria-invalid={Boolean(errors.category)} /><FieldError message={errors.category} /></> : null}</div>
              <div className="field"><label htmlFor="service-currency">Валюта</label><input id="service-currency" className="mono" value={form.currency} maxLength="8" onChange={(event) => change({ currency: event.target.value.toUpperCase() })} aria-invalid={Boolean(errors.currency)} disabled={busy} /><FieldError message={errors.currency} /></div>
            </div>
            <div className="editor-two-columns">
              <div className="field"><label htmlFor="service-accent">Цвет акцента</label><div className="color-field"><input type="color" value={form.accent} onChange={(event) => change({ accent: event.target.value })} aria-label="Выбрать цвет" disabled={busy} /><input id="service-accent" className="mono" value={form.accent} onChange={(event) => change({ accent: event.target.value })} disabled={busy} /></div></div>
              <label className="switch-row compact-switch"><span><strong>Сервис активен</strong><small>Показывать на витрине</small></span><input type="checkbox" checked={form.is_active} onChange={(event) => change({ is_active: event.target.checked })} disabled={busy} /></label>
            </div>
          </section>

          <section className="card editor-section" aria-labelledby="periods-title">
            <EditorHeading icon="◷" id="periods-title" title="Периоды оплаты" copy="Колонки матрицы цен" action={<button className="btn secondary small-button" type="button" onClick={addPeriod} disabled={busy}>＋ Период</button>} />
            <FieldError message={errors.periods} />
            <div className="repeatable-list">{form.periods.map((period, index) => <fieldset className="repeatable-row period-editor-row" key={period._key}><legend className="sr-only">Период {index + 1}</legend><span className="repeatable-index">{index + 1}</span><div className="field compact-field"><label>Название</label><input value={period.name} onChange={(event) => updatePeriod(period._key, { name: event.target.value })} placeholder="1 месяц" aria-invalid={Boolean(errors[`period:${period._key}:name`])} /><FieldError message={errors[`period:${period._key}:name`]} /></div><div className="field compact-field"><label>Код</label><input className="mono" value={period.id} onChange={(event) => updatePeriod(period._key, { id: event.target.value.toLowerCase() })} disabled={period._persisted} placeholder="1m" aria-invalid={Boolean(errors[`period:${period._key}:id`])} /><FieldError message={errors[`period:${period._key}:id`]} /></div><div className="field compact-field"><label>Дней</label><input type="number" min="1" value={period.duration} onChange={(event) => updatePeriod(period._key, { duration: event.target.value })} placeholder="30" aria-invalid={Boolean(errors[`period:${period._key}:duration`])} /><FieldError message={errors[`period:${period._key}:duration`]} /></div><label className="mini-check"><input type="checkbox" checked={period.is_active} onChange={(event) => updatePeriod(period._key, { is_active: event.target.checked })} /> Активен</label><button className="remove-row-button" type="button" onClick={() => removePeriod(period)} disabled={form.periods.length === 1} aria-label={`Удалить период ${period.name || index + 1}`}>×</button></fieldset>)}</div>
          </section>

          <section className="card editor-section" aria-labelledby="plans-title">
            <EditorHeading icon="▦" id="plans-title" title="Тарифы" copy="Строки матрицы цен" action={<button className="btn secondary small-button" type="button" onClick={addPlan} disabled={busy}>＋ Тариф</button>} />
            <FieldError message={errors.levels} />
            <div className="repeatable-list">{form.levels.map((plan, index) => <fieldset className="repeatable-row plan-editor-row" key={plan._key}><legend className="sr-only">Тариф {index + 1}</legend><span className="repeatable-index">{index + 1}</span><div className="field compact-field"><label>Название</label><input value={plan.name} onChange={(event) => updatePlan(plan._key, { name: event.target.value })} placeholder="Premium" aria-invalid={Boolean(errors[`plan:${plan._key}:name`])} /><FieldError message={errors[`plan:${plan._key}:name`]} /></div><div className="field compact-field"><label>Код</label><input className="mono" value={plan.id} onChange={(event) => updatePlan(plan._key, { id: event.target.value.toLowerCase() })} disabled={plan._persisted} placeholder="premium" aria-invalid={Boolean(errors[`plan:${plan._key}:id`])} /><FieldError message={errors[`plan:${plan._key}:id`]} /></div><div className="field compact-field grow-field"><label>Описание</label><input value={plan.description} onChange={(event) => updatePlan(plan._key, { description: event.target.value })} placeholder="Для активного использования" /></div><label className="mini-check"><input type="checkbox" checked={plan.is_active} onChange={(event) => updatePlan(plan._key, { is_active: event.target.checked })} /> Активен</label><button className="remove-row-button" type="button" onClick={() => removePlan(plan)} disabled={form.levels.length === 1} aria-label={`Удалить тариф ${plan.name || index + 1}`}>×</button></fieldset>)}</div>
          </section>

          <section className="card editor-section price-section" aria-labelledby="prices-title">
            <EditorHeading icon="₽" id="prices-title" title="Матрица цен" copy="Нулевая цена отображается как «по запросу»" />
            <div className="price-matrix-wrap" tabIndex="0" aria-label="Таблица цен; прокручивается горизонтально"><table className="price-matrix"><thead><tr><th>Тариф</th>{form.periods.map((period) => <th key={period._key}>{period.name || period.id || "Период"}</th>)}</tr></thead><tbody>{form.levels.map((plan) => <tr key={plan._key}><th><strong>{plan.name || plan.id || "Тариф"}</strong><small>{plan.id || "без кода"}</small></th>{form.periods.map((period) => { const key = `price:${plan._key}:${period._key}`; return <td key={period._key}><label className="matrix-price-field"><span className="sr-only">Цена {plan.name}, {period.name}</span><input type="number" min="0" step="0.01" value={plan.prices[period._key] ?? ""} onChange={(event) => updatePlan(plan._key, { prices: { ...plan.prices, [period._key]: event.target.value } })} aria-invalid={Boolean(errors[key])} /><span>{plan.currency || form.currency}</span></label><FieldError message={errors[key]} /></td>; })}</tr>)}</tbody></table></div>
          </section>

          <section className="card editor-section fields-builder" aria-labelledby="fields-title">
            <EditorHeading icon="◎" id="fields-title" title="Поля клиента" copy="Форма заказа строится из этой конфигурации" action={<button className="btn secondary small-button" type="button" onClick={addField}>＋ Поле</button>} />
            {!form.fields.length ? <div className="inline-editor-note">Форма не содержит полей. Добавьте хотя бы одно, если для выполнения нужны данные клиента.</div> : null}
            <div className="field-builder-list">{form.fields.map((field, index) => (
              <fieldset className="field-builder-item" key={field._key}><legend><span>{index + 1}</span>{field.field_label || field.field_name || "Новое поле"}</legend>
                <div className="field-builder-grid"><div className="field"><label>Системное имя</label><input className="mono" value={field.field_name} onChange={(event) => updateField(field._key, { field_name: event.target.value.toLowerCase() })} placeholder="account_email" aria-invalid={Boolean(errors[`field:${field._key}:name`])} /><FieldError message={errors[`field:${field._key}:name`]} /></div><div className="field"><label>Подпись</label><input value={field.field_label} onChange={(event) => updateField(field._key, { field_label: event.target.value })} placeholder="Email аккаунта" aria-invalid={Boolean(errors[`field:${field._key}:label`])} /><FieldError message={errors[`field:${field._key}:label`]} /></div><div className="field"><label>Тип</label><select value={field.field_type} onChange={(event) => { const type = event.target.value; updateField(field._key, { field_type: type, ...(type === "secure_textarea" ? { sensitive: true, temporary_only: true } : {}) }); }}>{FIELD_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><div className="field"><label>Placeholder</label><input value={field.placeholder} onChange={(event) => updateField(field._key, { placeholder: event.target.value })} /></div></div>
                <div className="field"><label>Подсказка</label><input value={field.help_text} onChange={(event) => updateField(field._key, { help_text: event.target.value })} placeholder="Что и в каком формате нужно указать" /></div>
                {field.field_type === "select" ? <div className="field"><label>Варианты <span>каждый с новой строки</span></label><textarea rows="4" value={field.options_text} onChange={(event) => updateField(field._key, { options_text: event.target.value })} aria-invalid={Boolean(errors[`field:${field._key}:options`])} /><FieldError message={errors[`field:${field._key}:options`]} /></div> : null}
                <div className="schema-settings">
                  <strong>Schema настройки</strong>
                  <div className="field-builder-grid compact">
                    <div className="field"><label>Минимальная длина</label><input type="number" min="0" value={readFieldSchema(field).min_length ?? ""} onChange={(event) => updateField(field._key, { validation_rules: updateFieldSchema(field, { min_length: event.target.value ? Number(event.target.value) : undefined }) })} /></div>
                    <div className="field"><label>Максимальная длина</label><input type="number" min="0" value={readFieldSchema(field).max_length ?? ""} onChange={(event) => updateField(field._key, { validation_rules: updateFieldSchema(field, { max_length: event.target.value ? Number(event.target.value) : undefined }) })} /></div>
                    <div className="field"><label>Regex pattern</label><input className="mono" value={readFieldSchema(field).pattern ?? ""} onChange={(event) => updateField(field._key, { validation_rules: updateFieldSchema(field, { pattern: event.target.value || undefined }) })} placeholder="^[A-Za-z0-9]+$" /></div>
                  </div>
                  <div className="field"><label>Расширенная JSON schema</label><textarea className="mono" rows="3" value={field.validation_rules} onChange={(event) => updateField(field._key, { validation_rules: event.target.value })} aria-invalid={Boolean(errors[`field:${field._key}:validation`])} /><FieldError message={errors[`field:${field._key}:validation`]} /></div>
                </div>
                <div className="field-flags"><label><input type="checkbox" checked={field.required} onChange={(event) => updateField(field._key, { required: event.target.checked })} /> Обязательное</label><label><input type="checkbox" checked={field.sensitive} onChange={(event) => updateField(field._key, { sensitive: event.target.checked })} disabled={field.field_type === "secure_textarea"} /> Секретное</label><label><input type="checkbox" checked={field.temporary_only} onChange={(event) => updateField(field._key, { temporary_only: event.target.checked, sensitive: event.target.checked ? true : field.sensitive })} disabled={field.field_type === "secure_textarea"} /> Только временно</label><label><input type="checkbox" checked={field.is_active} onChange={(event) => updateField(field._key, { is_active: event.target.checked })} /> Активно</label><button className="text-button danger-text-button" type="button" onClick={() => removeField(field)}>Удалить поле</button></div>
              </fieldset>
            ))}</div>
          </section>
        </div>

        <aside className="service-editor-side">
          <section className="card editor-section" aria-labelledby="workflow-title">
            <EditorHeading icon="⚙" id="workflow-title" title="Сценарий выполнения" copy="Как обрабатывается заказ после отправки" />
            <div className="field"><label htmlFor="workflow-type">Тип workflow</label><select id="workflow-type" value={form.workflow.execution_type} onChange={(event) => change((current) => ({ ...current, workflow: { ...current.workflow, execution_type: event.target.value } }))}>{WORKFLOW_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
            <label className="switch-row"><span><strong>Workflow активен</strong><small>Разрешить запуск исполнителя</small></span><input type="checkbox" checked={form.workflow.active} onChange={(event) => change((current) => ({ ...current, workflow: { ...current.workflow, active: event.target.checked } }))} /></label>
            <label className="switch-row"><span><strong>Нужно действие менеджера</strong><small>Показывать ручной этап в CRM</small></span><input type="checkbox" checked={form.workflow.requires_manual_action} onChange={(event) => change((current) => ({ ...current, workflow: { ...current.workflow, requires_manual_action: event.target.checked } }))} /></label>
            <div className="field"><label htmlFor="workflow-description">Описание процесса</label><textarea id="workflow-description" rows="5" value={form.workflow.description} onChange={(event) => change((current) => ({ ...current, workflow: { ...current.workflow, description: event.target.value } }))} placeholder="Что должен выполнить executor или менеджер" /></div>
          </section>
          <section className="card editor-section" aria-labelledby="instructions-editor-title"><EditorHeading icon="≡" id="instructions-editor-title" title="Инструкция клиенту" copy="Отображается перед динамической формой" /><div className="field editor-instructions-field"><textarea rows="11" value={form.instructions} onChange={(event) => change({ instructions: event.target.value })} placeholder={'1. Проверьте выбранный тариф.\n2. Подготовьте данные.\n3. Отправьте форму.'} aria-label="Инструкция клиенту" /></div></section>
          <ServiceLivePreview form={form} />
          <section className="card editor-section security-editor-note"><span aria-hidden="true">◇</span><div><h2>Временные данные</h2><p>Поля с флагами «Секретное» или «Только временно» не должны сохраняться backend. Защищённый текст включает оба флага автоматически.</p></div></section>
        </aside>
      </div>

      <div className="card service-editor-footer"><span>{dirty ? "Есть несохранённые изменения" : "Изменения сохранены"}</span><div><button className="btn secondary" type="button" onClick={cancel} disabled={busy}>Отмена</button><button className="btn" type="submit" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить сервис"}</button></div></div>
    </form>
  );
}

function EditorHeading({ icon, id, title, copy, action }) {
  return <div className={`editor-section-heading ${action ? "editor-heading-actions" : ""}`}><div className="editor-heading-copy"><span className="panel-icon" aria-hidden="true">{icon}</span><div><h2 id={id}>{title}</h2><p>{copy}</p></div></div>{action}</div>;
}
