import { useState, useEffect } from "react";
import { fetchAppVersion } from "./api";
import "./VersionBadge.css";

export default function VersionBadge() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    fetchAppVersion().then(setInfo).catch(() => {});
  }, []);

  if (!info) return null;

  return (
    <div className="version-badge">
      <a href={info.repo_url} target="_blank" rel="noopener noreferrer" className="version-badge-link">
        Storyteller v{info.current}
      </a>
      {info.latest && (
        <a href={info.latest_url} target="_blank" rel="noopener noreferrer" className="version-badge-update">
          ⬆ v{info.latest} available
        </a>
      )}
    </div>
  );
}
