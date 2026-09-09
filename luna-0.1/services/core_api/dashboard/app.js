const REFRESH_INTERVAL = 2000;

let latestDashboardState = null;

async function sendDashboardCommand(command) {
    const response = await fetch(
        "/api/dashboard/command",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(command),
        }
    );

    if (!response.ok) {
        let detail = "Dashboard command failed.";

        try {
            const payload = await response.json();

            if (payload?.detail) {
                detail = payload.detail;
            }
        } catch {
            // Keep default error message.
        }

        throw new Error(detail);
    }

    return response.json();
}

async function applyLayout() {
    const layout = byId("layout-select")?.value;

    if (!layout) {
        return;
    }

    const panels = [
        "system",
        "providers",
        "routing",
        "memory",
        "activity",
        "network",
        "improvement",
        "wakeword",
    ];

    try {
        const state = await sendDashboardCommand({
            action: "set_dashboard",
            layout,
            panels,
        });

        latestDashboardState = state;
        applyDashboardState(state);
        updateDashboardControls(state);

    } catch (error) {
        console.error(error);
    }
}

async function focusPanel() {
    const panel = byId("panel-select")?.value;

    if (!panel) {
        return;
    }

    try {
        const state = await sendDashboardCommand({
            action: "focus_panel",
            panel,
        });

        latestDashboardState = state;
        applyDashboardState(state);
        updateDashboardControls(state);

    } catch (error) {
        console.error(error);
    }
}

async function clearFocus() {
    try {
        const state = await sendDashboardCommand({
            action: "clear_focus",
        });

        latestDashboardState = state;
        applyDashboardState(state);
        updateDashboardControls(state);

    } catch (error) {
        console.error(error);
    }
}

function updateDashboardControls(state) {
    if (!state) {
        return;
    }

    setText(
        "dashboard-mode",
        state.mode?.toUpperCase() ?? "DEFAULT"
    );

    const layoutSelect = byId("layout-select");

    if (layoutSelect && state.mode) {
        layoutSelect.value = state.mode;
    }

    const focused = state.focused_panel;

    const panelSelect = byId("panel-select");

    if (panelSelect && focused) {
        panelSelect.value = focused;
    }
}

async function setPanelVisibility(visible) {
    const panel = byId("panel-select")?.value;

    if (!panel) {
        return;
    }

    try {
        const state = await sendDashboardCommand({
            action: visible
                ? "show_panel"
                : "hide_panel",
            panel,
        });

        latestDashboardState = state;
        applyDashboardState(state);
        updateDashboardControls(state);

    } catch (error) {
        console.error(error);
    }
}

function byId(id) {
    return document.getElementById(id);
}

function setText(id, value) {
    const element = byId(id);

    if (element) {
        element.textContent = value;
    }
}

function formatBytes(bytes) {
    if (bytes == null) {
        return "—";
    }

    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = bytes;
    let index = 0;

    while (value >= 1024 && index < units.length - 1) {
        value /= 1024;
        index++;
    }

    return `${value.toFixed(1)} ${units[index]}`;
}

function formatUptime(seconds) {
    if (seconds == null) {
        return "—";
    }

    const total = Math.floor(seconds);

    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);

    if (days > 0) {
        return `${days}d ${hours}h`;
    }

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }

    return `${minutes}m`;
}

function formatLatency(seconds) {
    if (seconds == null) {
        return "—";
    }

    return `${seconds.toFixed(2)}s`;
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "—";
    }

    return new Date(timestamp).toLocaleTimeString();
}

function renderSystem(system) {
    setText("hostname", system.host?.hostname ?? "—");

    setText(
        "cpu",
        system.cpu?.percent != null
            ? `${system.cpu.percent.toFixed(1)}%`
            : "—"
    );

    setText(
        "ram",
        system.memory?.percent != null
            ? `${system.memory.percent.toFixed(1)}%`
            : "—"
    );

    setText(
        "temperature",
        system.temperature?.celsius != null
            ? `${system.temperature.celsius.toFixed(1)}°C`
            : "N/A"
    );

    setText(
        "storage",
        system.storage?.percent != null
            ? `${system.storage.percent.toFixed(1)}%`
            : "—"
    );

    setText(
        "network",
        system.network?.interface_online
            ? "ONLINE"
            : "OFFLINE"
    );

    setText(
        "uptime",
        formatUptime(system.uptime_seconds)
    );

    setText(
        "network-state",
        system.network?.interface_online
            ? "ONLINE"
            : "OFFLINE"
    );

    setText(
        "network-interface",
        system.network?.interface_online
            ? "PRIMARY"
            : "UNAVAILABLE"
    );

    setText(
        "network-status",
        system.network?.interface_online
            ? "CONNECTED"
            : "DISCONNECTED"
    );
}

function renderCore(core) {
    setText("core-status", core.status?.toUpperCase() ?? "—");
    setText("core-mode", core.mode?.toUpperCase() ?? "—");
    setText(
        "listening",
        core.listening ? "YES" : "NO"
    );

    setText(
        "session",
        core.conversation?.active
            ? `ACTIVE #${core.conversation.session_id}`
            : "INACTIVE"
    );

    setText(
        "memory-status",
        core.memory?.available
            ? "AVAILABLE"
            : "UNAVAILABLE"
    );

    setText(
        "improvement-status",
        core.improvement?.available
            ? "AVAILABLE"
            : "UNAVAILABLE"
    );

    setText(
        "improvement-available",
        core.improvement?.available
            ? "AVAILABLE"
            : "UNAVAILABLE"
    );

    setText(
        "memory-long-term",
        core.memory?.available
            ? "AVAILABLE"
            : "UNAVAILABLE"
    );

    setText(
        "memory-archive",
        core.memory?.conversation_archive
            ? "AVAILABLE"
            : "UNAVAILABLE"
    );

    setText(
        "wake-listening",
        core.listening ? "ACTIVE" : "STANDBY"
    );
}

function renderProviders(providers) {
    const container = byId("providers-list");

    if (!container) {
        return;
    }

    container.innerHTML = "";

    for (const provider of providers ?? []) {
        const wrapper = document.createElement("div");
        wrapper.className = "provider";

        const dot = document.createElement("div");
        dot.className = "provider-dot";

        if (provider.healthy) {
            dot.classList.add("healthy");
        }

        const info = document.createElement("div");

        const name = document.createElement("div");
        name.className = "provider-name";
        name.textContent = provider.name;

        const model = document.createElement("div");
        model.className = "provider-model";
        model.textContent = provider.model ?? "No model";

        info.appendChild(name);
        info.appendChild(model);

        wrapper.appendChild(dot);
        wrapper.appendChild(info);

        container.appendChild(wrapper);
    }
}

function renderRouting(runtimeState) {
    const routing = runtimeState?.routing;

    if (!routing) {
        return;
    }

    setText(
        "routing-state",
        routing.active ? "ACTIVE" : "IDLE"
    );

    setText("routing-task", routing.task ?? "—");
    setText("routing-provider", routing.provider ?? "—");
    setText("routing-model", routing.model ?? "—");

    setText(
        "routing-latency",
        formatLatency(routing.last_latency_seconds)
    );

    setText(
        "routing-fallback",
        routing.fallback_used
            ? `YES${routing.fallback_from ? ` (${routing.fallback_from})` : ""}`
            : "NO"
    );
}

function renderActivity(activity) {
    const container = byId("activity-list");

    if (!container) {
        return;
    }

    setText("activity-count", activity?.count ?? 0);

    container.innerHTML = "";

    for (const event of (activity?.events ?? []).slice(0, 10)) {
        const item = document.createElement("div");
        item.className = "activity-item";

        const main = document.createElement("div");
        main.className = "activity-main";

        const message = document.createElement("div");
        message.className = "activity-message";
        message.textContent = event.message;

        const time = document.createElement("div");
        time.className = "activity-meta";
        time.textContent = formatTimestamp(event.timestamp);

        main.appendChild(message);
        main.appendChild(time);

        const meta = document.createElement("div");
        meta.className = "activity-meta";

        const details = [
            event.task,
            event.provider,
            event.model,
            event.latency_seconds != null
                ? formatLatency(event.latency_seconds)
                : null,
        ].filter(Boolean);

        meta.textContent = details.join(" • ");

        item.appendChild(main);
        item.appendChild(meta);

        container.appendChild(item);
    }
}

function renderAlerts(alerts) {
    const container = byId("alerts-list");

    if (!container) {
        return;
    }

    const visibleAlerts = alerts ?? [];

    setText("alert-count", visibleAlerts.length);

    container.innerHTML = "";

    for (const alert of visibleAlerts) {
        const item = document.createElement("div");

        item.className = `alert ${alert.severity ?? "info"}`;

        const message = document.createElement("div");
        message.className = "alert-message";
        message.textContent = alert.message;

        const time = document.createElement("div");
        time.className = "alert-time";
        time.textContent = formatTimestamp(alert.timestamp);

        item.appendChild(message);
        item.appendChild(time);

        container.appendChild(item);
    }
}

function applyDashboardState(state) {
    if (!state) {
        return;
    }

    latestDashboardState = state;

    const panels = state.panels ?? {};

    for (const [panelId, panel] of Object.entries(panels)) {
        const element = byId(`${panelId}-panel`);

        if (!element) {
            continue;
        }

        element.classList.toggle(
            "hidden",
            panel.visible === false
        );

        element.classList.toggle(
            "focused",
            panelId === state.focused_panel
        );

        element.dataset.priority = String(
            panel.priority ?? 0
        );
    }

    if (state.mode) {
        document.body.dataset.dashboardMode = state.mode;
    }

    updateDashboardControls(state);
}

async function loadTelemetry() {
    try {
        const response = await fetch(
            "/api/telemetry",
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error(
                `Telemetry request failed: ${response.status}`
            );
        }

        const telemetry = await response.json();

        byId("connection-dot")?.classList.add("online");
        byId("connection-dot")?.classList.remove("offline");
        setText("connection-text", "CORE ONLINE");

        renderSystem(telemetry.system);
        renderCore(telemetry.core);
        renderProviders(telemetry.core?.providers);
        renderRouting(telemetry.runtime_state);
        renderActivity(telemetry.activity);
        renderAlerts(telemetry.dashboard?.alerts);


        applyDashboardState(telemetry.dashboard);

        setText(
            "last-update",
            `Updated ${formatTimestamp(telemetry.timestamp)}`
        );

    } catch (error) {
        console.error(error);

        byId("connection-dot")?.classList.remove("online");
        byId("connection-dot")?.classList.add("offline");
        setText("connection-text", "CORE OFFLINE");
    }
}

byId("apply-layout")?.addEventListener(
    "click",
    applyLayout
);

byId("show-panel")?.addEventListener(
    "click",
    () => setPanelVisibility(true)
);

byId("hide-panel")?.addEventListener(
    "click",
    () => setPanelVisibility(false)
);

byId("focus-panel")?.addEventListener(
    "click",
    focusPanel
);

byId("clear-focus")?.addEventListener(
    "click",
    clearFocus
);

loadTelemetry();

setInterval(
    loadTelemetry,
    REFRESH_INTERVAL
);