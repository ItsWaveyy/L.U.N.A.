const REFRESH_INTERVAL = 1000;

let latestTelemetry = null;
let lastBootId = null;
let startupRunning = false;
let toastTimeout = null;


/* =========================================================
   BASIC HELPERS
   ========================================================= */

function byId(id) {
    return document.getElementById(id);
}

function setText(id, value) {
    const element = byId(id);

    if (element) {
        element.textContent = value ?? "";
    }
}

function show(id) {
    const element = byId(id);

    if (element) {
        element.classList.remove("hidden");
    }
}

function hide(id) {
    const element = byId(id);

    if (element) {
        element.classList.add("hidden");
    }
}

function formatTime(timestamp) {
    if (!timestamp) {
        return "—";
    }

    try {
        return new Date(timestamp).toLocaleTimeString(
            [],
            {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            }
        );
    } catch {
        return "—";
    }
}

function formatPercent(value) {
    if (value == null) {
        return "—";
    }

    return `${Number(value).toFixed(0)}%`;
}


/* =========================================================
   API
   ========================================================= */

async function getTelemetry() {
    const response = await fetch(
        "/api/telemetry",
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `Telemetry request failed: ${response.status}`
        );
    }

    return response.json();
}

async function postJson(url, payload) {
    const response = await fetch(
        url,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }
    );

    if (!response.ok) {
        let detail = "Request failed.";

        try {
            const body = await response.json();

            if (body?.detail) {
                detail = body.detail;
            }
        } catch {
            // Keep default.
        }

        throw new Error(detail);
    }

    return response.json();
}


/* =========================================================
   RUNTIME STATUS
   ========================================================= */

function updateRuntimeStatus(telemetry) {
    const dashboard = telemetry?.dashboard;
    const state = dashboard?.state ?? "starting";

    const message =
        dashboard?.status?.message ??
        "Initializing L.U.N.A.";

    setText(
        "runtime-state",
        state.toUpperCase()
    );

    setText(
        "runtime-message",
        message
    );

    const dot = byId("runtime-status-dot");

    if (!dot) {
        return;
    }

    dot.classList.remove(
        "online",
        "warning",
        "error"
    );

    if (state === "error") {
        dot.classList.add("error");
        return;
    }

    if (
        state === "starting" ||
        state === "thinking" ||
        state === "working" ||
        state === "updating" ||
        state === "researching"
    ) {
        dot.classList.add("warning");
        return;
    }

    if (
        state === "idle" ||
        state === "listening" ||
        state === "speaking"
    ) {
        dot.classList.add("online");
    }
}


/* =========================================================
   CANVAS STATE
   ========================================================= */

const STATE_VIEWS = {
    starting: "canvas-boot",
    idle: "canvas-idle",
    listening: "canvas-listening",
    thinking: "canvas-thinking",
    speaking: "canvas-speaking",
    working: "canvas-working",
    updating: "canvas-updating",
    researching: "canvas-researching",
};

function hideAllStateViews() {
    for (const id of Object.values(STATE_VIEWS)) {
        hide(id);
    }

    hide("canvas-presentation");
}

function showStateView(state) {
    hideAllStateViews();

    const viewId =
        STATE_VIEWS[state] ??
        STATE_VIEWS.idle;

    show(viewId);
}

function renderState(state, message) {
    showStateView(state);

    switch (state) {
        case "thinking":
            setText(
                "thinking-message",
                message || "Processing"
            );
            break;

        case "speaking":
            setText(
                "speaking-message",
                message || "Speaking"
            );
            break;

        case "working":
            setText(
                "working-message",
                message || "Working"
            );
            break;

        case "updating":
            setText(
                "update-message",
                message || "Applying update"
            );
            break;

        case "researching":
            setText(
                "research-message",
                message || "Searching"
            );
            break;

        case "idle":
            setText(
                "idle-state-text",
                "READY"
            );

            setText(
                "idle-subtext",
                "L.U.N.A. ONLINE"
            );
            break;

        case "listening":
            setText(
                "idle-state-text",
                "LISTENING"
            );
            break;

        default:
            break;
    }
}


/* =========================================================
   DYNAMIC PRESENTATIONS
   ========================================================= */

function clearPresentation() {
    const container = byId(
        "canvas-presentation"
    );

    if (!container) {
        return;
    }

    container.innerHTML = "";
}

function createElement(
    tag,
    className,
    text
) {
    const element =
        document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text != null) {
        element.textContent = text;
    }

    return element;
}

function renderPresentation(
    presentation
) {
    const container = byId(
        "canvas-presentation"
    );

    if (!container) {
        return;
    }

    const type =
        presentation?.type ?? "idle";

    const data =
        presentation?.data ?? {};

    if (
        !type ||
        type === "idle" ||
        type === "none"
    ) {
        return false;
    }

    clearPresentation();

    switch (type) {
        case "weather":
            renderWeather(
                container,
                data
            );
            break;

        case "forecast":
            renderForecast(
                container,
                data
            );
            break;

        case "progress":
            renderProgress(
                container,
                data
            );
            break;

        case "search":
            renderSearch(
                container,
                data
            );
            break;

        case "calendar":
            renderCalendar(
                container,
                data
            );
            break;

        case "alert":
            renderPresentationAlert(
                container,
                data
            );
            break;

        default:
            renderGenericPresentation(
                container,
                type,
                data
            );
            break;
    }

    hideAllStateViews();
    show("canvas-presentation");

    return true;
}


/* =========================================================
   WEATHER
   ========================================================= */

function renderWeather(
    container,
    data
) {
    const wrapper =
        createElement(
            "div",
            "presentation-card weather-card"
        );

    const location =
        createElement(
            "div",
            "presentation-eyebrow",
            data.location ?? "WEATHER"
        );

    const temperature =
        createElement(
            "div",
            "weather-temperature",
            data.temperature != null
                ? `${data.temperature}°`
                : "—"
        );

    const condition =
        createElement(
            "div",
            "weather-condition",
            data.condition ?? "Current conditions"
        );

    const details =
        createElement(
            "div",
            "weather-details"
        );

    const values = [
        ["FEELS", data.feels_like],
        ["HUMIDITY", data.humidity],
        ["WIND", data.wind],
    ];

    for (const [label, value] of values) {
        if (value == null) {
            continue;
        }

        const item =
            createElement(
                "div",
                "weather-detail"
            );

        item.appendChild(
            createElement(
                "span",
                "weather-detail-label",
                label
            )
        );

        item.appendChild(
            createElement(
                "span",
                "weather-detail-value",
                String(value)
            )
        );

        details.appendChild(item);
    }

    wrapper.appendChild(location);
    wrapper.appendChild(temperature);
    wrapper.appendChild(condition);
    wrapper.appendChild(details);

    container.appendChild(wrapper);
}


/* =========================================================
   FORECAST
   ========================================================= */

function renderForecast(
    container,
    data
) {
    const wrapper =
        createElement(
            "div",
            "presentation-card forecast-card"
        );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-eyebrow",
            data.location ?? "FORECAST"
        )
    );

    const title =
        createElement(
            "div",
            "presentation-title",
            data.title ?? "Forecast"
        );

    wrapper.appendChild(title);

    const days =
        createElement(
            "div",
            "forecast-days"
        );

    for (
        const day of data.days ?? []
    ) {
        const item =
            createElement(
                "div",
                "forecast-day"
            );

        item.appendChild(
            createElement(
                "div",
                "forecast-day-name",
                day.day ?? "—"
            )
        );

        item.appendChild(
            createElement(
                "div",
                "forecast-day-condition",
                day.condition ?? ""
            )
        );

        item.appendChild(
            createElement(
                "div",
                "forecast-day-temp",
                day.temperature ?? "—"
            )
        );

        days.appendChild(item);
    }

    wrapper.appendChild(days);
    container.appendChild(wrapper);
}


/* =========================================================
   PROGRESS
   ========================================================= */

function renderProgress(
    container,
    data
) {
    const wrapper =
        createElement(
            "div",
            "presentation-card progress-card"
        );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-eyebrow",
            data.label ?? "L.U.N.A."
        )
    );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-title",
            data.title ?? "Working"
        )
    );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-caption",
            data.message ?? ""
        )
    );

    const progress =
        createElement(
            "div",
            "presentation-progress"
        );

    const bar =
        createElement(
            "div",
            "presentation-progress-bar"
        );

    const percent =
        Math.max(
            0,
            Math.min(
                100,
                Number(data.percent ?? 0)
            )
        );

    bar.style.width =
        `${percent}%`;

    progress.appendChild(bar);
    wrapper.appendChild(progress);

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-percent",
            `${Math.round(percent)}%`
        )
    );

    container.appendChild(wrapper);
}


/* =========================================================
   SEARCH
   ========================================================= */

function renderSearch(
    container,
    data
) {
    const wrapper =
        createElement(
            "div",
            "presentation-card search-card"
        );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-eyebrow",
            "RESEARCH"
        )
    );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-title",
            data.query ?? "Search"
        )
    );

    const results =
        createElement(
            "div",
            "search-results"
        );

    for (
        const result of data.results ?? []
    ) {
        const item =
            createElement(
                "div",
                "search-result"
            );

        item.appendChild(
            createElement(
                "div",
                "search-result-title",
                result.title ?? "Result"
            )
        );

        if (result.description) {
            item.appendChild(
                createElement(
                    "div",
                    "search-result-description",
                    result.description
                )
            );
        }

        results.appendChild(item);
    }

    wrapper.appendChild(results);
    container.appendChild(wrapper);
}


/* =========================================================
   CALENDAR
   ========================================================= */

function renderCalendar(
    container,
    data
) {
    const wrapper =
        createElement(
            "div",
            "presentation-card calendar-card"
        );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-eyebrow",
            "CALENDAR"
        )
    );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-title",
            data.title ?? "Upcoming"
        )
    );

    const events =
        createElement(
            "div",
            "calendar-events"
        );

    for (
        const event of data.events ?? []
    ) {
        const item =
            createElement(
                "div",
                "calendar-event"
            );

        item.appendChild(
            createElement(
                "div",
                "calendar-event-time",
                event.time ?? ""
            )
        );

        item.appendChild(
            createElement(
                "div",
                "calendar-event-name",
                event.title ?? "Event"
            )
        );

        events.appendChild(item);
    }

    wrapper.appendChild(events);
    container.appendChild(wrapper);
}


/* =========================================================
   ALERT PRESENTATION
   ========================================================= */

function renderPresentationAlert(
    container,
    data
) {
    const wrapper =
        createElement(
            "div",
            `presentation-card presentation-alert ${data.severity ?? "info"}`
        );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-eyebrow",
            data.severity
                ? data.severity.toUpperCase()
                : "ALERT"
        )
    );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-title",
            data.title ?? "L.U.N.A."
        )
    );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-caption",
            data.message ?? ""
        )
    );

    container.appendChild(wrapper);
}


/* =========================================================
   GENERIC PRESENTATION
   ========================================================= */

function renderGenericPresentation(
    container,
    type,
    data
) {
    const wrapper =
        createElement(
            "div",
            "presentation-card"
        );

    wrapper.appendChild(
        createElement(
            "div",
            "presentation-eyebrow",
            type.toUpperCase()
        )
    );

    if (data.title) {
        wrapper.appendChild(
            createElement(
                "div",
                "presentation-title",
                data.title
            )
        );
    }

    if (data.message) {
        wrapper.appendChild(
            createElement(
                "div",
                "presentation-caption",
                data.message
            )
        );
    }

    container.appendChild(wrapper);
}


/* =========================================================
   BOOT SEQUENCE
   ========================================================= */

function setBootProgress(percent) {
    const bar =
        byId("startup-progress-bar");

    if (bar) {
        bar.style.width =
            `${Math.max(0, Math.min(100, percent))}%`;
    }

    const bootBar =
        byId("boot-progress-bar");

    if (bootBar) {
        bootBar.style.width =
            `${Math.max(0, Math.min(100, percent))}%`;
    }
}

function setBootPhase(
    phase,
    detail,
    percent
) {
    setText(
        "startup-phase",
        phase
    );

    setText(
        "startup-detail",
        detail
    );

    setText(
        "boot-status",
        phase
    );

    setBootProgress(percent);
}

function hideStartupOverlay() {
    const overlay =
        byId("startup-overlay");

    if (!overlay) {
        return;
    }

    overlay.style.opacity = "0";

    window.setTimeout(
        () => {
            overlay.classList.add(
                "hidden"
            );
        },
        700
    );
}

async function runStartupSequence(
    telemetry
) {
    if (startupRunning) {
        return;
    }

    startupRunning = true;

    const overlay =
        byId("startup-overlay");

    if (overlay) {
        overlay.classList.remove(
            "hidden"
        );

        overlay.style.opacity = "1";
    }

    const boot =
        telemetry?.dashboard?.boot;

    setBootPhase(
        "INITIALIZING",
        "Establishing core systems",
        12
    );

    await wait(350);

    setBootPhase(
        "CORE",
        "Verifying L.U.N.A. core",
        35
    );

    await wait(350);

    setBootPhase(
        "VOICE",
        "Checking voice systems",
        58
    );

    await wait(350);

    setBootPhase(
        "NEURAL",
        "Bringing intelligence online",
        78
    );

    await wait(350);

    setBootPhase(
        "ONLINE",
        "L.U.N.A. is ready",
        100
    );

    await wait(500);

    if (boot?.boot_id) {
        localStorage.setItem(
            "luna_last_boot_id",
            boot.boot_id
        );
    }

    hideStartupOverlay();

    startupRunning = false;
}

function wait(milliseconds) {
    return new Promise(
        resolve =>
            window.setTimeout(
                resolve,
                milliseconds
            )
    );
}

function shouldRunStartup(
    telemetry
) {
    const bootId =
        telemetry?.dashboard?.boot?.boot_id;

    if (!bootId) {
        return false;
    }

    const previous =
        localStorage.getItem(
            "luna_last_boot_id"
        );

    if (!previous) {
        return true;
    }

    return previous !== bootId;
}


/* =========================================================
   FIXED HUMAN CONTROLS
   ========================================================= */

async function toggleListening() {
    const current =
        latestTelemetry?.core?.listening ??
        false;

    try {
        await postJson(
            "/api/listening",
            {
                listening: !current,
            }
        );

        showToast(
            !current
                ? "Listening enabled."
                : "Listening disabled."
        );

        await refreshTelemetry();

    } catch (error) {
        showToast(
            error.message,
            "warning"
        );
    }
}

async function restartAgent() {
    try {
        showToast(
            "Restarting L.U.N.A. voice agent..."
        );

        await postJson(
            "/api/service",
            {
                service: "luna-agent",
                action: "restart",
            }
        );

    } catch (error) {
        showToast(
            error.message,
            "warning"
        );
    }
}

async function reconnect() {
    showToast(
        "Reconnecting voice systems..."
    );

    await restartAgent();
}

function updateControlState() {
    const listening =
        latestTelemetry?.core?.listening ??
        false;

    const button =
        byId("listening-button");

    if (button) {
        button.classList.toggle(
            "active",
            listening
        );
    }
}

function wireControls() {
    byId("listening-button")
        ?.addEventListener(
            "click",
            toggleListening
        );

    byId("reconnect-button")
        ?.addEventListener(
            "click",
            reconnect
        );

    byId("restart-button")
        ?.addEventListener(
            "click",
            restartAgent
        );

    byId("mute-button")
        ?.addEventListener(
            "click",
            () => {
                showToast(
                    "Microphone control will be connected to the voice device layer next."
                );
            }
        );
}


/* =========================================================
   TOASTS
   ========================================================= */

function showToast(
    message,
    severity = "info"
) {
    const toast =
        byId("system-toast");

    if (!toast) {
        return;
    }

    setText(
        "toast-severity",
        severity.toUpperCase()
    );

    setText(
        "toast-message",
        message
    );

    toast.classList.remove(
        "hidden"
    );

    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }

    toastTimeout =
        window.setTimeout(
            () => {
                toast.classList.add(
                    "hidden"
                );
            },
            3500
        );
}


/* =========================================================
   MAIN RENDER
   ========================================================= */

function renderTelemetry(
    telemetry
) {
    latestTelemetry =
        telemetry;

    updateRuntimeStatus(
        telemetry
    );

    updateControlState();

    const dashboard =
        telemetry.dashboard ?? {};

    const state =
        dashboard.state ?? "starting";

    const presentation =
        dashboard.presentation ?? {
            type: "idle",
            data: {},
        };

    const presentationActive =
        renderPresentation(
            presentation
        );

    if (!presentationActive) {
        renderState(
            state,
            dashboard.status?.message
        );
    }

    setText(
        "canvas-clock",
        formatTime(
            telemetry.timestamp
        )
    );

    setText(
        "canvas-connection",
        telemetry.core?.status === "online"
            ? "CORE ONLINE"
            : "CORE —"
    );

    const bootId =
        dashboard.boot?.boot_id;

    if (
        bootId &&
        bootId !== lastBootId
    ) {
        lastBootId = bootId;

        if (
            shouldRunStartup(
                telemetry
            )
        ) {
            runStartupSequence(
                telemetry
            );
        }
    }
}

async function refreshTelemetry() {
    try {
        const telemetry =
            await getTelemetry();

        renderTelemetry(
            telemetry
        );

    } catch (error) {
        console.error(
            "[L.U.N.A.] Dashboard telemetry failed:",
            error
        );

        setText(
            "runtime-state",
            "OFFLINE"
        );

        setText(
            "runtime-message",
            "Core unavailable"
        );

        const dot =
            byId("runtime-status-dot");

        dot?.classList.remove(
            "online",
            "warning"
        );

        dot?.classList.add(
            "error"
        );
    }
}


/* =========================================================
   START
   ========================================================= */

wireControls();

refreshTelemetry();

window.setInterval(
    refreshTelemetry,
    REFRESH_INTERVAL
);