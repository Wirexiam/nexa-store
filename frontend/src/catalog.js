export function serviceSlug(service) {
  return service?.slug || service?.key || service?.id || "service";
}

export function serviceLogo(service) {
  return service?.logo_url || service?.logo || "";
}

export function serviceCategory(service) {
  const category = service?.category;
  if (category && typeof category === "object") {
    return {
      id: category.id || category.slug || category.name,
      slug: category.slug || category.name || category.id,
      name: category.name || category.slug || "Без категории",
    };
  }
  const name = service?.category_name || category || "Без категории";
  return {
    id: service?.category_id || service?.category_slug || name,
    slug: service?.category_slug || String(name).toLocaleLowerCase("ru"),
    name,
  };
}

export function servicePlans(service) {
  return (service?.levels || service?.plans || []).map((plan) => ({
    ...plan,
    id: plan.key || plan.public_id || plan.id,
    db_id: plan.record_id || plan.db_id || (plan.key || plan.public_id ? plan.id : undefined),
    name: plan.name || plan.label || plan.key || plan.id,
    description: plan.description || "",
    prices: plan.prices || {},
    is_active: plan.is_active ?? plan.active ?? true,
  }));
}

export function servicePeriods(service) {
  return (service?.periods || []).map((period) => ({
    ...period,
    id: period.key || period.public_id || period.id,
    db_id: period.record_id || period.db_id || (period.key || period.public_id ? period.id : undefined),
    name: period.name || period.label || period.key || period.id,
    duration: period.duration || period.duration_days || "",
    is_active: period.is_active ?? period.active ?? true,
  }));
}

export function optionMatches(option, value) {
  if (!option || !value) return false;
  return [option.id, option.key, option.public_id, option.db_id, option.name]
    .filter(Boolean)
    .some((candidate) => String(candidate) === String(value));
}

export function priceFor(service, plan, period) {
  if (!plan || !period) return null;
  const candidates = [period.id, period.key, period.public_id, period.db_id, period.name].filter(Boolean);
  for (const key of candidates) {
    const amount = plan.prices?.[key];
    if (amount !== undefined && amount !== null && amount !== "") {
      const parsed = Number(amount);
      return Number.isFinite(parsed) ? parsed : null;
    }
  }
  const matrix = service?.prices || service?.price_matrix || [];
  if (Array.isArray(matrix)) {
    const row = matrix.find((item) =>
      [item.plan_id, item.level_id, item.plan_key].some((value) => optionMatches(plan, value)) &&
      [item.period_id, item.period_key].some((value) => optionMatches(period, value))
    );
    if (row) {
      const parsed = Number(row.amount ?? row.price);
      return Number.isFinite(parsed) ? parsed : null;
    }
  }
  const direct = Number(plan.price ?? service?.price);
  return Number.isFinite(direct) ? direct : null;
}

export function minimumServicePrice(service) {
  const amounts = servicePlans(service).flatMap((plan) =>
    servicePeriods(service).map((period) => priceFor(service, plan, period))
  ).filter((amount) => amount !== null && amount >= 0);
  return amounts.length ? Math.min(...amounts) : null;
}

export function serviceInstructions(service) {
  const value = service?.instructions ?? service?.instruction?.content ?? service?.instruction ?? "";
  return String(value || "");
}

export function workflowOf(serviceOrOrder) {
  const workflow = serviceOrOrder?.workflow;
  if (workflow && typeof workflow === "object") return workflow;
  return {
    execution_type: serviceOrOrder?.workflow_type || serviceOrOrder?.execution_type || "manual",
    active: true,
    requires_manual_action: serviceOrOrder?.requires_manual_action ?? true,
    description: "",
  };
}
