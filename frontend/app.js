// DriveMind Fleet Intelligence Client Engine

// Detect if running on Vercel (static mode) vs local FastAPI server
const IS_STATIC = window.location.hostname.includes('vercel.app');
const API_BASE = window.location.hostname.includes('vercel.app')
    ? "https://drivemind-production-a022.up.railway.app"
    : "";

function apiUrl(path) {
    if (!IS_STATIC) return path;
    // Map dynamic API routes to pre-generated static JSON files
    if (path === '/api/fleet') return '/static_data/fleet.json';
    if (path === '/api/graph') return '/static_data/graph.json';
    if (path === '/api/data-source') return '/static_data/data_source.json';
    // Dynamic vehicle/telemetry routes
    const vehicleMatch = path.match(/\/api\/vehicle\/(.+)/);
    if (vehicleMatch) return `/static_data/vehicle_${vehicleMatch[1]}.json`;
    const telemetryMatch = path.match(/\/api\/telemetry\/(.+)/);
    if (telemetryMatch) return `/static_data/telemetry_${telemetryMatch[1]}.json`;
    return path;
}

let selectedVehicleId = null;
let telemetryChart = null;
let shapChart = null;
let visNetwork = null;
let allKgNodes = {};

// On window load
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupTabSwitching();
    setupChatInterface();
    setupEvaluationRunner();
    initHeroCanvas();
    initScrambleTitle();
    initLiveViewers();
    
    // Fetch initial fleet data
    await fetchFleetInventory();
    await fetchKnowledgeGraph();
    await fetchDataSource();
    
    // Automatically select the first vehicle or TRK-427 (if present)
    const trk427 = document.querySelector('[data-vehicle-id="TRK-427"]');
    if (trk427) {
        trk427.click();
    } else {
        const firstRow = document.querySelector("#fleet-inventory-body tr");
        if (firstRow) firstRow.click();
    }
}

// 1. Tab Navigation Routing
function setupTabSwitching() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".workspace-tab").forEach(w => w.classList.remove("active"));
            
            tab.classList.add("active");
            const tabId = tab.getAttribute("data-tab");
            const tabEl = document.getElementById(tabId);
            tabEl.classList.add("active");
            
            // Adjust Vis.js size or charts rendering when tabs show
            if (tabId === "tab-graph" && visNetwork) {
                visNetwork.fit();
            }
        });
    });
}

function switchToTab(tabId) {
    const tabBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
    if (tabBtn) {
        tabBtn.click();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function scrollToBento() {
    const el = document.getElementById("architecture-bento");
    if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
    }
}

function initScrambleTitle() {
    const el = document.getElementById("scramble-title");
    if (!el) return;
    const targetText = "DRIVEMIND";
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&";
    let iteration = 0;
    const interval = setInterval(() => {
        el.innerText = targetText
            .split("")
            .map((letter, index) => {
                if (index < iteration) {
                    return targetText[index];
                }
                return chars[Math.floor(Math.random() * chars.length)];
            })
            .join("");

        if (iteration >= targetText.length) {
            clearInterval(interval);
        }
        iteration += 1 / 3;
    }, 35);
}

function initHeroCanvas() {
    const canvas = document.getElementById("hero-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let width, height;
    function resize() {
        width = canvas.width = canvas.offsetWidth;
        height = canvas.height = canvas.offsetHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    let t = 0;
    const dots = Array.from({ length: 50 }, () => ({
        x: Math.random() * (width || 800),
        y: Math.random() * (height || 500),
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: Math.random() * 2 + 1
    }));

    function animate() {
        t += 0.01;
        ctx.clearRect(0, 0, width, height);

        // Sci-Fi Grid lines
        ctx.strokeStyle = "rgba(99, 102, 241, 0.05)";
        ctx.lineWidth = 1;
        const gridSize = 45;
        for (let x = 0; x < width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        for (let y = 0; y < height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        // Animated laser scan line
        const scanY = (Math.sin(t * 0.7) * 0.5 + 0.5) * height;
        const grad = ctx.createLinearGradient(0, scanY - 35, 0, scanY + 35);
        grad.addColorStop(0, "rgba(56, 189, 248, 0)");
        grad.addColorStop(0.5, "rgba(56, 189, 248, 0.18)");
        grad.addColorStop(1, "rgba(56, 189, 248, 0)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, scanY - 35, width, 70);

        // Floating ambient particles
        dots.forEach(d => {
            d.x += d.vx;
            d.y += d.vy;
            if (d.x < 0 || d.x > width) d.vx *= -1;
            if (d.y < 0 || d.y > height) d.vy *= -1;

            ctx.beginPath();
            ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(129, 140, 248, 0.45)";
            ctx.fill();
        });

        requestAnimationFrame(animate);
    }
    animate();
}

// 2. Fetch Fleet inventory and populate table
async function fetchFleetInventory() {
    try {
        const response = await fetch(apiUrl("/api/fleet"));
        const vehicles = await response.json();
        
        const tbody = document.getElementById("fleet-inventory-body");
        tbody.innerHTML = "";
        
        let warningsCount = 0;
        let criticalCount = 0;
        let healthyCount = 0;
        let anomaliesCount = 0;
        
        vehicles.forEach(v => {
            // Count metrics
            if (v.status === "Critical") criticalCount++;
            else if (v.status === "Warning") warningsCount++;
            else healthyCount++;
            
            if (v.anomaly_score > 60) anomaliesCount++;
            
            const tr = document.createElement("tr");
            tr.setAttribute("data-vehicle-id", v.id);
            
            let badgeClass = "healthy";
            if (v.status === "Warning") badgeClass = "warning";
            else if (v.status === "Critical") badgeClass = "critical";
            
            tr.innerHTML = `
                <td><strong>${v.id}</strong></td>
                <td>${v.manufacturer}</td>
                <td>${v.model}</td>
                <td>${v.year}</td>
                <td>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-family: monospace;">${v.anomaly_score}%</span>
                        <div style="width:50px; height:6px; background:rgba(255,255,255,0.05); border-radius:3px; overflow:hidden;">
                            <div style="width:${v.anomaly_score}%; height:100%; background:${v.anomaly_score > 60 ? 'red' : '#38bdf8'};"></div>
                        </div>
                    </div>
                </td>
                <td>${v.predicted_rul} days</td>
                <td><span class="status-badge ${badgeClass}">${v.status}</span></td>
            `;
            
            tr.addEventListener("click", () => {
                document.querySelectorAll("#fleet-inventory-body tr").forEach(row => row.classList.remove("active-inspect"));
                tr.classList.add("active-inspect");
                inspectVehicle(v.id);
            });
            
            tbody.appendChild(tr);
        });
        
        // Update top summary metrics
        document.getElementById("val-total-fleet").innerText = vehicles.length;
        document.getElementById("val-healthy-fleet").innerText = healthyCount;
        document.getElementById("val-warning-fleet").innerText = warningsCount;
        document.getElementById("val-critical-fleet").innerText = criticalCount;
        document.getElementById("val-active-anomalies").innerText = anomaliesCount;
        
        // Render SQL analytics charts based on these details
        renderSqlAnalyticsCharts(vehicles);
        
    } catch (e) {
        console.error("Failed fetching fleet assets:", e);
    }
}

// 3. Render Static SQL Charts based on loaded DB properties
function renderSqlAnalyticsCharts(vehicles) {
    // A. Failures by Manufacturer
    const mfrMap = {};
    vehicles.forEach(v => {
        if (!mfrMap[v.manufacturer]) {
            mfrMap[v.manufacturer] = { count: 0, critical: 0 };
        }
        mfrMap[v.manufacturer].count++;
        if (v.status === "Critical" || v.status === "Warning") {
            mfrMap[v.manufacturer].critical++;
        }
    });
    
    const categories = Object.keys(mfrMap);
    const data = categories.map(c => Math.round((mfrMap[c].critical / mfrMap[c].count) * 100));
    
    const mfrOptions = {
        series: [{ name: 'Warning/Failure Rate', data: data }],
        chart: { type: 'bar', height: 200, toolbar: { show: false }, foreColor: '#94a3b8' },
        plotOptions: { bar: { borderRadius: 4, horizontal: true } },
        colors: ['#ef4444'],
        xaxis: { categories: categories, title: { text: 'Percentage (%)' } },
        grid: { borderColor: 'rgba(255,255,255,0.05)' }
    };
    
    document.getElementById("chart-mfr-failures").innerHTML = "";
    new ApexCharts(document.getElementById("chart-mfr-failures"), mfrOptions).render();
    
    // B. Maintenance Costs by Component (Simulated DB summaries)
    const costOptions = {
        series: [2450, 1800, 1110, 420],
        labels: ['Drivetrain', 'Fuel Systems', 'Electrical', 'Cooling System'],
        chart: { type: 'donut', height: 200, foreColor: '#94a3b8' },
        colors: ['#38bdf8', '#06b6d4', '#818cf8', '#f59e0b'],
        stroke: { show: false },
        legend: { position: 'bottom' }
    };
    
    document.getElementById("chart-comp-costs").innerHTML = "";
    new ApexCharts(document.getElementById("chart-comp-costs"), costOptions).render();
}

// 4. Inspect specific vehicle diagnostics and load history
async function inspectVehicle(vehicleId) {
    selectedVehicleId = vehicleId;
    
    try {
        const response = await fetch(apiUrl(`/api/vehicle/${vehicleId}`));
        const v = await response.json();
        
        // Update Info Labels
        document.getElementById("inspect-id").innerText = v.metadata.id;
        document.getElementById("inspect-mfr-model").innerText = `${v.metadata.manufacturer} ${v.metadata.model} (${v.metadata.year})`;
        
        const badge = document.getElementById("inspect-status-badge");
        badge.innerText = v.diagnostics.status;
        badge.className = `profile-status ${v.diagnostics.status.toLowerCase()}`;
        
        document.getElementById("inspect-rul").innerText = `${v.diagnostics.predicted_rul} Days`;
        document.getElementById("inspect-anomaly").innerText = `${v.diagnostics.anomaly_score}%`;
        document.getElementById("inspect-fail-class").innerText = v.diagnostics.failure_class;
        
        // Populate probability list
        const probContainer = document.getElementById("failure-prob-container");
        probContainer.innerHTML = "";
        
        Object.entries(v.diagnostics.failure_probabilities).forEach(([cls, pct]) => {
            const row = document.createElement("div");
            row.className = "prob-row";
            row.innerHTML = `
                <div class="prob-labels">
                    <span class="prob-label">${cls}</span>
                    <span class="prob-value">${pct}%</span>
                </div>
                <div class="prob-bar-bg">
                    <div class="prob-bar-fill" style="width: ${pct}%"></div>
                </div>
            `;
            probContainer.appendChild(row);
        });
        
        // Render SHAP explainability chart
        renderShapChart(v.diagnostics.feature_attributions);
        
        // Load and plot telemetry history
        const tResponse = await fetch(apiUrl(`/api/telemetry/${vehicleId}`));
        const telemetry = await tResponse.json();
        renderTelemetryChart(telemetry);
        
    } catch (e) {
        console.error("Failed inspecting vehicle:", e);
    }
}

// 5. Render sensor telemetry streams
function renderTelemetryChart(data) {
    const timestamps = data.map(d => new Date(d.timestamp).toLocaleDateString());
    
    const options = {
        series: [
            { name: 'Coolant Temp (°F)', data: data.map(d => d.coolant_temp) },
            { name: 'Exhaust Temp (°F)', data: data.map(d => d.exhaust_temp) },
            { name: 'Vibration (g)', data: data.map(d => d.vibration) },
            { name: 'Voltage (V)', data: data.map(d => d.voltage) }
        ],
        chart: {
            type: 'line',
            height: 300,
            toolbar: { show: false },
            foreColor: '#94a3b8',
            zoom: { enabled: false }
        },
        stroke: { width: [3, 3, 2, 2], curve: 'smooth' },
        colors: ['#ef4444', '#f59e0b', '#10b981', '#38bdf8'],
        xaxis: { categories: timestamps },
        yaxis: [
            { title: { text: 'Temperature (°F)' } },
            { opposite: true, title: { text: 'Vibration / Voltage' } }
        ],
        grid: { borderColor: 'rgba(255,255,255,0.05)' },
        legend: { position: 'top' }
    };
    
    if (telemetryChart) {
        telemetryChart.destroy();
    }
    telemetryChart = new ApexCharts(document.getElementById("chart-telemetry"), options);
    telemetryChart.render();
}

// 6. Render SHAP feature attributions
function renderShapChart(attributions) {
    const categories = Object.keys(attributions);
    const data = Object.values(attributions);
    
    const options = {
        series: [{ name: 'Contribution Ratio (%)', data: data }],
        chart: { type: 'bar', height: 200, toolbar: { show: false }, foreColor: '#94a3b8' },
        plotOptions: {
            bar: {
                borderRadius: 4,
                horizontal: true,
                distributed: true
            }
        },
        colors: ['#ef4444', '#f59e0b', '#10b981', '#38bdf8', '#818cf8', '#06b6d4'],
        xaxis: { categories: categories },
        grid: { borderColor: 'rgba(255,255,255,0.05)' },
        legend: { show: false }
    };
    
    if (shapChart) {
        shapChart.destroy();
    }
    shapChart = new ApexCharts(document.getElementById("chart-shap"), options);
    shapChart.render();
}

// 7. Load and visualize Vis.js Knowledge Graph
async function fetchKnowledgeGraph() {
    try {
        const response = await fetch(apiUrl("/api/graph"));
        const graphData = await response.json();
        
        // Save nodes mapping for quick lookup on select
        allKgNodes = {};
        graphData.nodes.forEach(n => {
            allKgNodes[n.id] = n;
        });
        
        const container = document.getElementById("vis-graph-container");
        
        const data = {
            nodes: new vis.DataSet(graphData.nodes),
            edges: new vis.DataSet(graphData.edges)
        };
        
        const options = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: { color: '#f8fafc', size: 12, face: 'Outfit' },
                borderWidth: 2
            },
            edges: {
                color: 'rgba(255,255,255,0.15)',
                font: { color: '#94a3b8', size: 9, face: 'Outfit' },
                arrows: { to: { enabled: true, scaleFactor: 0.5 } }
            },
            groups: {
                Vehicle: { color: { background: '#1e293b', border: '#38bdf8' }, shape: 'dot', size: 24 },
                Component: { color: { background: '#064e3b', border: '#10b981' }, shape: 'dot', size: 20 },
                FaultCode: { color: { background: '#78350f', border: '#f59e0b' }, shape: 'diamond', size: 16 },
                Maintenance: { color: { background: '#334155', border: '#94a3b8' }, shape: 'square', size: 14 },
                Warranty: { color: { background: '#581c87', border: '#a855f7' }, shape: 'triangle', size: 14 }
            },
            physics: {
                barnesHut: { gravitationalConstant: -2500, centralGravity: 0.3, springLength: 95 },
                stabilization: { iterations: 100 }
            }
        };
        
        visNetwork = new vis.Network(container, data, options);
        
        // Node selection event
        visNetwork.on("click", (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                showNodeProperties(nodeId);
            }
        });
        
    } catch (e) {
        console.error("Failed loading Vis graph:", e);
    }
}

// Display selected node attributes
function showNodeProperties(nodeId) {
    const node = allKgNodes[nodeId];
    if (!node) return;
    
    const detailsContainer = document.getElementById("kg-node-details");
    detailsContainer.innerHTML = "";
    
    const title = document.createElement("div");
    title.className = "node-details-title";
    title.innerText = node.label;
    detailsContainer.appendChild(title);
    
    const type = document.createElement("div");
    type.className = "node-details-type";
    type.innerText = node.group;
    detailsContainer.appendChild(type);
    
    Object.entries(node.properties).forEach(([key, val]) => {
        const item = document.createElement("div");
        item.className = "node-prop-item";
        item.innerHTML = `<strong>${key.replace('_', ' ')}</strong> <span>${val}</span>`;
        detailsContainer.appendChild(item);
    });
}

// 8. Q&A Console Chat & Agent Trace Interface
function setupChatInterface() {
    const btnSubmit = document.getElementById("btn-submit-chat");
    const chatInput = document.getElementById("chat-input");
    
    btnSubmit.addEventListener("click", () => {
        const query = chatInput.value.trim();
        if (query) {
            submitQuestion(query);
            chatInput.value = "";
        }
    });
    
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            btnSubmit.click();
        }
    });
    
    // Example question buttons selection
    const btns = document.querySelectorAll(".btn-question");
    btns.forEach(btn => {
        btn.addEventListener("click", () => {
            const query = btn.getAttribute("data-query");
            submitQuestion(query);
        });
    });
}

async function submitQuestion(query) {
    const chatContainer = document.getElementById("chat-container");
    const trailSteps = document.getElementById("agent-trail-steps");
    
    // Add user message to chat UI
    const userMsg = document.createElement("div");
    userMsg.className = "message user-msg";
    userMsg.innerHTML = `
        <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
        <div class="msg-content"><p>${query}</p></div>
    `;
    chatContainer.appendChild(userMsg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Clear and start loading in the agent trace panel
    trailSteps.innerHTML = `
        <div class="empty-trail">
            <i class="fa-solid fa-spinner fa-spin loading-icon"></i>
            <p>Planner parsing intent...</p>
        </div>
    `;
    
    const diagnoseUrl = `${API_BASE}/api/diagnose`;
    console.log("Calling diagnose API:", diagnoseUrl);
    
    try {
        const response = await fetch(diagnoseUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: query })
        });
        const result = await response.json();
        
        // Add final report message from diagnosis agent to chat UI
        const systemMsg = document.createElement("div");
        systemMsg.className = "message system-msg";
        systemMsg.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="msg-content">${formatMarkdown(result.answer)}</div>
        `;
        chatContainer.appendChild(systemMsg);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // Draw the trace execution logs
        trailSteps.innerHTML = "";
        result.trace.forEach(step => {
            const stepCard = document.createElement("div");
            stepCard.className = "agent-step-card";
            
            const outStr = typeof step.output === "object" ? JSON.stringify(step.output, null, 2) : step.output;
            
            stepCard.innerHTML = `
                <div class="step-header">
                    <span class="step-agent-name">${step.agent}</span>
                </div>
                <div class="step-thought">${step.thought}</div>
                <div class="step-output-container">
                    <pre><code>${escapeHtml(outStr)}</code></pre>
                </div>
            `;
            trailSteps.appendChild(stepCard);
        });
        
    } catch (e) {
        console.error("Multi-agent diagnose failure:", e);
        const errMsg = document.createElement("div");
        errMsg.className = "message system-msg";
        errMsg.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-triangle-exclamation" style="color:red"></i></div>
            <div class="msg-content"><p style="color:red">Error running multi-agent diagnosis pipeline.</p></div>
        `;
        chatContainer.appendChild(errMsg);
    }
}

// 9. Evaluation Studio
function setupEvaluationRunner() {
    const btnRun = document.getElementById("btn-run-eval-suite");
    const tbody = document.getElementById("eval-table-body");
    
    btnRun.addEventListener("click", async () => {
        tbody.innerHTML = `<tr><td colspan="8" class="loading-td"><i class="fa-solid fa-spinner fa-spin"></i> Running evaluation test cases. This may take a moment...</td></tr>`;
        
        try {
            const response = await fetch(`${API_BASE}/api/evaluation`);
            const res = await response.json();
            
            // Set summaries
            document.getElementById("val-mean-precision").innerText = `${Math.round(res.summary.mean_precision * 100)}%`;
            document.getElementById("val-mean-recall").innerText = `${Math.round(res.summary.mean_recall_at_5 * 100)}%`;
            document.getElementById("val-mean-ndcg").innerText = res.summary.mean_ndcg;
            document.getElementById("val-mean-faithfulness").innerText = `${Math.round(res.summary.mean_faithfulness * 100)}%`;
            document.getElementById("val-mean-groundedness").innerText = `${Math.round(res.summary.mean_groundedness * 100)}%`;
            document.getElementById("val-mean-hallucination").innerText = `${Math.round(res.summary.mean_hallucination_rate * 100)}%`;
            document.getElementById("val-mean-latency").innerText = `${res.summary.mean_latency_ms} ms`;
            
            // Load case rows
            tbody.innerHTML = "";
            res.cases.forEach(c => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${c.query}</strong></td>
                    <td>${c.precision}</td>
                    <td>${c.recall_at_5}</td>
                    <td>${c.ndcg}</td>
                    <td>${c.faithfulness}</td>
                    <td>${c.groundedness}</td>
                    <td>${c.hallucination_rate === 0 ? '<span style="color:#10b981">None</span>' : '<span style="color:#ef4444">Yes</span>'}</td>
                    <td>${c.latency_ms} ms</td>
                `;
                tbody.appendChild(tr);
            });
            
        } catch (e) {
            console.error("Failed running evaluations:", e);
            tbody.innerHTML = `<tr><td colspan="8" class="placeholder-td" style="color:red">Error running evaluation benchmark suite.</td></tr>`;
        }
    });
}

// Helpers
function formatMarkdown(text) {
    if (!text) return "";
    
    // Replace headers
    let html = text
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^\* (.*$)/gim, '<li>$1</li>')
        .replace(/^- (.*$)/gim, '<li>$1</li>');
        
    // Handle simple lists wrapping
    // Replace code blocks
    html = html.replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');
    // Replace inline bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert newlines to paragraphs
    html = html.split("\n\n").map(p => {
        if (p.trim().startsWith("<h") || p.trim().startsWith("<li") || p.trim().startsWith("<pre")) {
            return p;
        }
        return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join("");
    
    return html;
}

function escapeHtml(text) {
    if (typeof text !== 'string') return text;
    return text
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// 10. Data Source Badge
async function fetchDataSource() {
    try {
        const resp = await fetch(apiUrl("/api/data-source"));
        const ds   = await resp.json();
        
        const header = document.querySelector(".header-tagline");
        if (!header) return;
        
        const isLive = ds.source === "smartcar_live";
        const badge  = document.createElement("div");
        badge.className = "data-source-badge";
        badge.style.cssText = `
            display: inline-flex; align-items: center; gap: 8px;
            margin-top: 8px; padding: 5px 12px;
            border-radius: 20px; font-size: 0.78rem; font-weight: 700;
            border: 1px solid ${isLive ? "rgba(16,185,129,0.4)" : "rgba(56,189,248,0.3)"};
            background: ${isLive ? "rgba(16,185,129,0.1)" : "rgba(56,189,248,0.08)"};
            color: ${isLive ? "#10b981" : "#38bdf8"};
        `;
        badge.innerHTML = `
            <span style="width:8px;height:8px;border-radius:50%;
                background:${isLive ? "#10b981" : "#38bdf8"};
                box-shadow: 0 0 6px ${isLive ? "#10b981" : "#38bdf8"};
                animation: pulse 2s infinite;"></span>
            <span>${ds.label}</span>
        `;
        badge.title = ds.description;
        header.appendChild(badge);
    } catch(e) {
        console.warn("Could not fetch data source status:", e);
    }
}

// 6. Live Viewers simulation
function initLiveViewers() {
    const el = document.getElementById("viewer-count");
    if (!el) return;
    
    let currentCount = 42;
    
    // Simulate minor fluctuations every 3-8 seconds
    setInterval(() => {
        // Randomly add or subtract 1 to 3 viewers
        const change = Math.floor(Math.random() * 5) - 2; // -2 to +2
        currentCount = Math.max(12, currentCount + change); // Keep a minimum
        
        el.innerText = currentCount;
    }, Math.random() * 5000 + 3000);
}
