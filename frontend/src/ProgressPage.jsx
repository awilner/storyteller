import { useState, useEffect, useCallback } from "react";
import { useI18n } from "./I18nContext";
import { fetchProgress, updateProgress, resetSession } from "./api";
import "./ProgressPage.css";

const DEFAULT_VISIBLE = 10;

function ProgressBar({ current, target, label }) {
  const isNeg = current < 0;
  const pct = target > 0 ? Math.min(Math.round((Math.abs(current) / target) * 100), 100) : 0;
  return (
    <div className="progress-bar-wrapper">
      <div className="progress-bar-track">
        {isNeg ? (
          <div className="progress-bar-fill progress-bar-fill--negative" style={{ width: `${pct}%` }} />
        ) : (
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        )}
      </div>
      <span className="progress-bar-label">{label} ({isNeg ? "-" : ""}{pct}%)</span>
    </div>
  );
}

/* Simple linear regression: returns { slope, intercept } */
function linearRegression(xs, ys) {
  const n = xs.length;
  if (n < 2) return null;
  let sx = 0, sy = 0, sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) {
    sx += xs[i]; sy += ys[i]; sxy += xs[i] * ys[i]; sxx += xs[i] * xs[i];
  }
  const denom = n * sxx - sx * sx;
  if (denom === 0) return null;
  const slope = (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  return { slope, intercept };
}

/* Zoom / scroll controls shared by all charts */
function ChartControls({ offset, setOffset, visible, setVisible, total }) {
  const canLeft = offset > 0;
  const canRight = offset + visible < total;
  return (
    <div className="chart-controls">
      <button type="button" disabled={!canLeft} onClick={() => setOffset(Math.max(0, offset - Math.max(1, Math.floor(visible / 2))))} aria-label="Scroll left">◀</button>
      <button type="button" disabled={visible >= total} onClick={() => { const nv = Math.min(total, visible + 5); setVisible(nv); setOffset(Math.min(offset, Math.max(0, total - nv))); }} aria-label="Zoom out">🔍−</button>
      <button type="button" disabled={visible <= 3} onClick={() => { const nv = Math.max(3, visible - 5); setOffset(Math.min(offset, Math.max(0, total - nv))); setVisible(nv); }} aria-label="Zoom in">🔍+</button>
      <button type="button" disabled={!canRight} onClick={() => setOffset(Math.min(total - visible, offset + Math.max(1, Math.floor(visible / 2))))} aria-label="Scroll right">▶</button>
      <span className="chart-controls-info">{offset + 1}–{Math.min(offset + visible, total)} / {total}</span>
    </div>
  );
}

/* Pick up to maxLabels evenly-spaced indices from an array of length n */
function pickLabelIndices(n, maxLabels = 10) {
  if (n <= maxLabels) return Array.from({ length: n }, (_, i) => i);
  const indices = [0];
  const step = (n - 1) / (maxLabels - 1);
  for (let i = 1; i < maxLabels - 1; i++) indices.push(Math.round(step * i));
  indices.push(n - 1);
  return [...new Set(indices)];
}


function ProgressGraph({ snapshots, manuscriptTarget, t }) {
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const total = snapshots?.length || 0;
  const [visible, setVisible] = useState(Math.min(DEFAULT_VISIBLE, total));
  const [offset, setOffset] = useState(Math.max(0, total - visible));

  useEffect(() => {
    const v = Math.min(DEFAULT_VISIBLE, total);
    setVisible(v);
    setOffset(Math.max(0, total - v));
  }, [total]);

  if (!snapshots || snapshots.length < 2) {
    return <p className="progress-insufficient">{t("progress.insufficient_data")}</p>;
  }

  const slice = snapshots.slice(offset, offset + visible);
  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const width = 600;
  const height = 200;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const dates = slice.map((s) => new Date(s.date));
  const counts = slice.map((s) => s.word_count);

  const minDate = dates[0].getTime();
  const maxDate = dates[dates.length - 1].getTime();
  const dateRange = maxDate - minDate || 1;

  let maxCount = Math.max(...counts);
  if (manuscriptTarget) maxCount = Math.max(maxCount, manuscriptTarget);
  maxCount = maxCount || 1;

  const xScale = (d) => padding.left + ((d.getTime() - minDate) / dateRange) * innerW;
  const yScale = (v) => padding.top + innerH - (v / maxCount) * innerH;

  const points = slice.map((s, i) => `${xScale(dates[i])},${yScale(s.word_count)}`).join(" ");
  const formatDate = (d) => `${d.getMonth() + 1}/${d.getDate()}`;

  // Trend line from last 10 points of the FULL dataset
  const trendN = Math.min(10, snapshots.length);
  const trendSlice = snapshots.slice(-trendN);
  const trendXs = trendSlice.map((s) => new Date(s.date).getTime());
  const trendYs = trendSlice.map((s) => s.word_count);
  const reg = linearRegression(trendXs, trendYs);

  // Projected completion
  let projectedDate = null;
  if (reg && reg.slope > 0 && manuscriptTarget && trendYs[trendYs.length - 1] < manuscriptTarget) {
    const tMs = (manuscriptTarget - reg.intercept) / reg.slope;
    projectedDate = new Date(tMs);
  }

  // Trend line endpoints clipped to visible range
  let trendLine = null;
  if (reg && reg.slope !== 0) {
    const x1t = minDate;
    const x2t = maxDate;
    const y1t = reg.slope * x1t + reg.intercept;
    const y2t = reg.slope * x2t + reg.intercept;
    trendLine = { x1: xScale(new Date(x1t)), y1: yScale(y1t), x2: xScale(new Date(x2t)), y2: yScale(y2t) };
  }

  return (
    <div>
      <div style={{ position: "relative" }}>
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + innerH} stroke="#ccc" />
          <line x1={padding.left} y1={padding.top + innerH} x2={padding.left + innerW} y2={padding.top + innerH} stroke="#ccc" />
          <text x={padding.left - 5} y={padding.top + 4} textAnchor="end" fontSize="10" fill="#999">{maxCount.toLocaleString()}</text>
          <text x={padding.left - 5} y={padding.top + innerH + 4} textAnchor="end" fontSize="10" fill="#999">0</text>

          {/* X axis date labels */}
          {pickLabelIndices(slice.length).map((i) => (
            <text key={i} x={xScale(dates[i])} y={height - 5} textAnchor="middle" fontSize="10" fill="#999">{formatDate(dates[i])}</text>
          ))}

          {/* Manuscript target */}
          {manuscriptTarget && manuscriptTarget <= maxCount && (
            <line x1={padding.left} y1={yScale(manuscriptTarget)} x2={padding.left + innerW} y2={yScale(manuscriptTarget)} stroke="#e74c3c" strokeWidth="1" strokeDasharray="4,3" />
          )}

          {/* Data line */}
          <polyline points={points} fill="none" stroke="#4a90d9" strokeWidth="2" />

          {/* Trend line */}
          {trendLine && (
            <line x1={trendLine.x1} y1={trendLine.y1} x2={trendLine.x2} y2={trendLine.y2} stroke="#f39c12" strokeWidth="1.5" strokeDasharray="6,3" />
          )}

          {/* Data points */}
          {slice.map((s, i) => (
            <circle key={i} cx={xScale(dates[i])} cy={yScale(s.word_count)}
              r={hoveredPoint === i ? 5 : 3} fill={hoveredPoint === i ? "#2a6cb8" : "#4a90d9"}
              stroke="#fff" strokeWidth="1.5" style={{ cursor: "pointer" }}
              onMouseEnter={() => setHoveredPoint(i)} onMouseLeave={() => setHoveredPoint(null)} />
          ))}
        </svg>
        {hoveredPoint !== null && (() => {
          const s = slice[hoveredPoint];
          const cx = xScale(dates[hoveredPoint]);
          const cy = yScale(s.word_count);
          const pctStr = manuscriptTarget ? ` (${Math.min(Math.round((s.word_count / manuscriptTarget) * 100), 100)}%)` : "";
          return (
            <div className="progress-tooltip" style={{ left: `${(cx / width) * 100}%`, top: `${(cy / height) * 100}%` }}>
              <div>{formatDate(dates[hoveredPoint])}</div>
              <div>{s.word_count.toLocaleString()} {t("progress.words_label")}{pctStr}</div>
            </div>
          );
        })()}
      </div>
      {projectedDate && (
        <p className="progress-projection">
          {t("progress.projected_completion")}: {projectedDate.toLocaleDateString()}
        </p>
      )}
      {total > DEFAULT_VISIBLE && (
        <ChartControls offset={offset} setOffset={setOffset} visible={visible} setVisible={setVisible} total={total} />
      )}
    </div>
  );
}


function DailyBarChart({ dailyCounts, dailyTarget, t }) {
  const [hoveredBar, setHoveredBar] = useState(null);

  if (!dailyCounts || dailyCounts.length === 0) {
    return <p className="progress-insufficient">{t("progress.insufficient_data")}</p>;
  }

  const allDeltas = dailyCounts.map((d) => ({ date: d.date, words: d.word_count }));

  const total = allDeltas.length;
  const [visible, setVisible] = useState(Math.min(DEFAULT_VISIBLE, total));
  const [offset, setOffset] = useState(Math.max(0, total - visible));

  useEffect(() => {
    const v = Math.min(DEFAULT_VISIBLE, total);
    setVisible(v);
    setOffset(Math.max(0, total - v));
  }, [total]);

  const deltas = allDeltas.slice(offset, offset + visible);

  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const width = 600;
  const height = 200;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  let maxVal = Math.max(...deltas.map((d) => Math.abs(d.words)), 1);
  if (dailyTarget) maxVal = Math.max(maxVal, dailyTarget);
  const minVal = Math.min(...deltas.map((d) => d.words), 0);
  const hasNeg = minVal < 0;
  const range = hasNeg ? maxVal - minVal : maxVal;
  const zeroY = hasNeg ? padding.top + (maxVal / range) * innerH : padding.top + innerH;

  const barWidth = Math.max(4, (innerW / deltas.length) - 2);
  const formatDate = (d) => { const dt = new Date(d); return `${dt.getMonth() + 1}/${dt.getDate()}`; };

  return (
    <div>
      <div style={{ position: "relative" }}>
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + innerH} stroke="#ccc" />
          <line x1={padding.left} y1={padding.top + innerH} x2={padding.left + innerW} y2={padding.top + innerH} stroke="#ccc" />
          <text x={padding.left - 5} y={padding.top + 4} textAnchor="end" fontSize="10" fill="#999">{maxVal.toLocaleString()}</text>
          {hasNeg && <text x={padding.left - 5} y={padding.top + innerH + 4} textAnchor="end" fontSize="10" fill="#999">{minVal.toLocaleString()}</text>}
          {!hasNeg && <text x={padding.left - 5} y={padding.top + innerH + 4} textAnchor="end" fontSize="10" fill="#999">0</text>}
          {hasNeg && <line x1={padding.left} y1={zeroY} x2={padding.left + innerW} y2={zeroY} stroke="#aaa" strokeWidth="0.5" />}

          {deltas.map((d, i) => {
            const isNeg = d.words < 0;
            const barH = (Math.abs(d.words) / range) * innerH;
            const x = padding.left + (i / deltas.length) * innerW + 1;
            const y = isNeg ? zeroY : zeroY - barH;
            return (
              <rect key={i} x={x} y={y} width={barWidth} height={barH}
                fill={isNeg ? (hoveredBar === i ? "#a93226" : "#e74c3c") : (hoveredBar === i ? "#2a6cb8" : "#4a90d9")}
                rx="2" style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredBar(i)} onMouseLeave={() => setHoveredBar(null)} />
            );
          })}

          {dailyTarget && (
            <>
              <line x1={padding.left} y1={zeroY - (dailyTarget / range) * innerH}
                x2={padding.left + innerW} y2={zeroY - (dailyTarget / range) * innerH}
                stroke="#e74c3c" strokeWidth="1" strokeDasharray="4,3" />
              <text x={padding.left - 5} y={zeroY - (dailyTarget / range) * innerH + 3} textAnchor="end" fontSize="9" fill="#e74c3c">
                {dailyTarget.toLocaleString()}
              </text>
            </>
          )}

          {/* X axis date labels */}
          {pickLabelIndices(deltas.length).map((i) => {
            const x = padding.left + (i / deltas.length) * innerW + 1 + barWidth / 2;
            return <text key={i} x={x} y={height - 5} textAnchor="middle" fontSize="10" fill="#999">{formatDate(deltas[i].date)}</text>;
          })}
        </svg>
        {hoveredBar !== null && (() => {
          const d = deltas[hoveredBar];
          const x = padding.left + (hoveredBar / deltas.length) * innerW + barWidth / 2;
          const barH = (Math.abs(d.words) / range) * innerH;
          const y = d.words < 0 ? zeroY : zeroY - barH;
          return (
            <div className="progress-tooltip" style={{ left: `${(x / width) * 100}%`, top: `${(y / height) * 100}%` }}>
              <div>{formatDate(d.date)}</div>
              <div>{d.words.toLocaleString()} {t("progress.words_label")}</div>
            </div>
          );
        })()}
      </div>
      {total > DEFAULT_VISIBLE && (
        <ChartControls offset={offset} setOffset={setOffset} visible={visible} setVisible={setVisible} total={total} />
      )}
    </div>
  );
}


function SessionBarChart({ sessions, sessionTarget, t }) {
  const [hoveredBar, setHoveredBar] = useState(null);

  const sorted = sessions ? [...sessions].sort((a, b) => new Date(a.started_at) - new Date(b.started_at)) : [];
  const total = sorted.length;
  const [visible, setVisible] = useState(Math.min(DEFAULT_VISIBLE, total));
  const [offset, setOffset] = useState(Math.max(0, total - visible));

  useEffect(() => {
    const v = Math.min(DEFAULT_VISIBLE, total);
    setVisible(v);
    setOffset(Math.max(0, total - v));
  }, [total]);

  if (!sessions || sessions.length === 0) {
    return <p className="progress-insufficient">{t("progress.no_sessions")}</p>;
  }

  const slice = sorted.slice(offset, offset + visible);

  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const width = 600;
  const height = 200;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  let maxVal = Math.max(...slice.map((s) => Math.abs(s.word_count)), 1);
  if (sessionTarget) maxVal = Math.max(maxVal, sessionTarget);
  const minVal = Math.min(...slice.map((s) => s.word_count), 0);
  const hasNeg = minVal < 0;
  const range = hasNeg ? maxVal - minVal : maxVal;
  const zeroY = hasNeg ? padding.top + (maxVal / range) * innerH : padding.top + innerH;

  const barWidth = Math.max(4, (innerW / slice.length) - 2);
  const formatDt = (iso) => {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  return (
    <div>
      <div style={{ position: "relative" }}>
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + innerH} stroke="#ccc" />
          <line x1={padding.left} y1={padding.top + innerH} x2={padding.left + innerW} y2={padding.top + innerH} stroke="#ccc" />
          <text x={padding.left - 5} y={padding.top + 4} textAnchor="end" fontSize="10" fill="#999">{maxVal.toLocaleString()}</text>
          {hasNeg && <text x={padding.left - 5} y={padding.top + innerH + 4} textAnchor="end" fontSize="10" fill="#999">{minVal.toLocaleString()}</text>}
          {!hasNeg && <text x={padding.left - 5} y={padding.top + innerH + 4} textAnchor="end" fontSize="10" fill="#999">0</text>}
          {hasNeg && <line x1={padding.left} y1={zeroY} x2={padding.left + innerW} y2={zeroY} stroke="#aaa" strokeWidth="0.5" />}

          {slice.map((s, i) => {
            const isNeg = s.word_count < 0;
            const barH = (Math.abs(s.word_count) / range) * innerH;
            const x = padding.left + (i / slice.length) * innerW + 1;
            const y = isNeg ? zeroY : zeroY - barH;
            return (
              <rect key={i} x={x} y={y} width={barWidth} height={barH}
                fill={isNeg ? (hoveredBar === i ? "#a93226" : "#e74c3c") : (hoveredBar === i ? "#1e8449" : "#27ae60")}
                rx="2" style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredBar(i)} onMouseLeave={() => setHoveredBar(null)} />
            );
          })}

          {sessionTarget && (
            <>
              <line x1={padding.left} y1={zeroY - (sessionTarget / range) * innerH}
                x2={padding.left + innerW} y2={zeroY - (sessionTarget / range) * innerH}
                stroke="#e74c3c" strokeWidth="1" strokeDasharray="4,3" />
              <text x={padding.left - 5} y={zeroY - (sessionTarget / range) * innerH + 3} textAnchor="end" fontSize="9" fill="#e74c3c">
                {sessionTarget.toLocaleString()}
              </text>
            </>
          )}

          {/* X axis date labels */}
          {pickLabelIndices(slice.length).map((i) => {
            const x = padding.left + (i / slice.length) * innerW + 1 + barWidth / 2;
            return <text key={i} x={x} y={height - 5} textAnchor="middle" fontSize="10" fill="#999">{formatDt(slice[i].started_at)}</text>;
          })}
        </svg>
        {hoveredBar !== null && hoveredBar < slice.length && (() => {
          const s = slice[hoveredBar];
          const x = padding.left + (hoveredBar / slice.length) * innerW + barWidth / 2;
          const barH = (Math.abs(s.word_count) / range) * innerH;
          const y = s.word_count < 0 ? zeroY : zeroY - barH;
          return (
            <div className="progress-tooltip" style={{ left: `${(x / width) * 100}%`, top: `${(y / height) * 100}%` }}>
              <div>{formatDt(s.started_at)}</div>
              <div>{s.word_count.toLocaleString()} {t("progress.words_label")}</div>
            </div>
          );
        })()}
      </div>
      {total > DEFAULT_VISIBLE && (
        <ChartControls offset={offset} setOffset={setOffset} visible={visible} setVisible={setVisible} total={total} />
      )}
    </div>
  );
}


export default function ProgressPage({ projectId, onClose, onDataLoaded, initialData }) {
  const t = useI18n();
  const [data, setData] = useState(initialData || null);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState(null);

  const [manuscriptTarget, setManuscriptTarget] = useState(() =>
    initialData?.manuscript_target != null ? String(initialData.manuscript_target) : ""
  );
  const [dailyTarget, setDailyTarget] = useState(() =>
    initialData?.daily_target != null ? String(initialData.daily_target) : ""
  );
  const [sessionTarget, setSessionTarget] = useState(() =>
    initialData?.session_target != null ? String(initialData.session_target) : ""
  );
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const d = await fetchProgress(projectId);
      setData(d);
      if (onDataLoaded) onDataLoaded(d);
      setManuscriptTarget(d.manuscript_target != null ? String(d.manuscript_target) : "");
      setDailyTarget(d.daily_target != null ? String(d.daily_target) : "");
      setSessionTarget(d.session_target != null ? String(d.session_target) : "");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { if (!initialData) load(); }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        manuscript_target: manuscriptTarget ? Number(manuscriptTarget) : null,
        daily_target: dailyTarget ? Number(dailyTarget) : null,
        session_target: sessionTarget ? Number(sessionTarget) : null,
      };
      await updateProgress(projectId, payload);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      setError(null);
      await resetSession(projectId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return <div className="progress-page"><p className="progress-loading">{t("common.loading")}</p></div>;

  return (
    <div className="progress-page">
      <button type="button" className="progress-back-btn" onClick={onClose}>
        ← {t("progress.back_to_editor")}
      </button>
      <h2>{t("progress.title")}</h2>

      {error && <p className="progress-error">{error}</p>}

      <div className="progress-targets-form">
        <div className="progress-field">
          <label>{t("progress.manuscript_target")}</label>
          <input type="number" min="1" value={manuscriptTarget} onChange={(e) => setManuscriptTarget(e.target.value)} />
        </div>
        <div className="progress-field">
          <label>{t("progress.daily_target")}</label>
          <input type="number" min="1" value={dailyTarget} onChange={(e) => setDailyTarget(e.target.value)} />
        </div>
        <div className="progress-field">
          <label>{t("progress.session_target")}</label>
          <input type="number" min="1" value={sessionTarget} onChange={(e) => setSessionTarget(e.target.value)} />
        </div>
        <button type="button" className="progress-save-btn" onClick={handleSave} disabled={saving}>
          {saving ? t("editor.saving") : t("progress.save_targets")}
        </button>
      </div>

      {data && (
        <>
          {data.manuscript_target != null && (
            <div className="progress-section">
              <h3>{t("progress.manuscript_target")}</h3>
              <ProgressBar current={data.current_word_count} target={data.manuscript_target}
                label={`${data.current_word_count.toLocaleString()} / ${data.manuscript_target.toLocaleString()}`} />
            </div>
          )}

          {data.daily_target != null && (
            <div className="progress-section">
              <h3>{t("progress.words_written_today")}</h3>
              <ProgressBar current={data.daily_word_count} target={data.daily_target}
                label={`${data.daily_word_count.toLocaleString()} / ${data.daily_target.toLocaleString()}`} />
            </div>
          )}

          {data.session_target != null && (
            <div className="progress-section">
              <h3>{t("progress.session_words")}</h3>
              <ProgressBar current={data.session_word_count} target={data.session_target}
                label={`${data.session_word_count.toLocaleString()} / ${data.session_target.toLocaleString()}`} />
              <button type="button" className="progress-reset-btn" onClick={handleReset} style={{ marginTop: 6 }}>
                {t("progress.reset_session")}
              </button>
            </div>
          )}

          <div className="progress-graph">
            <h3>{t("progress.word_count_over_time")}</h3>
            <ProgressGraph snapshots={data.snapshots} manuscriptTarget={data.manuscript_target} t={t} />
          </div>

          <div className="progress-graph">
            <h3>{t("progress.daily_words")}</h3>
            <DailyBarChart dailyCounts={data.daily_counts} dailyTarget={data.daily_target} t={t} />
          </div>

          <div className="progress-graph">
            <h3>{t("progress.session_history")}</h3>
            <SessionBarChart sessions={data.sessions} sessionTarget={data.session_target} t={t} />
          </div>
        </>
      )}
    </div>
  );
}
