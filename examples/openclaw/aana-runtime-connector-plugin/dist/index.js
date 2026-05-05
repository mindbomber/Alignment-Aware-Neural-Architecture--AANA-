import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

const LOOPBACK_HOSTS = new Set([
  ["127", "0", "0", "1"].join("."),
  "localhost",
  "[::1]",
  "::1"
]);

const DEFAULT_TIMEOUT_MS = 8000;

function textResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2)
      }
    ]
  };
}

function readConfig(api) {
  return api?.config ?? api?.runtime?.config ?? {};
}

function resolveBridgeBaseUrl(api, params = {}) {
  const config = readConfig(api);
  const value = params.bridgeBaseUrl ?? config.bridgeBaseUrl;
  if (!value || typeof value !== "string" || !value.trim()) {
    throw new Error("AANA bridgeBaseUrl is required and must point to a trusted loopback AANA bridge.");
  }

  const url = new URL(value);
  if (url.protocol !== "http:") {
    throw new Error("AANA bridgeBaseUrl must use plain HTTP on a loopback interface.");
  }
  if (!LOOPBACK_HOSTS.has(url.hostname)) {
    throw new Error("AANA bridgeBaseUrl must resolve to a loopback host.");
  }
  url.search = "";
  url.hash = "";
  return url;
}

function resolveTimeout(api, params = {}) {
  const config = readConfig(api);
  const value = params.timeoutMs ?? config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeout = Number(value);
  if (!Number.isFinite(timeout) || timeout < 1000 || timeout > 30000) {
    throw new Error("timeoutMs must be between 1000 and 30000.");
  }
  return timeout;
}

async function callBridge(api, params, path, options = {}) {
  const baseUrl = resolveBridgeBaseUrl(api, params);
  const timeoutMs = resolveTimeout(api, params);
  const basePath = baseUrl.pathname === "/" ? "" : baseUrl.pathname.replace(/\/+$/, "");
  const endpoint = new URL(`${basePath}${path}`, baseUrl.origin);
  if (options.adapterId) {
    endpoint.searchParams.set("adapter_id", options.adapterId);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(endpoint, {
      method: options.method ?? "POST",
      headers: options.body ? { "content-type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal
    });
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      payload = { raw_response: text };
    }
    if (!response.ok) {
      return textResult({
        ok: false,
        status: response.status,
        endpoint: path,
        error: payload
      });
    }
    return textResult({
      ok: true,
      status: response.status,
      endpoint: path,
      result: payload
    });
  } finally {
    clearTimeout(timeout);
  }
}

const bridgeParams = {
  type: "object",
  properties: {
    bridgeBaseUrl: {
      type: "string",
      description: "Trusted loopback AANA bridge base URL. May be omitted when configured for the plugin."
    },
    timeoutMs: {
      type: "integer",
      minimum: 1000,
      maximum: 30000,
      description: "Optional timeout override in milliseconds."
    }
  },
  additionalProperties: false
};

const eventParams = {
  type: "object",
  required: ["event"],
  properties: {
    ...bridgeParams.properties,
    event: {
      type: "object",
      description: "AANA agent event object. Keep payloads minimal and redacted."
    },
    adapterId: {
      type: "string",
      description: "Optional adapter override for the AANA bridge."
    }
  },
  additionalProperties: false
};

const workflowParams = {
  type: "object",
  required: ["workflowRequest"],
  properties: {
    ...bridgeParams.properties,
    workflowRequest: {
      type: "object",
      description: "AANA Workflow Contract request object."
    }
  },
  additionalProperties: false
};

export default definePluginEntry({
  id: "aana-runtime-connector",
  name: "AANA Runtime Connector",
  description: "Registers optional OpenClaw tools for checking planned agent events against a local AANA bridge.",
  register(api) {
    api.registerTool(
      {
        name: "aana_runtime_health",
        description: "Check whether the configured local AANA bridge is reachable.",
        parameters: bridgeParams,
        async execute(_id, params = {}) {
          return callBridge(api, params, "/health", { method: "GET" });
        }
      },
      { optional: true }
    );

    api.registerTool(
      {
        name: "aana_validate_event",
        description: "Validate an AANA agent event shape without running the gate.",
        parameters: eventParams,
        async execute(_id, params = {}) {
          return callBridge(api, params, "/validate-event", { body: params.event });
        }
      },
      { optional: true }
    );

    api.registerTool(
      {
        name: "aana_agent_check",
        description: "Check a planned agent answer or action through the AANA gate.",
        parameters: eventParams,
        async execute(_id, params = {}) {
          return callBridge(api, params, "/agent-check", {
            body: params.event,
            adapterId: params.adapterId
          });
        }
      },
      { optional: true }
    );

    api.registerTool(
      {
        name: "aana_validate_workflow",
        description: "Validate an AANA Workflow Contract request without running the gate.",
        parameters: workflowParams,
        async execute(_id, params = {}) {
          return callBridge(api, params, "/validate-workflow", { body: params.workflowRequest });
        }
      },
      { optional: true }
    );

    api.registerTool(
      {
        name: "aana_workflow_check",
        description: "Check a proposed output or action through the AANA Workflow Contract gate.",
        parameters: workflowParams,
        async execute(_id, params = {}) {
          return callBridge(api, params, "/workflow-check", { body: params.workflowRequest });
        }
      },
      { optional: true }
    );
  }
});
