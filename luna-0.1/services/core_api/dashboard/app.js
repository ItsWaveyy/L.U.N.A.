const REFRESH_INTERVAL = 1000;

let latestTelemetry = null;
let latestServices = [];
let lastBootId = null;
let startupRunning = false;
let toastTimeout = null;

let demoRunning = false;
let demoStepIndex = 0;
let demoTimeout = null;
let demoIntroWritingFrame = null;
let demoIntroAnimationFrame = null;
let demoWritingOrb = null;

let memoryAnimationFrame = null;
let memoryResizeObserver = null;

function stopDemoIntroWriting() {
    if (
        demoIntroWritingFrame !== null
    ) {
        cancelAnimationFrame(
            demoIntroWritingFrame
        );

        demoIntroWritingFrame = null;
    }
}

function stopMemoryAnimation() {
    if (memoryAnimationFrame !== null) {
        cancelAnimationFrame(
            memoryAnimationFrame
        );

        memoryAnimationFrame = null;
    }

    if (memoryResizeObserver) {
        memoryResizeObserver.disconnect();
        memoryResizeObserver = null;
    }
}


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

async function getSystem() {
    const response = await fetch(
        "/api/system",
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `System request failed: ${response.status}`
        );
    }

    return response.json();
}

async function getServices() {
    const response = await fetch(
        "/api/services",
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `Services request failed: ${response.status}`
        );
    }

    return response.json();
}

async function getStatus() {
    const response = await fetch(
        "/api/status",
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `Status request failed: ${response.status}`
        );
    }

    return response.json();
}

async function getDataStatus() {
    const response = await fetch(
        "/api/data",
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `Data request failed: ${response.status}`
        );
    }

    return response.json();
}

async function getUpdateStatus() {
  const response = await fetch("/api/update", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `Update request failed: ${response.status}`
    );
  }

  return response.json();
}

function renderDataSettings(data) {
    const available =
        data?.status === "online";

    setText(
        "settings-memory-count",
        available
            ? String(data.memories ?? 0)
            : "—"
    );

    setText(
        "settings-session-count",
        available
            ? String(data.sessions ?? 0)
            : "—"
    );

    setText(
        "settings-message-count",
        available
            ? String(data.messages ?? 0)
            : "—"
    );

    setText(
        "settings-reminder-count",
        available
            ? String(data.reminders ?? 0)
            : "—"
    );

    setText(
        "settings-data-state",
        available
            ? "ONLINE"
            : "UNAVAILABLE"
    );
}

function renderUpdateSettings(update) {
  const available =
    update?.status === "online" ||
    update?.status === "development";

  const development = update?.status === "development";

  let state = "UNAVAILABLE";

  if (development) {
    state = update.local_changes
      ? "DEVELOPMENT"
      : "DEVELOPMENT • CLEAN";
  } else if (available) {
    if (update.local_changes) {
      state = "LOCAL CHANGES";
    } else if (update.current) {
      state = "CURRENT";
    } else {
      state = "UPDATE AVAILABLE";
    }
  }

  setText("settings-update-state", state);

  setText(
    "settings-update-branch",
    available ? update.branch ?? "—" : "—"
  );

  setText(
    "settings-update-version",
    available ? update.commit ?? "—" : "—"
  );

  setText(
    "settings-update-remote",
    available ? update.remote ?? "—" : "—"
  );

  setText(
    "settings-update-schedule",
    available ? update.schedule ?? "—" : "—"
  );

  setText(
    "settings-update-last",
    available ? update.last_update ?? "—" : "—"
  );

  const warning = byId("settings-update-warning");

  if (warning) {
    warning.classList.toggle(
      "hidden",
      !available || !update.local_changes
    );
  }

  const stateElement = byId("settings-update-state");

  if (stateElement) {
    stateElement.classList.remove(
        "is-current",
        "is-development",
        "is-warning",
        "is-available"
    );

    if (state === "CURRENT") {
        stateElement.classList.add("is-current");
    } else if (state === "DEVELOPMENT") {
        stateElement.classList.add("is-development");
    } else if (state === "UPDATE AVAILABLE") {
        stateElement.classList.add("is-available");
    } else if (state === "LOCAL CHANGES") {
        stateElement.classList.add("is-warning");
    }
  }
}

function renderAISettings(data) {
    const providers = data?.providers ?? [];

    const healthyCount = providers.filter(
        (provider) => provider.healthy === true
    ).length;

    setText(
        "settings-ai-mode",
        data?.mode ?? "—"
    );

    setText(
        "settings-ai-providers",
        providers.length
            ? `${healthyCount}/${providers.length}`
            : "—"
    );

    setText(
        "settings-ai-conversation",
        data?.conversation?.active
            ? "ACTIVE"
            : "IDLE"
    );

    setText(
        "settings-ai-improvement",
        data?.improvement?.available
            ? "AVAILABLE"
            : "OFF"
    );

    setText(
        "settings-ai-state",
        data?.status === "online"
            ? "ONLINE"
            : "OFFLINE"
    );

    const container = byId(
        "settings-ai-providers-list"
    );

    if (!container) {
        return;
    }

    if (!providers.length) {
        container.innerHTML = `
            <div class="settings-service-row error">
                <span class="settings-service-name">
                    No providers reported
                </span>

                <span class="settings-service-state">
                    UNKNOWN
                </span>
            </div>
        `;

        return;
    }

    container.innerHTML = providers
        .map((provider) => {
            const healthy =
                provider.healthy === true;

            const state =
                healthy
                    ? "HEALTHY"
                    : "UNAVAILABLE";

            const className =
                healthy
                    ? "active"
                    : "error";

            const model =
                provider.model ?? "NO MODEL";

            const capabilities =
                provider.capabilities ?? [];

            const capabilityText =
                capabilities.length
                    ? capabilities.join(" · ")
                    : "NO CAPABILITIES";

            return `
                <div
                    class="settings-service-row ${className}"
                >
                    <div>
                        <span class="settings-service-name">
                            ${provider.name}
                        </span>

                        <span class="settings-service-model">
                            ${model}
                        </span>

                        <span class="settings-service-capabilities">
                            ${capabilityText}
                        </span>
                    </div>

                    <span class="settings-service-state">
                        ${state}
                    </span>
                </div>
            `;
        })
        .join("");
}

function renderNetworkSettings(system) {
    const hostname =
        system?.host?.hostname;

    const networkOnline =
        system?.network?.interface_online === true;

    setText(
        "settings-hostname",
        hostname ?? "—"
    );

    setText(
        "settings-network",
        networkOnline
            ? "ONLINE"
            : "OFFLINE"
    );

    setText(
        "settings-network-state",
        networkOnline
            ? "ONLINE"
            : "OFFLINE"
    );
}

function renderServicesSettings(data) {
    const container = byId(
        "settings-services"
    );

    if (!container) {
        return;
    }

    const services = data?.services ?? [];

    if (!services.length) {
        container.innerHTML = `
            <div class="settings-service-row">
                <span class="settings-service-name">
                    No services reported
                </span>

                <span class="settings-service-state">
                    UNKNOWN
                </span>
            </div>
        `;

        setText(
            "settings-services-state",
            "UNKNOWN"
        );

        return;
    }

    container.innerHTML = services
        .map((service) => {
            const active = service.active === true;
            const state = String(
                service.state ?? "unknown"
            ).toUpperCase();

            let className = "";

            if (active) {
                className = "active";
            } else if (
                state === "DEVELOPMENT"
            ) {
                className = "warning";
            } else {
                className = "error";
            }

            return `
                <div
                    class="settings-service-row ${className}"
                >
                    <span class="settings-service-name">
                        ${service.name}
                    </span>

                    <span class="settings-service-state">
                        ${state}
                    </span>
                </div>
            `;
        })
        .join("");

    const activeCount = services.filter(
        (service) => service.active === true
    ).length;

    setText(
        "settings-services-state",
        `${activeCount}/${services.length} ONLINE`
    );
}

function renderSystemSettings(system) {
    const cpu = system?.cpu;
    const memory = system?.memory;
    const temperature = system?.temperature;
    const storage = system?.storage;

    setText(
        "settings-cpu",
        cpu?.percent != null
            ? `${Number(cpu.percent).toFixed(0)}%`
            : "—"
    );

    setText(
        "settings-memory",
        memory?.percent != null
            ? `${Number(memory.percent).toFixed(0)}%`
            : "—"
    );

    setText(
        "settings-temperature",
        temperature?.celsius != null
            ? `${Number(temperature.celsius).toFixed(1)}°C`
            : "—"
    );

    const uptime = system?.uptime_seconds;

    if (uptime != null) {
        const totalSeconds = Math.floor(
            Number(uptime)
        );

        const hours = Math.floor(
            totalSeconds / 3600
        );

        const minutes = Math.floor(
            (totalSeconds % 3600) / 60
        );

        setText(
            "settings-uptime",
            `${hours}h ${minutes}m`
        );
    } else {
        setText(
            "settings-uptime",
            "—"
        );
    }

    setText(
        "settings-system-state",
        system ? "ONLINE" : "UNKNOWN"
    );

    setText(
        "settings-storage",
        storage?.percent != null
            ? `${Number(storage.percent).toFixed(0)}%`
            : "—"
    );
}

function renderServices(data) {
    latestServices =
        data?.services ?? [];

    const services =
        data?.services ?? [];

    for (const service of services) {
        const item = document.querySelector(
            `.service-item[data-service="${service.name}"]`
        );

        if (!item) {
            continue;
        }

        item.classList.remove(
            "active",
            "warning",
            "error",
            "development"
        );

        if (service.state === "development") {
            item.classList.add("development");
            continue;
        }

        if (service.active) {
            item.classList.add("active");
            continue;
        }

        if (
            service.state === "activating" ||
            service.state === "deactivating" ||
            service.state === "reloading"
        ) {
            item.classList.add("warning");
            continue;
        }

        item.classList.add("error");
    }
}

let selectedService = null;


function serviceDisplayName(service) {
    const names = {
        "luna-core": "CORE",
        "luna-agent": "AGENT",
        "kokoro": "KOKORO",
        "ollama": "OLLAMA",
    };

    return names[service] ?? service.toUpperCase();
}


function getSelectedServiceStatus() {
    return latestServices.find(
        service =>
            service.name === selectedService
    );
}


function openServiceMenu(service) {
    selectedService = service;

    const menu = byId("service-menu");

    if (!menu) {
        return;
    }

    const status =
        getSelectedServiceStatus();

    setText(
        "service-menu-name",
        serviceDisplayName(service)
    );

    setText(
        "service-menu-state",
        status?.state?.toUpperCase() ??
        "UNKNOWN"
    );

    menu.classList.remove("hidden");
}


function closeServiceMenu() {
    selectedService = null;

    byId("service-menu")
        ?.classList.add("hidden");
}


async function controlSelectedService(
    action
) {
    if (!selectedService) {
        return;
    }

    const service =
        selectedService;

    try {
        showToast(
            `${action.toUpperCase()} ${serviceDisplayName(service)}...`
        );

        await postJson(
            "/api/control",
            {
                action:
                    `${action}_service`,
                payload: {
                    service,
                },
            }
        );

        showToast(
            `${serviceDisplayName(service)} ${action} accepted.`
        );

        await refreshTelemetry();

        openServiceMenu(service);

    } catch (error) {
        showToast(
            error.message,
            "warning"
        );
    }
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
   SYSTEM DEMO
   ========================================================= */

const DEMO_STEPS = [
    { id: "intro", duration: 10000 },
    { id: "runtime", duration: 5200 },
    { id: "services", duration: 5600 },
    { id: "intelligence", duration: 5600 },
    { id: "memory", duration: 16000 },
    { id: "deployment", duration: 5200 },
    { id: "capabilities", duration: 6200 },
    { id: "finale", duration: 4800 },
];

function setDemoState(state, running = false) {
    const element = byId("settings-demo-state");

    if (element) {
        element.classList.remove(
            "is-demo",
            "is-demo-running"
        );

        element.classList.add(
            running
                ? "is-demo-running"
                : "is-demo"
        );
    }

    setText(
        "settings-demo-state",
        state
    );

    const button = byId(
        "settings-demo-button"
    );

    if (button) {
        button.classList.toggle(
            "running",
            running
        );

        button.textContent =
            running
                ? "DEMO RUNNING"
                : "RUN DEMO";
    }
}

function clearDemoTimer() {
    if (demoTimeout) {
        window.clearTimeout(
            demoTimeout
        );

        demoTimeout = null;
    }
}

function closeSettingsForDemo() {
    byId(
        "settings-overlay"
    )?.classList.add("hidden");
}

function createDemoShell() {
    const presentation =
        byId("canvas-presentation");

    if (!presentation) {
        return null;
    }

    stopMemoryAnimation();
    stopDemoIntroWriting();

    clearPresentation();

    presentation.classList.add(
        "demo-stage"
    );

    const shell =
        createElement(
            "div",
            "demo-shell"
        );

    presentation.appendChild(shell);

    return shell;
}

function destroyDemoShell() {
    stopMemoryAnimation();
    stopDemoIntroWriting();

    const presentation =
        byId("canvas-presentation");

    if (!presentation) {
        return;
    }

    presentation.classList.remove(
        "demo-stage"
    );

    clearPresentation();
}

function demoHeading(
    shell,
    eyebrow,
    title,
    caption
) {
    const heading =
        createElement(
            "div",
            "demo-heading"
        );

    const eyebrowNode =
        createElement(
            "div",
            "demo-eyebrow",
            eyebrow
        );

    const titleNode =
        createElement(
            "div",
            "demo-title",
            title
        );

    const captionNode =
        createElement(
            "div",
            "demo-caption",
            caption
        );

    heading.appendChild(
        eyebrowNode
    );

    heading.appendChild(
        titleNode
    );

    heading.appendChild(
        captionNode
    );

    shell.appendChild(
        heading
    );
}

function demoCorners(
    shell,
    leftTop = "L.U.N.A. // DEMONSTRATION",
    rightTop = "LIVE SYSTEM",
    leftBottom = "NEURAL ASSISTANT",
    rightBottom = "ONLINE"
) {
    const positions = [
        ["top-left", leftTop],
        ["top-right", rightTop],
        ["bottom-left", leftBottom],
        ["bottom-right", rightBottom],
    ];

    positions.forEach(
        ([position, value]) => {
            const node =
                createElement(
                    "div",
                    `demo-corner ${position}`
                );

            node.textContent =
                value;

            shell.appendChild(node);
        }
    );
}

function demoNarration(
    shell,
    label,
    message
) {
    const narration =
        createElement(
            "div",
            "demo-narration"
        );

    const labelNode =
        createElement(
            "div",
            "demo-narration-label",
            label
        );

    const textNode =
        createElement(
            "div",
            "demo-narration-text",
            message
        );

    narration.appendChild(
        labelNode
    );

    narration.appendChild(
        textNode
    );

    shell.appendChild(
        narration
    );
}

function renderDemoIntro() {
    const shell =
        createDemoShell();

    if (!shell) return;

    demoCorners(
        shell,
        "L.U.N.A. // SYSTEM DEMONSTRATION",
        "LIVE",
        "LOWKEY USEFUL NEURAL ASSISTANT",
        "READY"
    );

    const writing =
        createElement(
            "div",
            "demo-writing-intro"
        );

    const svg =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "svg"
        );

    svg.setAttribute(
        "viewBox",
        "0 0 620 150"
    );

    svg.setAttribute(
        "aria-hidden",
        "true"
    );

    svg.classList.add(
        "demo-writing-svg"
    );

    /*
       Clean geometric L.U.N.A.

       These are intentionally simple,
       straight/controlled strokes.
       The orb is drawing a logo,
       not handwriting.
    */

    const pathData = [
        // L
        `
        M 151 43
        L 151 102
        L 201 102
        `,

        // .
        `
        M 213.5 102
        C 213.5 100.6 214.6 99.5 216 99.5
        C 217.4 99.5 218.5 100.6 218.5 102
        C 218.5 103.4 217.4 104.5 216 104.5
        C 214.6 104.5 213.5 103.4 213.5 102
        `,

        // U
        `
        M 231 43
        L 231 82
        C 231 95 237 102 251 102
        C 265 102 271 95 271 82
        L 271 43
        `,

        // .
        `
        M 283.5 102
        C 283.5 100.6 284.6 99.5 286 99.5
        C 287.4 99.5 288.5 100.6 288.5 102
        C 288.5 103.4 287.4 104.5 286 104.5
        C 284.6 104.5 283.5 103.4 283.5 102
        `,

        // N
        `
        M 301 102
        L 301 43
        L 346 102
        L 346 43
        `,

        // .
        `
        M 358.5 102
        C 358.5 100.6 359.6 99.5 361 99.5
        C 362.4 99.5 363.5 100.6 363.5 102
        C 363.5 103.4 362.4 104.5 361 104.5
        C 359.6 104.5 358.5 103.4 358.5 102
        `,

        // A
        `
        M 380 102
        L 412 43
        L 444 102
        `,

        // A crossbar
        `
        M 394 80
        L 430 80
        `,
    ];

    const paths = [];

    pathData.forEach(
        (data, index) => {
            const path =
                document.createElementNS(
                    "http://www.w3.org/2000/svg",
                    "path"
                );

            path.setAttribute(
                "d",
                data.replace(/\s+/g, " ").trim()
            );

            path.classList.add(
                "demo-writing-path"
            );

            if (
                index === 1 ||
                index === 3 ||
                index === 5
            ) {
                path.classList.add(
                    "demo-writing-dot"
                );
            }

            const length =
                path.getTotalLength();

            path.style.strokeDasharray =
                `${length}`;

            path.style.strokeDashoffset =
                `${length}`;

            svg.appendChild(path);

            paths.push(path);
        }
    );

    writing.appendChild(
        svg
    );

    /*
       Move the REAL idle orb into the
       writing scene.
    */

    const orb =
        document.querySelector(
            "#canvas-idle .idle-orb"
        );

    if (orb) {
        demoWritingOrb = orb;

        writing.appendChild(
            orb
        );

        orb.classList.add(
            "demo-writing-orb"
        );

        orb.style.left =
            "50%";

        orb.style.top =
            "50%";

        orb.style.transform =
            "translate(-50%, -50%) scale(1)";
    }

    shell.appendChild(
        writing
    );

    demoNarration(
        shell,
        "L.U.N.A.",
        "You asked what I'm for. Let me show you."
    );

    requestAnimationFrame(() => {
        if (
            !demoRunning ||
            !demoWritingOrb
        ) {
            return;
        }

        const firstPath =
            paths[0];

        if (!firstPath) {
            return;
        }

        const writingRect =
            writing.getBoundingClientRect();

        const svgRect =
            svg.getBoundingClientRect();

        const svgToWriting = (
            point
        ) => ({
            x:
                svgRect.left -
                writingRect.left +
                (
                    point.x /
                    620
                ) *
                svgRect.width,

            y:
                svgRect.top -
                writingRect.top +
                (
                    point.y /
                    150
                ) *
                svgRect.height,
        });

        const start =
            firstPath.getPointAtLength(
                0
            );

        const startPosition =
            svgToWriting(
                start
            );

        /*
           Transition is ON here.

           The orb smoothly travels from
           the center to the beginning
           of the L.
        */

        demoWritingOrb.style.left =
            `${startPosition.x}px`;

        demoWritingOrb.style.top =
            `${startPosition.y}px`;

        demoWritingOrb.style.transform =
            "translate(-50%, -50%) scale(1.08)";

        window.setTimeout(() => {
            if (!demoRunning) {
                return;
            }

            /*
               From this point onward the orb
               must track the stroke EXACTLY.
            */

            demoWritingOrb.classList.add(
                "is-writing"
            );

            animateDemoWriting(
                paths,
                svg,
                writing
            );
        }, 1050);
    });
}


function animateDemoWriting(
    paths,
    svg,
    writing
) {
    if (!demoWritingOrb) {
        return;
    }

    const writingRect =
        writing.getBoundingClientRect();

    const svgRect =
        svg.getBoundingClientRect();

    const svgToWriting = (
        point
    ) => {
        return {
            x:
                svgRect.left -
                writingRect.left +
                (
                    point.x /
                    620
                ) *
                svgRect.width,

            y:
                svgRect.top -
                writingRect.top +
                (
                    point.y /
                    150
                ) *
                svgRect.height,
        };
    };

    /*
       Every stroke starts completely hidden.
    */

    paths.forEach(
        path => {
            const length =
                path.getTotalLength();

            path.style.strokeDasharray =
                `${length}`;

            path.style.strokeDashoffset =
                `${length}`;
        }
    );

    let pathIndex = 0;
    let distance = 0;

    let lastTimestamp = null;

    /*
       When a stroke finishes, the orb enters
       a travel phase instead of teleporting.
    */

    let traveling = false;
    let travelStart = null;
    let travelDuration = 0;
    let travelFrom = null;
    let travelTo = null;

    const pixelsPerSecond = 92;

    const travelSpeed = 240;

    const writeNextPath = (
        timestamp
    ) => {
        if (
            !demoRunning ||
            !demoWritingOrb
        ) {
            demoIntroAnimationFrame =
                null;

            return;
        }

        const path =
            paths[pathIndex];

        /*
           Everything is finished.
        */

        if (!path) {
            demoIntroAnimationFrame =
                null;

            demoWritingOrb.style.transform =
                "translate(-50%, -50%) scale(1.02)";

            return;
        }

        /*
           --------------------------------
           SMOOTH TRAVEL BETWEEN STROKES
           --------------------------------
        */

        if (traveling) {
            if (
                travelStart === null
            ) {
                travelStart =
                    timestamp;
            }

            const elapsed =
                timestamp -
                travelStart;

            const progress =
                Math.min(
                    1,
                    elapsed /
                    travelDuration
                );

            /*
               Smooth ease-in-out so the orb
               doesn't snap at either end.
            */

            const eased =
                progress < 0.5
                    ? 2 *
                      progress *
                      progress
                    : 1 -
                      (
                          Math.pow(
                              -2 *
                              progress +
                              2,
                              2
                          ) /
                          2
                      );

            const x =
                travelFrom.x +
                (
                    travelTo.x -
                    travelFrom.x
                ) *
                eased;

            const y =
                travelFrom.y +
                (
                    travelTo.y -
                    travelFrom.y
                ) *
                eased;

            demoWritingOrb.style.left =
                `${x}px`;

            demoWritingOrb.style.top =
                `${y}px`;

            demoWritingOrb.style.transform =
                "translate(-50%, -50%) scale(1.04)";

            if (
                progress >= 1
            ) {
                traveling = false;
                travelStart = null;
                lastTimestamp = null;
                distance = 0;
            }

            demoIntroAnimationFrame =
                requestAnimationFrame(
                    writeNextPath
                );

            return;
        }

        /*
           --------------------------------
           DRAW CURRENT STROKE
           --------------------------------
        */

        if (
            lastTimestamp === null
        ) {
            lastTimestamp =
                timestamp;
        }

        const delta =
            Math.min(
                40,
                timestamp -
                lastTimestamp
            );

        lastTimestamp =
            timestamp;

        const speed =
            pixelsPerSecond *
            (
                0.94 +
                Math.sin(
                    timestamp * 0.003
                ) * 0.04
            );

        distance +=
            speed *
            (
                delta /
                1000
            );

        const length =
            path.getTotalLength();

        const progress =
            Math.min(
                1,
                distance /
                length
            );

        const point =
            path.getPointAtLength(
                Math.min(
                    distance,
                    length
                )
            );

        const position =
            svgToWriting(
                point
            );

        demoWritingOrb.style.left =
            `${position.x}px`;

        demoWritingOrb.style.top =
            `${position.y}px`;

        demoWritingOrb.style.transform =
            "translate(-50%, -50%) scale(1.04)";

        path.style.strokeDashoffset =
            `${length * (1 - progress)}`;

        /*
           --------------------------------
           STROKE FINISHED
           --------------------------------
        */

        if (
            progress >= 1
        ) {
            const endPoint =
                path.getPointAtLength(
                    length
                );

            const endPosition =
                svgToWriting(
                    endPoint
                );

            pathIndex += 1;

            const nextPath =
                paths[pathIndex];

            /*
               No next stroke = we're done.
            */

            if (!nextPath) {
                demoWritingOrb.style.left =
                    `${endPosition.x}px`;

                demoWritingOrb.style.top =
                    `${endPosition.y}px`;

                demoWritingOrb.style.transform =
                    "translate(-50%, -50%) scale(1.02)";

                demoIntroAnimationFrame =
                    null;

                return;
            }

            /*
               Find the beginning of the next
               stroke and smoothly travel there.
            */

            const nextStart =
                nextPath.getPointAtLength(
                    0
                );

            const nextPosition =
                svgToWriting(
                    nextStart
                );

            const dx =
                nextPosition.x -
                endPosition.x;

            const dy =
                nextPosition.y -
                endPosition.y;

            const travelDistance =
                Math.sqrt(
                    dx * dx +
                    dy * dy
                );

            travelFrom =
                endPosition;

            travelTo =
                nextPosition;

            travelDuration =
                Math.max(
                    90,
                    (
                        travelDistance /
                        travelSpeed
                    ) *
                    1000
                );

            travelStart =
                timestamp;

            traveling = true;

            distance = 0;
            lastTimestamp = null;
        }

        demoIntroAnimationFrame =
            requestAnimationFrame(
                writeNextPath
            );
    };

    demoIntroAnimationFrame =
        requestAnimationFrame(
            writeNextPath
        );
}

function restoreIdleOrb() {
    if (demoIntroAnimationFrame !== null) {
        cancelAnimationFrame(
            demoIntroAnimationFrame
        );

        demoIntroAnimationFrame = null;
    }

    const orb =
        demoWritingOrb ||
        document.querySelector(
            ".demo-writing-orb"
        );

    const idle =
        byId("canvas-idle");

    if (!orb || !idle) {
        demoWritingOrb = null;
        return;
    }

    orb.classList.remove(
        "demo-writing-orb"
    );

    orb.removeAttribute(
        "style"
    );

    idle.insertBefore(
        orb,
        idle.firstChild
    );

    demoWritingOrb = null;
}

function renderDemoRuntime(
    system
) {
    const shell =
        createDemoShell();

    if (!shell) return;

    demoHeading(
        shell,
        "SYSTEM RUNTIME",
        "Everything starts here.",
        "Live telemetry from the L.U.N.A. host"
    );

    demoCorners(
        shell,
        "RUNTIME // TELEMETRY",
        "LIVE DATA",
        `HOST ${system?.host ?? "UNKNOWN"}`,
        "SYSTEM ONLINE"
    );

    const core =
        createElement(
            "div",
            "demo-core"
        );

    [
        "one",
        "two",
        "three",
        "four"
    ].forEach(
        name => {
            core.appendChild(
                createElement(
                    "div",
                    `demo-core-ring ${name}`
                )
            );
        }
    );

    core.appendChild(
        createElement(
            "div",
            "demo-core-center"
        )
    );

    core.appendChild(
        createElement(
            "div",
            "demo-core-label",
            "L.U.N.A. CORE"
        )
    );

    shell.appendChild(
        core
    );

    const telemetry =
        [
            [
                "left",
                "CPU",
                formatPercent(
                    system?.cpu?.percent
                ),
                "%"
            ],
            [
                "left",
                "MEMORY",
                formatPercent(
                    system?.memory?.percent
                ),
                "%"
            ],
            [
                "right",
                "TEMPERATURE",
                system?.temperature?.celsius != null
                    ? Number(
                        system.temperature.celsius
                    ).toFixed(1)
                    : "—",
                "°C"
            ],
            [
                "right",
                "STORAGE",
                system?.storage?.percent != null
                    ? Number(
                        system.storage.percent
                    ).toFixed(0)
                    : "—",
                "%"
            ],
        ];

    const groups = {
        left: [],
        right: [],
    };

    telemetry.forEach(
        item => {
            groups[item[0]].push(
                item
            );
        }
    );

    Object.entries(
        groups
    ).forEach(
        ([side, items]) => {
            const group =
                createElement(
                    "div",
                    `demo-telemetry ${side}`
                );

            items.forEach(
                item => {
                    const card =
                        createElement(
                            "div",
                            "demo-telemetry-card"
                        );

                    const label =
                        createElement(
                            "div",
                            "demo-telemetry-label",
                            item[1]
                        );

                    const value =
                        createElement(
                            "span",
                            "demo-telemetry-value",
                            item[2]
                        );

                    const unit =
                        createElement(
                            "span",
                            "demo-telemetry-unit",
                            item[3]
                        );

                    value.appendChild(
                        unit
                    );

                    card.appendChild(
                        label
                    );

                    card.appendChild(
                        value
                    );

                    group.appendChild(
                        card
                    );
                }
            );

            shell.appendChild(
                group
            );
        }
    );

    shell.appendChild(
        createElement(
            "div",
            "demo-stream left"
        )
    );

    shell.appendChild(
        createElement(
            "div",
            "demo-stream right"
        )
    );

    demoNarration(
        shell,
        "LIVE TELEMETRY",
        "CPU, memory, temperature and storage are being monitored in real time."
    );
}

function renderDemoServices(
    services
) {
    const shell =
        createDemoShell();

    if (!shell) return;

    const list =
        services?.services ?? [];

    demoHeading(
        shell,
        "SERVICE ARCHITECTURE",
        "A modular system.",
        "Every subsystem has a job."
    );

    demoCorners(
        shell,
        "ARCHITECTURE // SERVICES",
        `${list.length} MODULES`,
        "LIVE SERVICE STATE",
        "CONNECTED"
    );

    const network =
        createElement(
            "div",
            "demo-network"
        );

    const center =
        createElement(
            "div",
            "demo-network-center"
        );

    center.appendChild(
        createElement(
            "span",
            "",
            "L.U.N.A."
        )
    );

    network.appendChild(
        center
    );

    const positions = [
        ["luna-core", 50, 10],
        ["luna-agent", 15, 50],
        ["kokoro", 85, 50],
        ["ollama", 50, 90],
    ];

    positions.forEach(
        ([name, left, top]) => {
            const service =
                list.find(
                    item =>
                        item.name === name
                );

            const node =
                createElement(
                    "div",
                    "demo-node"
                );

            node.style.left =
                `${left}%`;

            node.style.top =
                `${top}%`;

            if (
                service?.active === true
            ) {
                node.classList.add(
                    "active"
                );
            } else {
                node.classList.add(
                    "warning"
                );
            }

            node.appendChild(
                createElement(
                    "div",
                    "demo-node-name",
                    name.toUpperCase()
                )
            );

            node.appendChild(
                createElement(
                    "div",
                    "demo-node-state",
                    String(
                        service?.state ??
                        "UNKNOWN"
                    ).toUpperCase()
                )
            );

            if (service?.model) {
                node.appendChild(
                    createElement(
                        "div",
                        "demo-node-model",
                        service.model
                    )
                );
            }

            network.appendChild(
                node
            );
        }
    );

    shell.appendChild(
        network
    );

    demoNarration(
        shell,
        "MODULAR ARCHITECTURE",
        "Core, agent, voice and local intelligence operate as separate services."
    );
}

function renderDemoIntelligence(
    status
) {
    const shell =
        createDemoShell();

    if (!shell) return;

    const providers =
        status?.providers ?? [];

    const healthy =
        providers.filter(
            provider =>
                provider.healthy === true
        ).length;

    demoHeading(
        shell,
        "INTELLIGENCE",
        "Multiple layers. One assistant.",
        `${healthy}/${providers.length} providers currently healthy`
    );

    demoCorners(
        shell,
        "INTELLIGENCE // PROVIDERS",
        "LIVE",
        "MODEL ROUTING",
        "ACTIVE"
    );

    const capabilities =
        [
            "VOICE",
            "MEMORY",
            "TOOLS",
            "LOCAL AI",
            "SYSTEM CONTROL",
            "RESEARCH",
        ];

    const matrix =
        createElement(
            "div",
            "demo-capabilities"
        );

    const core =
        createElement(
            "div",
            "demo-capability core",
            "L.U.N.A. INTELLIGENCE"
        );

    matrix.appendChild(
        core
    );

    capabilities.forEach(
        (capability, index) => {
            const node =
                createElement(
                    "div",
                    "demo-capability",
                    capability
                );

            node.style.animationDelay =
                `${index * 110}ms`;

            matrix.appendChild(
                node
            );
        }
    );

    shell.appendChild(
        matrix
    );

    const models =
        providers
            .filter(
                provider =>
                    provider.healthy === true
            )
            .map(
                provider =>
                    `${provider.name}: ${provider.model ?? "MODEL ACTIVE"}`
            )
            .join(
                "  ·  "
            );

    demoNarration(
        shell,
        "INTELLIGENCE LAYER",
        models ||
        "Local intelligence systems are currently unavailable."
    );
}

function renderDemoMemory(
    data
) {
    const shell =
        createDemoShell();

    if (!shell) {
        return;
    }

    const sessions =
        Number(data?.sessions) || 0;

    const messages =
        Number(data?.messages) || 0;

    const memories =
        Number(data?.memories) || 0;

    const reminders =
        Number(data?.reminders) || 0;

    /*
     * -----------------------------------------------------
     * MEMORY UNIVERSE
     *
     * The same particles exist in both states:
     *
     *   CONVERSATION FIELD
     *          ↓
     *   MEMORY ORGANIZATION
     *          ↓
     *   MEMORY STRUCTURE
     *
     * Nothing fades into a separate visualization.
     * The particles themselves physically reorganize.
     * -----------------------------------------------------
     */

    const visual =
        createElement(
            "div",
            "demo-memory-visual"
        );

    visual.innerHTML = `
        <canvas
            class="demo-memory-canvas"
        ></canvas>

        <div
            class="demo-memory-readout"
        >
            <div
                class="demo-memory-readout-label"
            >
                ARCHIVE STATE
            </div>

            <div
                class="demo-memory-readout-phase"
            >
                CONVERSATION FIELD
            </div>
        </div>

        <div
            class="demo-memory-count"
        >
            ${memories}
            <span>MEMORIES</span>
        </div>
    `;

    shell.appendChild(
        visual
    );

    demoNarration(
        shell,
        "MEMORY & ARCHIVE",
        `${sessions} sessions stored. · ` +
        `${memories} memories · ` +
        `${messages} messages · ` +
        `${reminders} reminders`
    );

    const canvas =
        visual.querySelector(
            ".demo-memory-canvas"
        );

    const phaseLabel =
        visual.querySelector(
            ".demo-memory-readout-phase"
        );

    const context =
        canvas?.getContext("2d");

    if (!canvas || !context) {
        return;
    }

    /*
     * -----------------------------------------------------
     * CANVAS SETUP
     * -----------------------------------------------------
     */

    let width = 1;
    let height = 1;
    let pixelRatio = 1;

    function resizeCanvas() {
        const rect =
            visual.getBoundingClientRect();

        width =
            Math.max(
                1,
                rect.width
            );

        height =
            Math.max(
                1,
                rect.height
            );

        pixelRatio =
            Math.min(
                2,
                window.devicePixelRatio || 1
            );

        canvas.width =
            Math.floor(
                width * pixelRatio
            );

        canvas.height =
            Math.floor(
                height * pixelRatio
            );

        canvas.style.width =
            `${width}px`;

        canvas.style.height =
            `${height}px`;

        context.setTransform(
            pixelRatio,
            0,
            0,
            pixelRatio,
            0,
            0
        );
    }

    resizeCanvas();

    if (
        typeof ResizeObserver !==
        "undefined"
    ) {
        memoryResizeObserver =
            new ResizeObserver(
                resizeCanvas
            );

        memoryResizeObserver.observe(
            visual
        );
    }

    /*
     * -----------------------------------------------------
     * DETERMINISTIC RANDOMNESS
     *
     * The same database state produces the same particle
     * arrangement instead of a completely different galaxy
     * every time the demo runs.
     * -----------------------------------------------------
     */

    let seed =
        (
            sessions * 73856093 ^
            messages * 19349663 ^
            memories * 83492791 ^
            reminders * 2654435761
        ) >>> 0;

    function random() {
        seed =
            (
                seed * 1664525 +
                1013904223
            ) >>> 0;

        return (
            seed / 4294967296
        );
    }

    /*
     * More conversations = denser field.
     *
     * We deliberately keep the visual within a sane range
     * so a huge message count doesn't turn the demo into
     * a performance test.
     */

    const particleCount =
        Math.min(
            108,
            Math.max(
                76,
                76 +
                Math.round(
                    Math.log10(
                        Math.max(
                            messages,
                            1
                        ) + 1
                    ) * 10
                )
            )
        );

    const particles = [];

    /*
     * -----------------------------------------------------
     * 3D ROTATION
     * -----------------------------------------------------
     */

    function rotate3D(
        point,
        rotateX,
        rotateY,
        rotateZ
    ) {
        let x = point.x;
        let y = point.y;
        let z = point.z;

        const cosX =
            Math.cos(rotateX);

        const sinX =
            Math.sin(rotateX);

        const y1 =
            y * cosX -
            z * sinX;

        const z1 =
            y * sinX +
            z * cosX;

        y = y1;
        z = z1;

        const cosY =
            Math.cos(rotateY);

        const sinY =
            Math.sin(rotateY);

        const x2 =
            x * cosY -
            z * sinY;

        const z2 =
            x * sinY +
            z * cosY;

        x = x2;
        z = z2;

        const cosZ =
            Math.cos(rotateZ);

        const sinZ =
            Math.sin(rotateZ);

        const x3 =
            x * cosZ -
            y * sinZ;

        const y3 =
            x * sinZ +
            y * cosZ;

        return {
            x: x3,
            y: y3,
            z,
        };
    }

    /*
     * -----------------------------------------------------
     * GALAXY COORDINATES
     *
     * Four loose spiral arms + central density.
     * This is the "conversation" state.
     * -----------------------------------------------------
     */

    function createGalaxyPoint(
        index
    ) {
        const arm =
            index % 4;

        const core =
            index <
            particleCount * 0.22;

        if (core) {
            const radius =
                Math.pow(
                    random(),
                    1.8
                ) * 0.42;

            const angle =
                random() *
                Math.PI *
                2;

            return {
                x:
                    Math.cos(angle) *
                    radius,

                y:
                    Math.sin(angle) *
                    radius *
                    0.42,

                z:
                    (random() - 0.5) *
                    0.16,
            };
        }

        const radial =
            0.12 +
            Math.pow(
                random(),
                0.82
            ) * 1.02;

        const angle =
            (
                arm *
                (Math.PI * 2 / 4)
            ) +
            radial * 7.1 +
            (random() - 0.5) *
            0.55;

        return {
            x:
                Math.cos(angle) *
                radial,

            y:
                Math.sin(angle) *
                radial *
                0.44,

            z:
                (random() - 0.5) *
                0.14 *
                radial,
        };
    }

    /*
     * -----------------------------------------------------
     * GYROSCOPE COORDINATES
     *
     * These are the DESTINATIONS of the exact same
     * particles.
     *
     * Four orbital families create the spherical
     * JARVIS-like structure.
     * -----------------------------------------------------
     */

    const gyroRotations = [
        [
            1.10,
            0.22,
            0.10,
        ],
        [
            0.42,
            1.04,
            -0.46,
        ],
        [
            1.46,
            -0.55,
            0.72,
        ],
        [
            0.78,
            0.18,
            -1.04,
        ],
    ];

    function createGyroPoint(
        index
    ) {
        const family =
            index % 4;

        const theta =
            random() *
            Math.PI *
            2;

        const radius =
            0.72 +
            random() *
            0.30;

        let point;

        /*
         * Every family starts as the same kind
         * of orbital ellipse, then gets rotated into
         * its own plane.
         */

        point = {
            x:
                Math.cos(theta) *
                radius,

            y:
                Math.sin(theta) *
                radius *
                0.50,

            z: 0,
        };

        const rotation =
            gyroRotations[
                family
            ];

        point =
            rotate3D(
                point,
                rotation[0],
                rotation[1],
                rotation[2]
            );

        return {
            ...point,
            family,
            theta,
            radius,
        };
    }

    for (
        let index = 0;
        index < particleCount;
        index += 1
    ) {
        particles.push({
            galaxy:
                createGalaxyPoint(
                    index
                ),

            gyro:
                createGyroPoint(
                    index
                ),

            size:
                0.65 +
                random() * 1.25,

            brightness:
                0.45 +
                random() * 0.55,
        });
    }

    /*
     * -----------------------------------------------------
     * MATH HELPERS
     * -----------------------------------------------------
     */

    function clamp(
        value,
        minimum,
        maximum
    ) {
        return Math.max(
            minimum,
            Math.min(
                maximum,
                value
            )
        );
    }

    function smoothstep(
        value
    ) {
        const t =
            clamp(
                value,
                0,
                1
            );

        return (
            t *
            t *
            (3 - 2 * t)
        );
    }

    function lerp(
        a,
        b,
        amount
    ) {
        return (
            a +
            (b - a) *
            amount
        );
    }

    function project(
        point
    ) {
        /*
         * A tiny perspective effect makes the final
         * structure feel volumetric instead of flat.
         */

        const depth =
            1 /
            (
                1.58 -
                point.z * 0.30
            );

        const scale =
            Math.min(
                width,
                height
            ) * 0.37;

        return {
            x:
                width / 2 +
                point.x *
                scale *
                depth,

            y:
                height / 2 +
                point.y *
                scale *
                depth,

            depth,
        };
    }

    /*
     * -----------------------------------------------------
     * FINAL GYRO POSITION
     * -----------------------------------------------------
     */

    function getGyroPosition(
        particle,
        elapsed
    ) {
        const point =
            particle.gyro;

        const rotation =
            gyroRotations[
                point.family
            ];

        /*
         * The rings slowly orbit around the core
         * rather than spinning like a flat loading icon.
         */

        const orbitalSpin =
            elapsed *
            0.00018;

        const wobble =
            Math.sin(
                elapsed *
                0.00055 +
                point.family
            ) *
            0.045;

        return rotate3D(
            point,
            rotation[0] +
                wobble,

            rotation[1] +
                orbitalSpin * 0.28,

            rotation[2] +
                orbitalSpin
        );
    }

    /*
     * -----------------------------------------------------
     * RING GUIDE GEOMETRY
     *
     * These are intentionally faint.
     * The PARTICLES are the actual structure.
     * -----------------------------------------------------
     */

    function getRingPoint(
        family,
        theta,
        elapsed
    ) {
        const point = {
            x:
                Math.cos(theta),

            y:
                Math.sin(theta) *
                0.50,

            z: 0,
        };

        const rotation =
            gyroRotations[
                family
            ];

        const orbitalSpin =
            elapsed *
            0.00018;

        return rotate3D(
            point,
            rotation[0],

            rotation[1] +
                orbitalSpin * 0.28,

            rotation[2] +
                orbitalSpin
        );
    }

    /*
     * -----------------------------------------------------
     * DRAW
     * -----------------------------------------------------
     */

    function drawFrame(
        elapsed
    ) {
        context.clearRect(
            0,
            0,
            width,
            height
        );

        /*
         * Timeline:
         *
         * 0–3.5 sec
         *     Galaxy / conversations
         *
         * 3.5–11.5 sec
         *     Morph / organization
         *
         * 11.5–16 sec
         *     Finished memory structure
         */

        const galaxyHold =
            3500;

        const morphDuration =
            8000;

        const morphProgress =
            smoothstep(
                (
                    elapsed -
                    galaxyHold
                ) /
                morphDuration
            );

        const gyroProgress =
            clamp(
                (
                    elapsed -
                    galaxyHold -
                    morphDuration
                ) /
                4500,
                0,
                1
            );

        /*
         * Phase label
         */

        if (phaseLabel) {
            if (
                morphProgress <
                0.03
            ) {
                phaseLabel.textContent =
                    "CONVERSATION FIELD";
            } else if (
                morphProgress <
                0.88
            ) {
                phaseLabel.textContent =
                    "ORGANIZING MEMORY";
            } else {
                phaseLabel.textContent =
                    "MEMORY STRUCTURE";
            }
        }

        /*
         * Very subtle galaxy drift.
         */

        const galaxySpin =
            elapsed *
            0.000035;

        const renderedPoints =
            [];

        /*
         * -------------------------------------------------
         * PARTICLES
         * -------------------------------------------------
         */

        particles.forEach(
            (
                particle
            ) => {
                let galaxyPoint =
                    rotate3D(
                        particle.galaxy,
                        0,
                        0,
                        galaxySpin
                    );

                const gyroPoint =
                    getGyroPosition(
                        particle,
                        elapsed
                    );

                const point = {
                    x:
                        lerp(
                            galaxyPoint.x,
                            gyroPoint.x,
                            morphProgress
                        ),

                    y:
                        lerp(
                            galaxyPoint.y,
                            gyroPoint.y,
                            morphProgress
                        ),

                    z:
                        lerp(
                            galaxyPoint.z,
                            gyroPoint.z,
                            morphProgress
                        ),
                };

                const projected =
                    project(
                        point
                    );

                renderedPoints.push({
                    ...projected,
                    point,
                    particle,
                });
            }
        );

        /*
         * -------------------------------------------------
         * GALAXY CONNECTIONS
         *
         * These disappear as the conversations become
         * organized memory structures.
         * -------------------------------------------------
         */

        if (
            morphProgress < 0.82
        ) {
            context.save();

            context.lineWidth = 0.7;

            for (
                let index = 0;
                index <
                    renderedPoints.length - 1;
                index += 1
            ) {
                const a =
                    renderedPoints[
                        index
                    ];

                const b =
                    renderedPoints[
                        index + 1
                    ];

                const dx =
                    b.x - a.x;

                const dy =
                    b.y - a.y;

                const distance =
                    Math.sqrt(
                        dx * dx +
                        dy * dy
                    );

                if (
                    distance >
                    Math.min(
                        width,
                        height
                    ) * 0.18
                ) {
                    continue;
                }

                const alpha =
                    (
                        1 -
                        morphProgress
                    ) *
                    0.13;

                context.strokeStyle =
                    `rgba(169, 140, 255, ${alpha})`;

                context.beginPath();

                context.moveTo(
                    a.x,
                    a.y
                );

                context.lineTo(
                    b.x,
                    b.y
                );

                context.stroke();
            }

            context.restore();
        }

        /*
         * -------------------------------------------------
         * ORBIT RINGS
         *
         * They emerge during the morph instead of
         * existing from frame one.
         * -------------------------------------------------
         */

        if (
            morphProgress > 0.28
        ) {
            const ringAlpha =
                smoothstep(
                    (
                        morphProgress -
                        0.28
                    ) /
                    0.72
                );

            context.save();

            context.lineWidth = 0.7;

            for (
                let family = 0;
                family < 4;
                family += 1
            ) {
                context.beginPath();

                const segments = 72;

                for (
                    let index = 0;
                    index <= segments;
                    index += 1
                ) {
                    const theta =
                        (
                            index /
                            segments
                        ) *
                        Math.PI *
                        2;

                    const point =
                        getRingPoint(
                            family,
                            theta,
                            elapsed
                        );

                    const projected =
                        project(
                            point
                        );

                    if (
                        index === 0
                    ) {
                        context.moveTo(
                            projected.x,
                            projected.y
                        );
                    } else {
                        context.lineTo(
                            projected.x,
                            projected.y
                        );
                    }
                }

                const alpha =
                    (
                        0.045 +
                        gyroProgress *
                        0.055
                    ) *
                    ringAlpha;

                context.strokeStyle =
                    `rgba(169, 140, 255, ${alpha})`;

                context.stroke();
            }

            context.restore();
        }

        /*
         * -------------------------------------------------
         * PARTICLE GLOW
         * -------------------------------------------------
         */

        context.save();

        context.globalCompositeOperation =
            "lighter";

        renderedPoints.forEach(
            ({
                x,
                y,
                depth,
                particle,
            }) => {
                const depthScale =
                    clamp(
                        0.72 +
                        depth * 0.36,
                        0.55,
                        1.35
                    );

                const size =
                    particle.size *
                    depthScale;

                const finalBoost =
                    1 +
                    morphProgress *
                    0.35;

                const alpha =
                    (
                        0.34 +
                        particle.brightness *
                        0.52
                    ) *
                    finalBoost;

                /*
                 * Soft halo
                 */

                context.fillStyle =
                    `rgba(169, 140, 255, ${alpha * 0.22})`;

                context.beginPath();

                context.arc(
                    x,
                    y,
                    size * 2.8,
                    0,
                    Math.PI * 2
                );

                context.fill();

                /*
                 * Actual particle
                 */

                context.fillStyle =
                    `rgba(198, 181, 255, ${alpha})`;

                context.beginPath();

                context.arc(
                    x,
                    y,
                    size,
                    0,
                    Math.PI * 2
                );

                context.fill();
            }
        );

        context.restore();

        /*
         * -------------------------------------------------
         * CENTRAL MEMORY CORE
         * -------------------------------------------------
         */

        if (
            morphProgress > 0.45
        ) {
            const coreAlpha =
                smoothstep(
                    (
                        morphProgress -
                        0.45
                    ) /
                    0.55
                );

            const centerX =
                width / 2;

            const centerY =
                height / 2;

            context.save();

            context.globalCompositeOperation =
                "lighter";

            const glowRadius =
                26 +
                gyroProgress * 12;

            const gradient =
                context.createRadialGradient(
                    centerX,
                    centerY,
                    0,
                    centerX,
                    centerY,
                    glowRadius
                );

            gradient.addColorStop(
                0,
                `rgba(230, 220, 255, ${0.20 * coreAlpha})`
            );

            gradient.addColorStop(
                0.22,
                `rgba(169, 140, 255, ${0.11 * coreAlpha})`
            );

            gradient.addColorStop(
                1,
                "rgba(169, 140, 255, 0)"
            );

            context.fillStyle =
                gradient;

            context.beginPath();

            context.arc(
                centerX,
                centerY,
                glowRadius,
                0,
                Math.PI * 2
            );

            context.fill();

            /*
             * Tiny actual core.
             *
             * Deliberately NOT a giant circle.
             */

            context.fillStyle =
                `rgba(245, 241, 255, ${0.72 * coreAlpha})`;

            context.beginPath();

            context.arc(
                centerX,
                centerY,
                2.2 +
                    gyroProgress * 1.8,
                0,
                Math.PI * 2
            );

            context.fill();

            context.restore();
        }

        /*
         * -------------------------------------------------
         * SUBTLE SCAN / DATA PULSE
         * -------------------------------------------------
         */

        if (
            morphProgress > 0.62
        ) {
            const pulse =
                (
                    Math.sin(
                        elapsed *
                        0.003
                    ) + 1
                ) / 2;

            const radius =
                (
                    Math.min(
                        width,
                        height
                    ) *
                    (
                        0.24 +
                        pulse * 0.18
                    )
                );

            context.save();

            context.strokeStyle =
                `rgba(169, 140, 255, ${0.025 + pulse * 0.035})`;

            context.lineWidth = 1;

            context.beginPath();

            context.arc(
                width / 2,
                height / 2,
                radius,
                0,
                Math.PI * 2
            );

            context.stroke();

            context.restore();
        }
    }

    /*
     * -----------------------------------------------------
     * START ANIMATION
     * -----------------------------------------------------
     */

    const reducedMotion =
        window.matchMedia?.(
            "(prefers-reduced-motion: reduce)"
        ).matches === true;

    const animationDuration =
        16000;

    const startTime =
        performance.now();

    function animate(
        timestamp
    ) {
        const elapsed =
            Math.min(
                timestamp -
                    startTime,
                animationDuration
            );

        drawFrame(
            elapsed
        );

        if (
            elapsed <
            animationDuration &&
            demoRunning
        ) {
            memoryAnimationFrame =
                requestAnimationFrame(
                    animate
                );
        } else {
            memoryAnimationFrame =
                null;

            if (
                memoryResizeObserver
            ) {
                memoryResizeObserver.disconnect();

                memoryResizeObserver =
                    null;
            }
        }
    }

    if (reducedMotion) {
        drawFrame(
            animationDuration
        );

        if (
            memoryResizeObserver
        ) {
            memoryResizeObserver.disconnect();

            memoryResizeObserver =
                null;
        }

        return;
    }

    memoryAnimationFrame =
        requestAnimationFrame(
            animate
        );
}

function renderDemoDeployment(
    update
) {
    const shell =
        createDemoShell();

    if (!shell) return;

    demoHeading(
        shell,
        "DEPLOYMENT",
        "The system can maintain itself.",
        "Repository state and automated deployment"
    );

    demoCorners(
        shell,
        "DEPLOYMENT // GIT",
        update?.environment
            ? String(
                update.environment
            ).toUpperCase()
            : "UNKNOWN",
        update?.schedule ??
            "SCHEDULE UNKNOWN",
        update?.status === "development"
            ? "DEVELOPMENT"
            : "DEPLOYED"
    );

    const deployment =
        createElement(
            "div",
            "demo-deployment"
        );

    deployment.appendChild(
        createElement(
            "div",
            "demo-deployment-track"
        )
    );

    const local =
        createElement(
            "div",
            "demo-deployment-node local"
        );

    local.appendChild(
        createElement(
            "div",
            "demo-deployment-label",
            "LOCAL"
        )
    );

    local.appendChild(
        createElement(
            "div",
            "demo-deployment-value",
            update?.branch ??
                "UNKNOWN"
        )
    );

    local.appendChild(
        createElement(
            "div",
            "demo-deployment-meta",
            `VERSION ${update?.commit ?? "UNKNOWN"}`
        )
    );

    const remote =
        createElement(
            "div",
            "demo-deployment-node remote"
        );

    remote.appendChild(
        createElement(
            "div",
            "demo-deployment-label",
            "REMOTE"
        )
    );

    remote.appendChild(
        createElement(
            "div",
            "demo-deployment-value",
            update?.remote ??
                "UNKNOWN"
        )
    );

    remote.appendChild(
        createElement(
            "div",
            "demo-deployment-meta",
            update?.current
                ? "CURRENT"
                : update?.local_changes
                    ? "LOCAL CHANGES DETECTED"
                    : "REMOTE STATE"
        )
    );

    deployment.appendChild(
        local
    );

    deployment.appendChild(
        remote
    );

    shell.appendChild(
        deployment
    );

    demoNarration(
        shell,
        "AUTOMATED DEPLOYMENT",
        update?.local_changes
            ? "Local changes detected. Automatic update protection is active."
            : `Repository state is ${update?.current ? "current" : "not current"}.`
    );
}

function renderDemoCapabilities() {
    const shell =
        createDemoShell();

    if (!shell) return;

    demoHeading(
        shell,
        "CAPABILITIES",
        "This is where L.U.N.A. gets useful.",
        "A live assistant should do more than display information."
    );

    demoCorners(
        shell,
        "CAPABILITY MATRIX",
        "INTERACTIVE",
        "VOICE // CONTROL // TOOLS",
        "READY"
    );

    const matrix =
        createElement(
            "div",
            "demo-capabilities"
        );

    const labels = [
        "VOICE",
        "LISTENING",
        "SYSTEM CONTROL",
        "MEMORY",
        "LOCAL INTELLIGENCE",
        "RESEARCH",
    ];

    labels.forEach(
        (label, index) => {
            const node =
                createElement(
                    "div",
                    "demo-capability"
                );

            node.textContent =
                label;

            node.style.animationDelay =
                `${index * 120}ms`;

            matrix.appendChild(
                node
            );
        }
    );

    const core =
        createElement(
            "div",
            "demo-capability core"
        );

    core.textContent =
        "L.U.N.A. // READY";

    matrix.appendChild(
        core
    );

    shell.appendChild(
        matrix
    );

    demoNarration(
        shell,
        "LIVE CAPABILITY",
        "L.U.N.A. can listen, speak, control runtime functions, retain context, use local intelligence, and present information visually."
    );

    /*
       Safe live capability demonstration:
       briefly read the current volume without
       changing the user's setting.
    */

    getStatus()
        .then(status => {
            if (!demoRunning) return;

            const conversation =
                status?.conversation;

            if (conversation) {
                demoNarration(
                    shell,
                    "LIVE RUNTIME",
                    conversation.active
                        ? "Conversation runtime is active."
                        : "Conversation runtime is standing by."
                );
            }
        })
        .catch(() => {});
}

function renderDemoFinale() {
    const shell =
        createDemoShell();

    if (!shell) {
        return;
    }

    demoCorners(
        shell,
        "L.U.N.A. // COMPLETE",
        "SYSTEM ONLINE",
        "LOWKEY USEFUL NEURAL ASSISTANT",
        "READY"
    );

    const finale =
        createElement(
            "div",
            "demo-finale"
        );

    finale.appendChild(
        createElement(
            "div",
            "demo-finale-logo",
            "L.U.N.A."
        )
    );

    finale.appendChild(
        createElement(
            "div",
            "demo-finale-status",
            "VOICE · MEMORY · TOOLS · LOCAL AI · CONTROL"
        )
    );

    shell.appendChild(
        finale
    );

    demoNarration(
        shell,
        "DEMONSTRATION COMPLETE",
        "That's L.U.N.A."
    );

    /*
     * The finale holds for a moment, then the entire
     * presentation quietly disappears.
     *
     * The normal idle sphere is revealed underneath.
     */

    window.setTimeout(
        () => {
            if (!demoRunning) {
                return;
            }

            const presentation =
                byId(
                    "canvas-presentation"
                );

            if (!presentation) {
                return;
            }

            presentation.classList.add(
                "demo-finale-exit"
            );

            window.setTimeout(
                () => {
                    if (!demoRunning) {
                        return;
                    }

                    restoreIdleOrb();

                    showStateView(
                        "idle"
                    );
                },
                850
            );
        },
        2500
    );
}

function transitionDemoScene(
    renderScene
) {
    return new Promise(
        (resolve) => {
            const container =
                byId(
                    "canvas-presentation"
                );

            if (!container) {
                renderScene();
                resolve();
                return;
            }

            container.classList.remove(
                "demo-scene-enter",
                "demo-scene-exit"
            );

            /*
             * If this is the first scene, don't waste
             * time doing an exit animation.
             */

            const hasContent =
                container.children.length > 0;

            if (!hasContent) {
                renderScene();

                requestAnimationFrame(
                    () => {
                        container.classList.add(
                            "demo-scene-enter"
                        );

                        window.setTimeout(
                            () => {
                                container.classList.remove(
                                    "demo-scene-enter"
                                );

                                resolve();
                            },
                            520
                        );
                    }
                );

                return;
            }

            /*
             * Existing scene leaves first.
             */

            container.classList.add(
                "demo-scene-exit"
            );

            window.setTimeout(
                () => {
                    if (!demoRunning) {
                        resolve();
                        return;
                    }

                    container.classList.remove(
                        "demo-scene-exit"
                    );

                    renderScene();

                    requestAnimationFrame(
                        () => {
                            container.classList.add(
                                "demo-scene-enter"
                            );

                            window.setTimeout(
                                () => {
                                    container.classList.remove(
                                        "demo-scene-enter"
                                    );

                                    resolve();
                                },
                                520
                            );
                        }
                    );
                },
                260
            );
        }
    );
}

async function runDemoStep() {
    if (!demoRunning) {
        return;
    }

    const step =
        DEMO_STEPS[
            demoStepIndex
        ];

    if (!step) {
        finishDemo();
        return;
    }

    try {
        switch (step.id) {
            case "intro":
                await transitionDemoScene(
                    () => {
                        renderDemoIntro();
                    }
                );
                break;

            case "runtime": {
                const system =
                    await getSystem();

                if (demoRunning) {
                    await transitionDemoScene(
                        () => {
                            renderDemoRuntime(
                                system
                            );
                        }
                    );
                }

                break;
            }

            case "services": {
                const services =
                    await getServices();

                if (demoRunning) {
                    await transitionDemoScene(
                        () => {
                            renderDemoServices(
                                services
                            );
                        }
                    );
                }

                break;
            }

            case "intelligence": {
                const status =
                    await getStatus();

                if (demoRunning) {
                    await transitionDemoScene(
                        () => {
                            renderDemoIntelligence(
                                status
                            );
                        }
                    );
                }

                break;
            }

            case "memory": {
                const data =
                    await getDataStatus();

                if (demoRunning) {
                    await transitionDemoScene(
                        () => {
                            renderDemoMemory(
                                data
                            );
                        }
                    );
                }

                break;
            }

            case "deployment": {
                const update =
                    await getUpdateStatus();

                if (demoRunning) {
                    await transitionDemoScene(
                        () => {
                            renderDemoDeployment(
                                update
                            );
                        }
                    );
                }

                break;
            }

            case "capabilities":
                await transitionDemoScene(
                    () => {
                        renderDemoCapabilities();
                    }
                );
                break;

            case "finale":
                await transitionDemoScene(
                    () => {
                        renderDemoFinale();
                    }
                );
                break;

            default:
                break;
        }
    } catch (error) {
        console.error(
            "[L.U.N.A.] Demo step failed:",
            error
        );
    }

    if (!demoRunning) {
        return;
    }

    demoTimeout =
        window.setTimeout(
            () => {
                demoTimeout = null;

                demoStepIndex += 1;

                runDemoStep();
            },
            step.duration
        );
}

function startDemo() {
    if (demoRunning) {
        return;
    }

    demoRunning = true;
    demoStepIndex = 0;

    clearDemoTimer();

    setDemoState(
        "RUNNING",
        true
    );

    closeSettingsForDemo();

    hideAllStateViews();

    show(
        "canvas-presentation"
    );

    runDemoStep();
}

function finishDemo() {
    clearDemoTimer();

    demoRunning = false;
    demoStepIndex = 0;

    setDemoState(
        "READY",
        false
    );

    restoreIdleOrb();
    destroyDemoShell();

    if (latestTelemetry?.dashboard) {
        const dashboard =
            latestTelemetry.dashboard;

        renderState(
            dashboard.state ?? "idle",
            dashboard.status?.message
        );
    } else {
        renderState(
            "idle"
        );
    }
}

function stopDemo() {
    if (!demoRunning) {
        return;
    }

    clearDemoTimer();

    demoRunning = false;
    demoStepIndex = 0;

    setDemoState(
        "READY",
        false
    );

    restoreIdleOrb();
    destroyDemoShell();

    if (latestTelemetry?.dashboard) {
        const dashboard =
            latestTelemetry.dashboard;

        renderState(
            dashboard.state ?? "idle",
            dashboard.status?.message
        );
    } else {
        renderState(
            "idle"
        );
    }
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
   L.U.N.A. CINEMATIC STARTUP SEQUENCE
   ========================================================= */

let startupAnimationFrame = null;
let startupSignaturePaths = [];
let startupSignatureLength = 0;


function setBootProgress(percent) {
    const value =
        Math.max(
            0,
            Math.min(
                100,
                percent
            )
        );

    const bar =
        byId(
            "startup-progress-bar"
        );

    if (bar) {
        bar.style.width =
            `${value}%`;
    }

    const bootBar =
        byId(
            "boot-progress-bar"
        );

    if (bootBar) {
        bootBar.style.width =
            `${value}%`;
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

    setBootProgress(
        percent
    );
}


function wait(
    milliseconds
) {
    return new Promise(
        resolve =>
            window.setTimeout(
                resolve,
                milliseconds
            )
    );
}


function stopStartupAnimation() {
    if (
        startupAnimationFrame !== null
    ) {
        cancelAnimationFrame(
            startupAnimationFrame
        );

        startupAnimationFrame = null;
    }
}


function resetStartupSignature() {
    stopStartupAnimation();

    startupSignaturePaths = [];
    startupSignatureLength = 0;

    const paths =
        document.querySelectorAll(
            "#startup-signature-svg path"
        );

    paths.forEach(
        path => {
            const length =
                path.getTotalLength();

            path.style.strokeDasharray =
                `${length}`;

            path.style.strokeDashoffset =
                `${length}`;

            startupSignaturePaths.push({
                path,
                length,
            });

            startupSignatureLength +=
                length;
        }
    );
}


function animateStartupSignature(
    duration = 760
) {
    resetStartupSignature();

    const signature =
        byId(
            "startup-signature"
        );

    const subtitle =
        byId(
            "startup-signature-subtitle"
        );

    const pen =
        byId(
            "startup-pen"
        );

    if (!signature) {
        return Promise.resolve();
    }

    signature.classList.add(
        "is-visible"
    );

    if (subtitle) {
        subtitle.classList.remove(
            "visible"
        );
    }

    const start =
        performance.now();

    let completed = false;

    return new Promise(
        resolve => {

            function frame(
                now
            ) {
                if (
                    completed
                ) {
                    return;
                }

                const elapsed =
                    now - start;

                const progress =
                    Math.min(
                        1,
                        elapsed /
                        duration
                    );

                /*
                 * Slight easing.
                 *
                 * The beginning is quick,
                 * the final stroke settles
                 * smoothly.
                 */

                const eased =
                    1 -
                    Math.pow(
                        1 - progress,
                        2.4
                    );

                let remaining =
                    startupSignatureLength *
                    eased;

                let activePath =
                    null;

                let activeDistance =
                    0;

                for (
                    const item
                    of startupSignaturePaths
                ) {

                    if (
                        remaining >=
                        item.length
                    ) {
                        item.path.style.strokeDashoffset =
                            "0";

                        remaining -=
                            item.length;

                        continue;
                    }

                    activePath =
                        item.path;

                    activeDistance =
                        remaining;

                    item.path.style.strokeDashoffset =
                        `${item.length - remaining}`;

                    break;
                }

                if (
                    pen &&
                    activePath
                ) {
                    try {
                        const point =
                            activePath.getPointAtLength(
                                activeDistance
                            );

                        const svg =
                            byId(
                                "startup-signature-svg"
                            );

                        const rect =
                            svg?.getBoundingClientRect();

                        const viewBoxWidth =
                            520;

                        const viewBoxHeight =
                            130;

                        if (
                            rect &&
                            svg
                        ) {
                            const scaleX =
                                rect.width /
                                viewBoxWidth;

                            const scaleY =
                                rect.height /
                                viewBoxHeight;

                            pen.style.left =
                                `${rect.left +
                                point.x *
                                scaleX}px`;

                            pen.style.top =
                                `${rect.top +
                                point.y *
                                scaleY}px`;
                        }
                    } catch {
                        // Keep signature animation alive.
                    }
                }

                if (
                    progress >= 1
                ) {
                    startupSignaturePaths.forEach(
                        item => {
                            item.path.style.strokeDashoffset =
                                "0";
                        }
                    );

                    if (pen) {
                        pen.style.opacity =
                            "0";
                    }

                    if (subtitle) {
                        subtitle.classList.add(
                            "visible"
                        );
                    }

                    completed = true;

                    startupAnimationFrame =
                        null;

                    window.setTimeout(
                        resolve,
                        260
                    );

                    return;
                }

                startupAnimationFrame =
                    requestAnimationFrame(
                        frame
                    );
            }

            startupAnimationFrame =
                requestAnimationFrame(
                    frame
                );
        }
    );
}


function updateStartupServices(
    services
) {
    const container =
        byId(
            "startup-services"
        );

    if (!container) {
        return;
    }

    const serviceList =
        services ?? [];

    document
        .querySelectorAll(
            ".startup-service"
        )
        .forEach(
            element => {

                const name =
                    element.dataset.service;

                const service =
                    serviceList.find(
                        item =>
                            item.name ===
                            name
                    );

                const state =
                    element.querySelector(
                        ".startup-service-state"
                    );

                const active =
                    service?.active === true;

                const serviceState =
                    String(
                        service?.state ??
                        "checking"
                    ).toUpperCase();

                element.classList.remove(
                    "online",
                    "warning",
                    "error"
                );

                if (active) {
                    element.classList.add(
                        "online"
                    );

                    if (state) {
                        state.textContent =
                            "ONLINE";
                    }

                    return;
                }

                if (
                    serviceState ===
                    "DEVELOPMENT"
                ) {
                    element.classList.add(
                        "warning"
                    );

                    if (state) {
                        state.textContent =
                            "DEVELOPMENT";
                    }

                    return;
                }

                element.classList.add(
                    "error"
                );

                if (state) {
                    state.textContent =
                        serviceState ===
                        "CHECKING"
                            ? "CHECKING"
                            : "OFFLINE";
                }
            }
        );
}


function prepareStartup() {
    const overlay =
        byId(
            "startup-overlay"
        );

    if (!overlay) {
        return;
    }

    stopStartupAnimation();

    overlay.classList.remove(
        "hidden"
    );

    overlay.classList.remove(
        "startup-awake",
        "startup-core-active",
        "startup-services-active",
        "startup-signature-active",
        "startup-dashboard"
    );

    overlay.classList.add(
        "startup-active"
    );

    overlay.style.opacity =
        "1";

    resetStartupSignature();

    const pen =
        byId(
            "startup-pen"
        );

    if (pen) {
        pen.style.opacity =
            "0";
    }

    const signature =
        byId(
            "startup-signature"
        );

    if (signature) {
        signature.classList.remove(
            "is-visible"
        );
    }

    const subtitle =
        byId(
            "startup-signature-subtitle"
        );

    if (subtitle) {
        subtitle.classList.remove(
            "visible"
        );
    }

    document
        .querySelectorAll(
            ".startup-service"
        )
        .forEach(
            element => {
                element.classList.remove(
                    "online",
                    "warning",
                    "error"
                );

                const state =
                    element.querySelector(
                        ".startup-service-state"
                    );

                if (state) {
                    state.textContent =
                        "VERIFYING";
                }
            }
        );
}


function revealDashboard() {
    const overlay =
        byId(
            "startup-overlay"
        );

    if (!overlay) {
        return;
    }

    overlay.classList.add(
        "startup-dashboard"
    );

    /*
     * Give the dashboard a tiny moment
     * to emerge through the startup field.
     */

    window.setTimeout(
        () => {
            overlay.style.opacity =
                "0";

            overlay.classList.remove(
                "startup-active"
            );

            window.setTimeout(
                () => {
                    overlay.classList.add(
                        "hidden"
                    );

                    overlay.style.opacity =
                        "";

                    /*
                     * Make absolutely sure
                     * the real idle state is
                     * visible after startup.
                     */

                    if (
                        !demoRunning
                    ) {
                        renderState(
                            "idle",
                            "L.U.N.A. online"
                        );
                    }
                },
                650
            );

        },
        180
    );
}


async function runStartupSequence(
    telemetry
) {
    if (
        startupRunning
    ) {
        return;
    }

    startupRunning = true;

    prepareStartup();

    const boot =
        telemetry?.dashboard?.boot;

    let services = [];

    try {
        services =
            await getServices();
    } catch {
        services = [];
    }

    updateStartupServices(
        services
    );


    /* ---------------------------------------------------------
       PHASE 01 — SILENCE
       --------------------------------------------------------- */

    setBootPhase(
        " ",
        "",
        0
    );

    await wait(
        220
    );


    /* ---------------------------------------------------------
       PHASE 02 — WAKE
       --------------------------------------------------------- */

    const overlay =
        byId(
            "startup-overlay"
        );

    overlay?.classList.add(
        "startup-awake"
    );

    setBootPhase(
        "WAKE",
        "Establishing local runtime",
        12
    );

    await wait(
        650
    );


    /* ---------------------------------------------------------
       PHASE 03 — CORE
       --------------------------------------------------------- */

    overlay?.classList.add(
        "startup-core-active"
    );

    setBootPhase(
        "CORE",
        "Forming L.U.N.A. core",
        28
    );

    await wait(
        720
    );


    /* ---------------------------------------------------------
       PHASE 04 — SERVICES
       --------------------------------------------------------- */

    overlay?.classList.add(
        "startup-services-active"
    );

    setBootPhase(
        "SYSTEM",
        "Bringing local services online",
        48
    );

    await wait(
        620
    );


    /*
     * Re-check service state after the
     * constellation has appeared.
     */

    try {
        services =
            await getServices();

        updateStartupServices(
            services
        );
    } catch {
        // Keep the last known state.
    }


    /* ---------------------------------------------------------
       PHASE 05 — IDENTITY
       --------------------------------------------------------- */

    overlay?.classList.add(
        "startup-signature-active"
    );

    setBootPhase(
        "IDENTITY",
        "Loading assistant profile",
        70
    );

    await wait(
        280
    );

    await animateStartupSignature(
        820
    );


    /* ---------------------------------------------------------
       PHASE 06 — ONLINE
       --------------------------------------------------------- */

    setBootPhase(
        "ONLINE",
        "L.U.N.A. is ready",
        100
    );

    await wait(
        480
    );


    /* ---------------------------------------------------------
       FINALIZE
       --------------------------------------------------------- */

    if (
        boot?.boot_id
    ) {
        localStorage.setItem(
            "luna_last_boot_id",
            boot.boot_id
        );
    }

    revealDashboard();

    startupRunning =
        false;
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
    const enabled = !latestTelemetry?.voice?.listening;

    try {
        await postJson("/api/control", {
            action: "listen",
            payload: {
                enabled,
            },
        });

        showToast(
            enabled
                ? "Listening enabled."
                : "Listening disabled."
        );

        await refreshTelemetry();
    } catch (error) {
        showToast(error.message, "warning");
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
    const confirmed = window.confirm(
        "Reboot L.U.N.A.?\n\nThe Raspberry Pi will restart and all L.U.N.A. services will go offline temporarily."
    );

    if (!confirmed) {
        return;
    }

    showToast("Rebooting L.U.N.A....");

    try {
        await postJson(
            "/api/control",
            {
                action: "reboot",
                payload: {},
            }
        );
    } catch (error) {
        showToast(
            error.message,
            "warning"
        );
    }
}

function updateControlState() {
    const listening = Boolean(
        latestTelemetry?.voice?.listening
    );

    const button = byId("listening-button");

    if (!button) return;

    button.classList.toggle(
        "active",
        listening
    );
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

    byId("stop-button")
        ?.addEventListener(
            "click",
            async () => {

                if (demoRunning) {
                    stopDemo();

                    showToast(
                        "L.U.N.A. demo stopped."
                    );

                    return;
                }

                try {
                    await postJson(
                        "/api/control",
                        {
                            action: "stop",
                            payload: {},
                        }
                    );

                    showToast(
                        "L.U.N.A. stopped."
                    );
                } catch (error) {
                    showToast(
                        error.message,
                        "warning"
                    );
                }
            }
        );

    byId("restart-button")
        ?.addEventListener(
            "click",
            restartAgent
        );

    byId("mute-button")?.addEventListener("click", async () => {
        const muted = !Boolean(
            latestTelemetry?.voice?.mic_muted
        );

        try {
            const result = await postJson("/api/control", {
                action: "mic",
                payload: {
                    enabled: !muted,
                },
            });

            if (result.status === "unavailable") {
                showToast(
                    "Hardware microphone control is Pi-only.",
                    "warning"
                );
                return;
            }

            showToast(
                muted
                    ? "Microphone muted."
                    : "Microphone unmuted."
            );

            await refreshTelemetry();
        } catch (error) {
            showToast(error.message, "warning");
        }
    });

    document
        .querySelectorAll(".service-item")
        .forEach(item => {
            item.addEventListener(
                "click",
                () => {
                    openServiceMenu(
                        item.dataset.service
                    );
                }
            );
        });

    byId("service-menu-close")
        ?.addEventListener(
            "click",
            closeServiceMenu
        );

    byId("service-start")
        ?.addEventListener(
            "click",
            () =>
                controlSelectedService(
                    "start"
                )
        );

    byId("service-stop")
        ?.addEventListener(
            "click",
            () =>
                controlSelectedService(
                    "stop"
                )
        );

    byId("service-restart")
        ?.addEventListener(
            "click",
            () =>
                controlSelectedService(
                    "restart"
                )
        );

    const volumeButton = byId("volume-button");
    const volumeMenu = byId("volume-menu");
    const volumeSlider = byId("volume-slider");
    const volumeValue = byId("volume-value");

    if (volumeButton && volumeMenu && volumeSlider) {
        volumeButton.addEventListener("click", () => {
            volumeMenu.classList.toggle("hidden");
        });

        volumeSlider.addEventListener("input", async () => {
            const volume = Number(volumeSlider.value);

            if (volumeValue) {
                volumeValue.textContent = `${volume}%`;
            }

            try {
                await postJson("/api/control", {
                    action: "volume",
                    payload: { volume },
                });
            } catch (error) {
                showToast(error.message, "warning");
            }
        });
    }

    byId("settings-button")
        ?.addEventListener(
            "click",
            () => {
                byId("settings-overlay")
                    ?.classList.remove("hidden");
            }
        );

    byId("settings-close")
        ?.addEventListener(
            "click",
            () => {
                byId("settings-overlay")
                    ?.classList.add("hidden");
            }
        );

    byId("settings-overlay")
        ?.addEventListener(
            "click",
            (event) => {
                if (
                    event.target ===
                    byId("settings-overlay")
                ) {
                    byId("settings-overlay")
                        ?.classList.add("hidden");
                }
            }
        );

    byId("settings-demo-button")
        ?.addEventListener(
            "click",
            () => {
                startDemo();
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

    if (!demoRunning) {
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
        const [telemetry, services] =
            await Promise.all([
                getTelemetry(),
                getServices(),
            ]);

        renderTelemetry(
            telemetry
        );

        renderServices(
            services
        );

        renderServicesSettings(
            services
        );

        const system = await getSystem();
        renderSystemSettings(system);
        renderNetworkSettings(system);

        const status = await getStatus();
        renderAISettings(status);

        getDataStatus()
            .then((dataStatus) => {
                renderDataSettings(dataStatus);
            })
            .catch((error) => {
                console.error(
                    "[L.U.N.A.] Data status failed:",
                    error
                );
            });

        getUpdateStatus()
            .then((updateStatus) => {
                renderUpdateSettings(updateStatus);
            })
            .catch((error) => {
                console.error("[L.U.N.A.] Update status failed:", error);
            });

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