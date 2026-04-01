import { useState } from "react";
import { useI18n } from "./I18nContext";
import { fetchMe, oidcLogin, oidcUnlink } from "./api";
import TopBar from "./TopBar";
import "./AccountPage.css";

export default function AccountPage({ user, oidcEnabled, onUserUpdate, onBack, onLogout, onSettings }) {
  const t = useI18n();
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
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
    setChangingPw(true); setError(null); setSuccess(null);
    try {
      const res = await fetch("/api/auth/change-password/", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
      setSuccess(t("account.password_changed") || "Password changed.");
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
    } catch (err) { setError(err.message); }
    finally { setChangingPw(false); }
  };

  const handleLinkOIDC = async () => {
    try {
      sessionStorage.setItem("oidc_mode", "link");
      const { authorization_url } = await oidcLogin();
      window.location.href = authorization_url;
    } catch (err) { setError(err.message); }
  };

  const handleUnlinkOIDC = async (identityId) => {
    try {
      await oidcUnlink(identityId);
      const updated = await fetchMe();
      onUserUpdate(updated);
    } catch (err) { setError(err.message); }
  };

  return (
    <div>
      <TopBar username={user.username} onHome={onBack} onAccount={onBack} onSettings={onSettings} onLogout={onLogout} />
      <div className="narrow-container">
        <h2>{t("account.title") || "Account"}</h2>
        {error && <p className="error-text">{error}</p>}
        {success && <p className="success-text">{success}</p>}

        <section className="account-section">
          <h3>{t("account.change_password") || "Change Password"}</h3>
          <form onSubmit={handleChangePassword}>
            <div className="mb-8">
              <label className="form-label">{t("account.current_password") || "Current password"}</label>
              <input type="password" className="input" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required minLength={8} />
            </div>
            <div className="mb-8">
              <label className="form-label">{t("account.new_password") || "New password"}</label>
              <input type="password" className="input" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
            </div>
            <div className="mb-12">
              <label className="form-label">{t("account.confirm_password") || "Confirm new password"}</label>
              <input type="password" className="input" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={8} />
            </div>
            <button type="submit" disabled={changingPw} className="btn btn-primary">
              {changingPw ? "…" : (t("account.change_password_btn") || "Change Password")}
            </button>
          </form>
        </section>

        {oidcEnabled && (
          <section className="account-section">
            <h3>{t("account.oidc_identities") || "Linked OIDC Identities"}</h3>
            {user.oidc_identities?.length > 0 ? (
              <ul className="account-oidc-list">
                {user.oidc_identities.map((id) => (
                  <li key={id.id} className="account-oidc-item">
                    <span>{id.provider} ({id.email || t("oidc.no_email") || "no email"})</span>
                    <button type="button" onClick={() => handleUnlinkOIDC(id.id)} className="btn btn-danger btn-small">
                      {t("oidc.unlink") || "Unlink"}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-text">{t("oidc.no_identities") || "No OIDC identities linked."}</p>
            )}
            <button type="button" onClick={handleLinkOIDC} className="btn btn-primary mt-8">
              {t("oidc.link_account") || "Link OIDC Account"}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
