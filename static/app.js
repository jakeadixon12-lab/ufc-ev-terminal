let varianceChart = null;

document.addEventListener("DOMContentLoaded", () => {
  loadMetrics();
  loadWagers();
  initChart();
});

// 1. Fetch & Render Bankroll Metrics
async function loadMetrics() {
  try {
    const res = await fetch("/api/metrics");
    const data = await res.json();

    document.getElementById("statCash").innerText = `$${data.current_cash.toFixed(2)}`;
    document.getElementById("statExposure").innerText = `$${data.pending_exposure.toFixed(2)}`;
    document.getElementById("statPortfolio").innerText = `$${data.total_portfolio_value.toFixed(2)}`;
    document.getElementById("statTheoretical").innerText = `${data.theoretical_ev_dollars >= 0 ? '+' : ''}$${data.theoretical_ev_dollars.toFixed(2)}`;
    document.getElementById("statPnL").innerText = `${data.realized_profit >= 0 ? '+' : ''}$${data.realized_profit.toFixed(2)}`;

    const pnlEl = document.getElementById("statPnL");
    if (data.realized_profit > 0) pnlEl.className = "text-2xl font-bold text-emerald-400 mt-1";
    else if (data.realized_profit < 0) pnlEl.className = "text-2xl font-bold text-red-400 mt-1";
  } catch (err) {
    console.error("Error loading metrics:", err);
  }
}

// 2. Fetch & Render Wagers Ledger
async function loadWagers() {
  try {
    const res = await fetch("/api/wagers");
    const wagers = await res.json();
    const tbody = document.getElementById("wagersTableBody");
    tbody.innerHTML = "";

    wagers.forEach(w => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-gray-800/40 transition";

      let statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">PENDING</span>`;
      if (w.status === "WON") statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">WON</span>`;
      if (w.status === "LOST") statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/20">LOST</span>`;
      if (w.status === "PUSH") statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/20">PUSH</span>`;

      tr.innerHTML = `
        <td class="py-3 font-semibold text-white">${w.fighter_selected}</td>
        <td class="text-gray-400">${w.opponent}</td>
        <td class="text-gray-300">${w.sportsbook}</td>
        <td class="font-mono text-emerald-400 font-bold">${w.odds_placed > 0 ? '+' : ''}${w.odds_placed}</td>
        <td>$${w.stake.toFixed(2)}</td>
        <td class="font-mono text-white">$${w.potential_payout.toFixed(2)}</td>
        <td class="font-mono text-indigo-400 font-semibold">+${(w.expected_value * 100).toFixed(2)}%</td>
        <td>${statusBadge}</td>
        <td>
          ${w.status === "PENDING" ? `
            <div class="flex gap-1">
              <button onclick="settleBet(${w.id}, 'WON')" class="bg-emerald-600/80 hover:bg-emerald-500 text-white px-2 py-0.5 rounded text-[10px]">Win</button>
              <button onclick="settleBet(${w.id}, 'LOST')" class="bg-red-600/80 hover:bg-red-500 text-white px-2 py-0.5 rounded text-[10px]">Loss</button>
              <button onclick="settleBet(${w.id}, 'PUSH')" class="bg-gray-700 hover:bg-gray-600 text-white px-2 py-0.5 rounded text-[10px]">Push</button>
            </div>
          ` : `<span class="text-gray-500 text-[11px]">Settled</span>`}
        </td>
      `;
      tbody.appendChild(tr);
    });

    updateChartData(wagers);
  } catch (err) {
    console.error("Error loading wagers:", err);
  }
}

// 3. Settle a Bet
async function settleBet(betId, status) {
  try {
    const res = await fetch(`/api/wagers/${betId}/settle`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    });
    if (res.ok) {
      loadMetrics();
      loadWagers();
    }
  } catch (err) {
    console.error("Settlement error:", err);
  }
}

// 4. Trigger Live +EV Scraper with AI Analysis
async function triggerScan() {
  const statusEl = document.getElementById("scanStatus");
  const listEl = document.getElementById("scannerList");
  const btn = document.getElementById("btnScan");

  btn.disabled = true;
  statusEl.innerText = "Querying live odds & evaluating market consensus...";
  listEl.innerHTML = `<div class="text-xs text-amber-400 animate-pulse py-2">Running scrapers and executing Gemini analysis...</div>`;

  try {
    const res = await fetch("/api/scan_ev");
    const data = await res.json();

    statusEl.innerText = `Scan complete. Found ${data.count} +EV divergence(s).`;
    listEl.innerHTML = "";

    if (data.bets.length === 0) {
      listEl.innerHTML = `<div class="text-xs text-gray-400 py-2">No edges above +1.0% currently available across retail books.</div>`;
    } else {
      data.bets.forEach(b => {
        const item = document.createElement("div");
        item.className = "bg-gray-900 border border-gray-800 p-4 rounded text-xs space-y-2";
        item.innerHTML = `
          <div class="flex justify-between items-start">
            <div>
              <span class="text-sm font-bold text-white">${b.fighter}</span>
              <span class="text-gray-400 ml-1">vs. ${b.opponent}</span>
              <div class="text-emerald-400 font-semibold mt-0.5">
                ${b.book} at ${b.offered_odds > 0 ? '+' : ''}${b.offered_odds} 
                <span class="text-gray-400 font-normal">(Sharp Fair: ${b.fair_odds > 0 ? '+' : ''}${b.fair_odds} via ${b.benchmark})</span>
              </div>
            </div>
            <div class="text-right">
              <span class="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-mono font-bold">+${b.ev_pct}% EV</span>
              <div class="text-[11px] text-gray-400 mt-1">Suggested Stake: <strong class="text-white">$${b.suggested_stake.toFixed(2)}</strong></div>
            </div>
          </div>
          <div class="bg-gray-950/70 p-2.5 rounded border border-gray-800 text-gray-300 text-[11px] leading-relaxed">
            <span class="text-indigo-400 font-semibold">AI Rationale:</span> ${b.rationale}
          </div>
        `;
        listEl.appendChild(item);
      });
    }
  } catch (err) {
    statusEl.innerText = "Error scanning odds.";
    listEl.innerHTML = `<div class="text-xs text-red-400">Failed to complete scrape: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
  }
}

// 5. Manual Calculator
async function calculateManual() {
  const sharpA = parseInt(document.getElementById("sharpA").value);
  const sharpB = parseInt(document.getElementById("sharpB").value);
  const offered = parseInt(document.getElementById("retailOdds").value);

  if (!sharpA || !sharpB || !offered) return;

  try {
    const res = await fetch("/api/calculate_custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sharp_odds_a: sharpA, sharp_odds_b: sharpB, offered_odds: offered, bankroll: 200.0 })
    });
    const d = await res.json();

    document.getElementById("calcResults").classList.remove("hidden");
    document.getElementById("resFair").innerText = `${d.fair_odds_a > 0 ? '+' : ''}${d.fair_odds_a} (${d.true_prob_a}%)`;
    
    const evEl = document.getElementById("resEV");
    evEl.innerText = `${d.ev_pct > 0 ? '+' : ''}${d.ev_pct}%`;
    evEl.className = d.ev_pct > 0 ? "font-mono font-bold text-emerald-400" : "font-mono font-bold text-red-400";
    
    document.getElementById("resStake").innerText = `$${d.quarter_kelly_stake.toFixed(2)}`;
  } catch (err) {
    console.error("Calculation error:", err);
  }
}

// 6. Variance Chart: Theoretical vs Realized
function initChart() {
  const ctx = document.getElementById("varianceChart").getContext("2d");
  varianceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["Start", "Active Portfolio"],
      datasets: [
        {
          label: "Realized Bankroll ($)",
          data: [200, 200],
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          tension: 0.2,
          fill: true
        },
        {
          label: "Theoretical EV Trajectory ($)",
          data: [200, 201.80],
          borderColor: "#818cf8",
          borderDash: [5, 5],
          tension: 0.2,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#9ca3af", font: { size: 11 } } }
      },
      scales: {
        x: { ticks: { color: "#6b7280" }, grid: { color: "#1f2937" } },
        y: { ticks: { color: "#6b7280" }, grid: { color: "#1f2937" } }
      }
    }
  });
}

function updateChartData(wagers) {
  if (!varianceChart) return;
  let realized = 200.0;
  let theoretical = 200.0;

  const labels = ["Start"];
  const realizedPoints = [200.0];
  const theoreticalPoints = [200.0];

  wagers.slice().reverse().forEach((w, idx) => {
    labels.push(`Bet #${idx + 1}`);
    theoretical += (w.stake * w.expected_value);
    if (w.status === "WON") realized += (w.potential_payout - w.stake);
    else if (w.status === "LOST") realized -= w.stake;

    realizedPoints.push(parseFloat(realized.toFixed(2)));
    theoreticalPoints.push(parseFloat(theoretical.toFixed(2)));
  });

  varianceChart.data.labels = labels;
  varianceChart.data.datasets[0].data = realizedPoints;
  varianceChart.data.datasets[1].data = theoreticalPoints;
  varianceChart.update();
}