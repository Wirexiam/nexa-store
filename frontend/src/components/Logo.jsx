export default function Logo({ light = false, size = 32 }) {
  return (
    <span className="logo brand">
      <svg className="logo-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
        <defs>
          <linearGradient id="nexa" x1="4" y1="4" x2="28" y2="28">
            <stop stopColor="#5eead4" />
            <stop offset="1" stopColor="#818cf8" />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="9" fill="url(#nexa)" />
        <path d="M9 22V10h3.2l7.6 8.4V10H23v12h-3.2L12.2 13.6V22H9z" fill={light ? "#04221c" : "#07111f"} />
      </svg>
      Nexa Store
    </span>
  );
}
