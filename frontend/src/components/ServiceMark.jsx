import { useEffect, useState } from "react";

function getSafeLogoUrl(logoUrl, logo) {
  const candidate = [logoUrl, logo].find((value) => typeof value === "string" && value.trim());

  if (!candidate) return "";

  const normalized = candidate.trim();

  if (normalized.startsWith("/") && !normalized.startsWith("//")) return normalized;

  try {
    const parsed = new URL(normalized, "https://service-logo.invalid");
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? normalized : "";
  } catch {
    return "";
  }
}

function getMonogram(name, serviceKey) {
  const source = typeof name === "string" && name.trim() ? name : serviceKey;
  const character = typeof source === "string" ? source.match(/[\p{L}\p{N}]/u)?.[0] : null;
  return character?.toLocaleUpperCase() || "N";
}

function ServiceGlyph({ serviceKey, name }) {
  const normalizedKey = typeof serviceKey === "string" ? serviceKey.trim().toLowerCase() : "";

  if (normalizedKey === "chatgpt") {
    return (
      <g fill="none" stroke="currentColor" strokeWidth="3.2">
        {[0, 60, 120].map((rotation) => (
          <rect
            key={rotation}
            x="19"
            y="7.5"
            width="10"
            height="33"
            rx="5"
            transform={`rotate(${rotation} 24 24)`}
          />
        ))}
      </g>
    );
  }

  if (normalizedKey === "claude") {
    return (
      <g fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="3.2">
        <path d="M24 7v34M7 24h34M12 12l24 24M36 12 12 36" />
        <path d="m17 8 14 32M40 17 8 31M31 8 17 40M40 31 8 17" strokeWidth="2" />
      </g>
    );
  }

  if (normalizedKey === "midjourney") {
    return (
      <g fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.7">
        <path d="M8 34h32M12 34c4.5 5 19.5 5 24 0" />
        <path d="M24 8v25M23 11 11 29h12M26 15l12 14H26" />
      </g>
    );
  }

  if (normalizedKey === "notion") {
    return (
      <g fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2.8">
        <path d="M11 10.5 34 8l4 4v25l-24 3-4-4z" />
        <path d="m15 15 5-1 12 17V13l-4 .5M16 35V15" />
      </g>
    );
  }

  return (
    <text
      x="24"
      y="25"
      fill="currentColor"
      fontSize="24"
      fontWeight="800"
      textAnchor="middle"
      dominantBaseline="middle"
    >
      {getMonogram(name, serviceKey)}
    </text>
  );
}

export default function ServiceMark({
  serviceKey,
  name,
  accent = "#0f766e",
  size = 88,
  compact = false,
  logo,
  logoUrl,
}) {
  const safeLogoUrl = getSafeLogoUrl(logoUrl, logo);
  const [failedLogoUrl, setFailedLogoUrl] = useState("");

  useEffect(() => {
    setFailedLogoUrl("");
  }, [safeLogoUrl]);

  const showRemoteLogo = Boolean(safeLogoUrl && failedLogoUrl !== safeLogoUrl);
  const accessibleName = name || serviceKey || "Сервис";

  return (
    <span
      className={`service-logo ${compact ? "compact" : ""}`}
      style={{ width: size, height: size, "--service-accent": accent }}
      role="img"
      aria-label={`Логотип сервиса ${accessibleName}`}
    >
      {showRemoteLogo ? (
        <img
          key={safeLogoUrl}
          src={safeLogoUrl}
          alt=""
          aria-hidden="true"
          decoding="async"
          draggable="false"
          referrerPolicy="no-referrer"
          onError={() => setFailedLogoUrl(safeLogoUrl)}
          style={{ display: "block", width: "64%", height: "64%", objectFit: "contain" }}
        />
      ) : (
        <svg viewBox="0 0 48 48" aria-hidden="true">
          <ServiceGlyph serviceKey={serviceKey} name={name} />
        </svg>
      )}
    </span>
  );
}
