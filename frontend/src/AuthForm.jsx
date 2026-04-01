import { useState } from "react";
import { login, register, oidcLogin } from "./api";
import { useI18n } from "./I18nContext";
import "./AuthForm.css";

export default function AuthForm({ onAuth, oidcEnabled }) {
  const t = useI18n();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const user = isRegister
        ? await register(username, password)
        : await login(username, password);
      onAuth(user);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleOIDC = async () => {
    setError(null);
    try {
      sessionStorage.setItem("oidc_mode", "login");
      const { authorization_url } = await oidcLogin();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="centered-container">
      <h2>{isRegister ? t("auth.register") : t("auth.login")}</h2>
      {error && <p className="error-text">{error}</p>}
      <form onSubmit={handleSubmit}>
        <div className="auth-form">
          <label htmlFor="username">{t("auth.username")}: </label>
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="auth-form">
          <label htmlFor="password">{t("auth.password")}: </label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </div>
        <button type="submit">{isRegister ? t("auth.register") : t("auth.login")}</button>
      </form>
      {oidcEnabled && (
        <div className="auth-oidc">
          <hr />
          <button type="button" onClick={handleOIDC} className="auth-oidc-btn">{t("auth.oidc_sign_in")}</button>
        </div>
      )}
      <p className="auth-toggle">
        {isRegister ? t("auth.already_have_account") : t("auth.no_account_yet")}{" "}
        <button type="button" onClick={() => { setIsRegister(!isRegister); setError(null); }} className="btn-link">
          {isRegister ? t("auth.login") : t("auth.register")}
        </button>
      </p>
    </div>
  );
}
