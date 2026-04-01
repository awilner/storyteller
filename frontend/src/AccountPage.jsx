import { useState } from "react";
import { useI18n } from "./I18nContext";
import { fetchMe, oidcLogin, oidcUnlink } from "./api";
import TopBar from "./TopBar";

export default function AccountPage({ user, oidcEnabled, onUserUpdate, onBack, onLogout, onSettings }) {
  const t = useI18n();
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // ── Password change ────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPw, setChangingPw] = useState(false);

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError(t("account.passwords_mismatch") || "Passwords do not match.");
      return;
    }
    setChangingPw(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch("/api/auth/change-password/", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "",
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
      setSuccess(t("account.password_changed") || "Password changed.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err.message);
    } finally {
      setChangingPw(false);
    }
  };

  // ── OIDC management ────────────────────────────────────────
  const handleLinkOIDC = async () => {
    try {
      sessionStorage.setItem("oidc_mode", "link");
      const { authorization_url } = await oidcLogin();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUnlinkOIDC = async (identityId) => {
    try {
      await oidcUnlink(identityId);
      const updated = await fetchMe();
      onUserUpdate(updated);
    } catch (err) {
      setError(err.message);
    }
  };

  const inputStyle = { width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, boxSizing: "border-box" };
  const btnStyle = { cursor: "pointer", border: "1px solid #4a90d9", borderRadius: 4, padding: "6px 14px", background: "#4a90d9", color: "#fff", fontWeight: 600, fontSize: 13 };

  return (
    <div>
      <TopBar username={user.username} onHome={onBack} onAccount={onBack} onSettings={onSettings} onLogout={onLogout} />
      <div style={{ maxWidth: 500, margin: "2rem auto", padding: "0 16px", fontFamily: "system-ui" }}>
        <h2>{t("account.title") || "Account"}</h2>

        {error && <p style={{ color: "red", fontSize: 13 }}>{error}</p>}
        {success && <p style={{ color: "green", fontSize: 13 }}>{success}</p>}

        {/* Password change */}
        <section style={{ marginBottom: "2rem" }}>
          <h3>{t("account.change_password") || "Change Password"}</h3>
          <form onSubmit={handleChangePassword}>
            <div style={{ marginBottom: 8 }}>
              <label style={{ display: "block", fontSize: 13, marginBottom: 2 }}>{t("account.current_password") || "Current password"}</label>
              <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required minLength={8} style={inputStyle} />
            </div>
            <div style={{ marginBottom: 8 }}>
              <label style={{ display: "block", fontSize: 13, marginBottom: 2 }}>{t("account.new_password") || "New password"}</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} style={inputStyle} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontSize: 13, marginBottom: 2 }}>{t("account.confirm_password") || "Confirm new password"}</label>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={8} style={inputStyle} />
            </div>
            <button type="submit" disabled={changingPw} style={btnStyle}>
              {changingPw ? "…" : (t("account.change_password_btn") || "Change Password")}
            </button>
          </form>
        </section>

        {/* OIDC identities */}
        {oidcEnabled && (
          <section style={{ marginBottom: "2rem" }}>
            <h3>{t("account.oidc_identities") || "Linked OIDC Identities"}</h3>
            {user.oidc_identities?.length > 0 ? (
              <ul style={{ padding: 0, listStyle: "none" }}>
                {user.oidc_identities.map((id) => (
                  <li key={id.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #eee" }}>
                    <span style={{ fontSize: 14 }}>{id.provider} ({id.email || t("oidc.no_email") || "no email"})</span>
                    <button type="button" onClick={() => handleUnlinkOIDC(id.id)}
                      style={{ cursor: "pointer", border: "1px solid #dc3545", borderRadius: 4, padding: "4px 10px", background: "#fff", color: "#dc3545", fontSize: 12 }}>
                      {t("oidc.unlink") || "Unlink"}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "#888", fontSize: 14 }}>{t("oidc.no_identities") || "No OIDC identities linked."}</p>
            )}
            <button type="button" onClick={handleLinkOIDC} style={{ ...btnStyle, marginTop: 8 }}>
              {t("oidc.link_account") || "Link OIDC Account"}
            </button>
          </section>
        )}

      </div>
    </div>
  );
}
