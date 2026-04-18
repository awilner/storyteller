const { Server } = require("@hocuspocus/server");
const { Redis } = require("@hocuspocus/extension-redis");
const fetch = require("node-fetch");

const AUTH_URL =
  process.env.HOCUSPOCUS_AUTH_URL ||
  "http://backend:8000/api/internal/yjs-auth/";
const HOCUSPOCUS_SECRET = process.env.HOCUSPOCUS_SECRET || "";
const REDIS_URL = process.env.REDIS_URL || "";
const PORT = parseInt(process.env.HOCUSPOCUS_PORT || "1234", 10);

/**
 * Parse a Redis URL into host/port for the extension.
 * Accepts redis://host:port format.
 */
function parseRedisUrl(url) {
  try {
    const parsed = new URL(url);
    return {
      host: parsed.hostname || "127.0.0.1",
      port: parseInt(parsed.port || "6379", 10),
    };
  } catch {
    return { host: "127.0.0.1", port: 6379 };
  }
}

// Only load the Redis extension when REDIS_URL is provided.
// For local single-instance dev, HocusPocus works fine with in-memory storage.
const extensions = [];
if (REDIS_URL) {
  const redisConfig = parseRedisUrl(REDIS_URL);
  extensions.push(
    new Redis({
      host: redisConfig.host,
      port: redisConfig.port,
      prefix: "hocuspocus:",
    })
  );
} else {
  console.log("No REDIS_URL set — running with in-memory document storage");
}

const server = Server.configure({
  port: PORT,
  extensions,

  /**
   * Authenticate incoming WebSocket connections by calling back to the
   * Django internal endpoint. The client sends the file_id as the
   * document name and the session cookie via the WebSocket handshake.
   */
  async onAuthenticate({ token, documentName, requestHeaders }) {
    // documentName is expected to be "file-<id>"
    const match = documentName.match(/^file-(\d+)$/);
    if (!match) {
      throw new Error("Invalid document name");
    }
    const fileId = parseInt(match[1], 10);

    // Forward the cookie header from the WebSocket handshake
    const cookie = requestHeaders.cookie || token || "";

    const response = await fetch(AUTH_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Hocuspocus-Secret": HOCUSPOCUS_SECRET,
      },
      body: JSON.stringify({
        file_id: fileId,
        cookie: cookie,
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Auth failed (${response.status}): ${text}`);
    }

    const data = await response.json();

    // Return user context — HocusPocus stores this on the connection
    return {
      user: {
        id: data.user_id,
        name: data.username,
        permission: data.permission,
      },
    };
  },

  /**
   * After authentication, set read-only mode for users with read-only
   * permission. The connection context is populated by onAuthenticate.
   */
  async onConnect({ connection, context }) {
    if (context && context.user && context.user.permission === "read-only") {
      connection.readOnly = true;
    }
  },
});

server.listen().then(() => {
  console.log(`HocusPocus server listening on port ${PORT}`);
});
