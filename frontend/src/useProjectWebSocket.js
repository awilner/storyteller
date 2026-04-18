import { useEffect, useRef, useCallback } from "react";

/**
 * React hook that manages a Django Channels WebSocket connection for a project.
 *
 * Connects to /ws/projects/<id>/ on mount, disconnects on unmount or when
 * projectId changes. Implements exponential backoff reconnection
 * (1s → 2s → 4s → … → 30s cap).
 *
 * @param {number|string} projectId - The project to connect to.
 * @param {object} handlers - Event callbacks keyed by message type.
 *   Built-in types dispatched by name:
 *   - onPermissionChanged(data)  — "permission_changed"
 *   - onAccessRevoked(data)      — "access_revoked"
 *   - onPresenceUpdate(data)     — "presence"
 *   - onTreeChanged(data)        — "tree_changed"
 *   - onSettingsChanged(data)    — "settings_changed"
 *   - onLabelsChanged(data)      — "labels_changed"
 *   - onStatusesChanged(data)    — "statuses_changed"
 *   - onLayoutsChanged(data)     — "layouts_changed"
 *
 *   For any event type not listed above, the hook calls
 *   handlers.onProjectEvent(data) if provided — making it easy to
 *   handle new event types without touching this file.
 */
export default function useProjectWebSocket(projectId, handlers) {
  const wsRef = useRef(null);
  const retryDelayRef = useRef(1000);
  const retryTimerRef = useRef(null);
  // Keep a stable ref to handlers so reconnect logic always sees the latest
  // callbacks without re-triggering the effect.
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const connect = useCallback(() => {
    if (!projectId) return;

    // Determine WebSocket base URL from the current page location.
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/projects/${projectId}/`;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      // Reset backoff on successful connection.
      retryDelayRef.current = 1000;
    };

    // Map message type → handler name for known events.
    const HANDLER_MAP = {
      permission_changed: "onPermissionChanged",
      access_revoked: "onAccessRevoked",
      presence: "onPresenceUpdate",
      tree_changed: "onTreeChanged",
      settings_changed: "onSettingsChanged",
      labels_changed: "onLabelsChanged",
      statuses_changed: "onStatusesChanged",
      layouts_changed: "onLayoutsChanged",
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const h = handlersRef.current;
        if (!h) return;

        const handlerName = HANDLER_MAP[data.type];
        if (handlerName && h[handlerName]) {
          h[handlerName](data);
        } else if (h.onProjectEvent) {
          // Generic fallback for any unrecognised event type.
          h.onProjectEvent(data);
        }
      } catch {
        // Ignore malformed messages.
      }
    };

    ws.onclose = () => {
      // Schedule reconnect with exponential backoff.
      retryTimerRef.current = setTimeout(() => {
        retryDelayRef.current = Math.min(retryDelayRef.current * 2, 30000);
        connect();
      }, retryDelayRef.current);
    };

    ws.onerror = () => {
      // The browser will fire onclose after onerror, so reconnect is
      // handled there. Nothing extra needed here.
    };

    wsRef.current = ws;
  }, [projectId]);

  useEffect(() => {
    connect();

    return () => {
      // Clean up on unmount or projectId change.
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close.
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);
}
