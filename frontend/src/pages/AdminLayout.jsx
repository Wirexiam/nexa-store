import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import Logo from "../components/Logo";
import { api, getAdminKey, setAdminKey } from "../api/client";

export default function AdminLayout() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [key, setKey] = useState(getAdminKey());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function checkSession() {
      if (!getAdminKey()) {
        if (active) setReady(true);
        return;
      }
      try {
        await api.adminHealth();
        if (active) setAuthed(true);
      } catch (err) {
        setAdminKey("");
        if (active) {
          setKey("");
          if (err.status !== 401) setError(err.message);
        }
      } finally {
        if (active) setReady(true);
      }
    }
    checkSession();
    return () => {
      active = false;
    };
  }, []);

  async function onLogin(event) {
    event.preventDefault();
    const nextKey = key.trim();
    if (!nextKey) {
      setError("Введите ключ администратора.");
      return;
    }
    setBusy(true);
    setError("");
    setAdminKey(nextKey);
    try {
      await api.adminHealth();
      setAuthed(true);
    } catch (err) {
      setAdminKey("");
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setAdminKey("");
    setKey("");
    setAuthed(false);
  }

  if (!ready) {
    return (
      <div className="admin-boot" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        Проверяем доступ…
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="login-wrap">
        <div className="login-brand-panel">
          <Link to="/" aria-label="Nexa Store — главная"><Logo light /></Link>
          <div>
            <span className="eyebrow">Private workspace</span>
            <h1>Заказы под контролем.<br />От ссылки до оплаты.</h1>
            <p>Единая CRM для персональных заказов цифровых подписок.</p>
          </div>
          <div className="login-security-note">
            <span aria-hidden="true">◇</span>
            <p><strong>Безопасная работа с данными</strong>Секреты клиентов не попадают в CRM.</p>
          </div>
        </div>
        <main className="login-form-panel">
          <form className="login-card" onSubmit={onLogin}>
            <div className="login-icon" aria-hidden="true">N</div>
            <span className="page-eyebrow">Nexa Store CRM</span>
            <h2>Вход для менеджера</h2>
            <p>Введите API-ключ из настроек backend.</p>
            <div className="field">
              <label htmlFor="admin-key">Ключ администратора</label>
              <input
                id="admin-key"
                type="password"
                autoComplete="current-password"
                value={key}
                onChange={(event) => {
                  setKey(event.target.value);
                  setError("");
                }}
                placeholder="••••••••••••"
                autoFocus
              />
            </div>
            {error ? <div className="admin-alert" role="alert">{error}</div> : null}
            <button className="btn login-button" type="submit" disabled={busy}>
              {busy ? "Проверяем…" : "Войти в CRM"}
            </button>
            <Link className="back-to-store" to="/">← Вернуться в каталог</Link>
          </form>
        </main>
      </div>
    );
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="sidebar-main">
          <Link className="sidebar-logo" to="/admin/orders" aria-label="Nexa Store CRM">
            <Logo light />
            <span>CRM</span>
          </Link>
          <nav aria-label="CRM навигация">
            <NavLink className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} to="/admin/orders">
              <span className="nav-icon" aria-hidden="true">▦</span>
              <span>Заказы</span>
            </NavLink>
            <NavLink className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} to="/admin/catalog">
              <span className="nav-icon" aria-hidden="true">◇</span>
              <span>Каталог</span>
            </NavLink>
            <Link className="nav-link" to="/" target="_blank" rel="noreferrer">
              <span className="nav-icon" aria-hidden="true">↗</span>
              <span>Витрина</span>
              <small>↗</small>
            </Link>
          </nav>
        </div>
        <div className="sidebar-footer">
          <div className="manager-avatar">NS</div>
          <div>
            <strong>Менеджер</strong>
            <span>Администратор</span>
          </div>
          <button type="button" onClick={logout} aria-label="Выйти из CRM" title="Выйти">↪</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
