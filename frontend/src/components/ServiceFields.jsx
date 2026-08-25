function parseRules(value) {
  if (!value) return {};
  if (typeof value === "object" && !Array.isArray(value)) return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function normalizeOptions(value) {
  let options = value;
  if (typeof options === "string") {
    try {
      options = JSON.parse(options);
    } catch {
      options = options.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
    }
  }
  if (!Array.isArray(options)) return [];
  return options.map((option) => {
    if (option && typeof option === "object") {
      return {
        value: String(option.value ?? option.id ?? option.label ?? option.name ?? ""),
        label: String(option.label ?? option.name ?? option.value ?? option.id ?? ""),
      };
    }
    return { value: String(option), label: String(option) };
  }).filter((option) => option.value);
}

export function normalizeServiceFields(service) {
  const configured = service?.fields || service?.service_fields || [];
  if (configured.length) {
    return [...configured]
      .map((field, index) => ({
        id: field.id,
        name: field.field_name || field.name || `field_${index + 1}`,
        label: field.field_label || field.label || field.field_name || `Поле ${index + 1}`,
        type: field.field_type || field.type || "text",
        required: Boolean(field.required),
        placeholder: field.placeholder || "",
        hint: field.help_text || field.hint || "",
        validation: parseRules(field.validation_rules || field.validation),
        options: normalizeOptions(field.options),
        order: Number(field.sort_order ?? field.order ?? index),
        sensitive: Boolean(field.sensitive),
        temporary_only: Boolean(field.temporary_only),
      }))
      .sort((a, b) => a.order - b.order);
  }

  const fields = [{
    name: "email",
    type: "email",
    label: `Email аккаунта${service?.name ? ` ${service.name}` : ""}`,
    placeholder: "name@example.com",
    required: true,
    hint: "На этот адрес оформляется подписка и приходят сообщения по заказу.",
    validation: {},
    options: [],
    order: 0,
    sensitive: false,
    temporary_only: false,
  }];

  if (service?.requires_access_token) {
    fields.push({
      name: "access_token",
      type: "secure_textarea",
      label: service.token_label || "Временные данные доступа",
      placeholder: "Вставьте временные данные",
      required: true,
      sensitive: true,
      temporary_only: true,
      hint: service.token_hint || "Значение используется только во время выполнения и не сохраняется в CRM.",
      validation: {},
      options: [],
      order: 1,
    });
  }

  return fields;
}

function commonProps(field) {
  const rules = field.validation;
  return {
    required: field.required,
    minLength: rules.min_length ?? rules.minLength,
    maxLength: rules.max_length ?? rules.maxLength,
    pattern: rules.pattern || undefined,
    min: rules.min,
    max: rules.max,
  };
}

export default function ServiceFields({ service, values, onChange, disabled = false }) {
  return normalizeServiceFields(service).map((field) => {
    const id = `customer-${field.name}`;
    const isSecret = field.sensitive || field.temporary_only || field.type === "secure_textarea";
    const value = values[field.name] ?? (field.type === "checkbox" ? false : "");
    const props = commonProps(field);

    if (field.type === "checkbox") {
      return (
        <div className="customer-field checkbox-customer-field" key={field.name}>
          <label htmlFor={id}>
            <input
              id={id}
              name={field.name}
              type="checkbox"
              checked={Boolean(value)}
              onChange={(event) => onChange(field.name, event.target.checked)}
              disabled={disabled}
              required={field.required}
            />
            <span><strong>{field.label}</strong>{field.hint ? <small>{field.hint}</small> : null}</span>
          </label>
        </div>
      );
    }

    return (
      <div className="field customer-field" key={field.name}>
        <div className="field-label-row">
          <label htmlFor={id}>{field.label}{!field.required ? <span> · необязательно</span> : null}</label>
          {isSecret ? <span className="sensitive-label">Не сохраняется</span> : null}
        </div>

        {field.type === "select" ? (
          <select
            id={id}
            name={field.name}
            value={value}
            onChange={(event) => onChange(field.name, event.target.value)}
            disabled={disabled}
            {...props}
          >
            <option value="" disabled>{field.placeholder || "Выберите вариант"}</option>
            {field.options.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        ) : ["textarea", "secure_textarea"].includes(field.type) ? (
          <textarea
            id={id}
            name={field.name}
            rows={field.type === "secure_textarea" ? 5 : 4}
            value={value}
            onChange={(event) => onChange(field.name, event.target.value)}
            placeholder={field.placeholder}
            autoComplete={isSecret ? "off" : undefined}
            disabled={disabled}
            spellCheck={isSecret ? false : undefined}
            className={isSecret ? "secure-textarea" : undefined}
            {...props}
          />
        ) : (
          <input
            id={id}
            name={field.name}
            type={field.type === "email" ? "email" : "text"}
            value={value}
            onChange={(event) => onChange(field.name, event.target.value)}
            placeholder={field.placeholder}
            autoComplete={field.type === "email" ? "email" : isSecret ? "off" : undefined}
            disabled={disabled}
            spellCheck={isSecret ? false : undefined}
            {...props}
          />
        )}

        {field.hint ? <div className={isSecret ? "secure-notice" : "field-hint"}>{field.hint}</div> : null}
      </div>
    );
  });
}
