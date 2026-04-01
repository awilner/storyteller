import { useEffect, useState, useRef } from "react";
import { oidcCallback, oidcLink } from "./api";
import { useI18n } from "./I18nContext";
import "./OIDCCallback.css";

export default function OIDCCallback({ onAuth }) {
  const t = useI18n();
  const [error, setError] = useState(null);
  const onAuthRef = useRef(onAuth);
  onAuthRef.current = onAuth;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    if (!code) { setError(t("oidc.missing_auth_code")); return; }
    const mode = sessionStorage.getItem("oidc_mode") || "login";
    sessionStorage.removeItem("oidc_mode");
    const handle = async () => {
      try {
        if (mode === "link") {
          await oidcLink(code, state);
          window.location.replace("/");
        } else {
          const user = await oidcCallback(code, state);
          window.history.replaceState({}, "", "/");
          onAuthRef.current(user);
        }
      } catch (err) { setError(err.message); }
    };
    handle();
  }, []);

  if (error) {
    return (
      <div className="oidc-callback-container">
        <h2>{t("oidc.error_title")}</h2>
        <p className="error-text">{error}</p>
        <a href="/">{t("oidc.back_to_login")}</a>
      </div>
    );
  }
  return <p className="oidc-completing">{t("oidc.completing_sign_in")}</p>;
}
