import ServiceMark from "./ServiceMark";

export default function ServiceLivePreview({ form }) {
  const firstPlan = form.levels?.find((item) => item.is_active) || form.levels?.[0];
  const firstPeriod = form.periods?.find((item) => item.is_active) || form.periods?.[0];
  const price = firstPlan?.prices?.[firstPeriod?._key];

  return (
    <section className="card editor-section live-preview-card">
      <div className="editor-section-heading">
        <div className="editor-heading-copy">
          <span className="panel-icon">◉</span>
          <div>
            <h2>Предпросмотр заказа</h2>
            <p>Так клиент увидит страницу услуги</p>
          </div>
        </div>
      </div>
      <div className="live-preview-phone">
        <ServiceMark
          serviceKey={form.slug}
          name={form.name || "Сервис"}
          logoUrl={form.logo}
          accent={form.accent}
          size={56}
        />
        <h3>{form.name || "Название сервиса"}</h3>
        <p>{form.description || "Описание услуги"}</p>
        {form.instructions ? <small>{form.instructions}</small> : null}
        <div className="preview-price">
          {price ? `${price} ${firstPlan?.currency || form.currency}` : "Цена по запросу"}
        </div>
        {(form.fields || []).filter((field) => field.is_active).slice(0, 4).map((field) => (
          <div className="preview-input" key={field._key}>
            {field.field_label || field.field_name}
          </div>
        ))}
        <button type="button" className="btn" disabled>Отправить данные</button>
      </div>
    </section>
  );
}
