import { useEffect, useState } from "react";
import { oidcCallback, oidcLink } from "./api";
import { useI18n } from "./I18nContext";

export default function OIDCCallback({ onAuth }) {
  const t = useI18n();
  const [error, setError] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (!code) {
      setError(t("oidc.missing_auth_code"));
      return;
    }

    const mode = sessionStorage.getItem("oidc_mode") || "login";
    sessionStorage.removeItem("oidc_mode");

    const handle = async () => {
      try {
        if (mode === "link") {
          await oidcLink(code, state);
          window.location.replace("/");
        } else {
          const user = await oidcCallback(code, state);
          onAuth(user);
          window.history.replaceState({}, "", "/");
        }
      } catch (err) {
        setError(err.message);
      }
    };

    handle();
  }, [onAuth]);

  if (error) {
    return (
      <div style={{ maxWidth: 400, margin: "4rem auto", fontFamily: "system-ui" }}>
        <h2>{t("oidc.error_title")}</h2>
        <p style={{ color: "red" }}>{error}</p>
        <a href="/">{t("oidc.back_to_login")}</a>
      </div>
    );
  }

  return (
    <p style={{ textAlign: "center", marginTop: "4rem" }}>
      {t("oidc.completing_sign_in")}
    </p>
  );
}
