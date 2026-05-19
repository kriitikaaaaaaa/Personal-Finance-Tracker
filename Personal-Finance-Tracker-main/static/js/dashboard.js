/* Dashboard analytics (Chart.js)
   Keeps charts minimal and professional. */
(function () {
  function getJSONFromScript(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "null");
    } catch (_e) {
      return null;
    }
  }

  function moneyTick(value) {
    var n = Number(value || 0);
    return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  function initIncomeExpenseBar(monthly) {
    var canvas = document.getElementById("chartIncomeExpense");
    if (!canvas || !window.Chart || !Array.isArray(monthly)) return;

    var labels = monthly.map(function (r) {
      return r.label || r.month_label;
    });
    var income = monthly.map(function (r) {
      return Number(r.income || 0);
    });
    var expense = monthly.map(function (r) {
      return Number(r.expense || 0);
    });

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Income",
            data: income,
            backgroundColor: "rgba(22, 163, 74, 0.35)",
            borderColor: "rgba(22, 163, 74, 0.75)",
            borderWidth: 1,
            borderRadius: 8,
            maxBarThickness: 26,
          },
          {
            label: "Expense",
            data: expense,
            backgroundColor: "rgba(220, 38, 38, 0.22)",
            borderColor: "rgba(220, 38, 38, 0.65)",
            borderWidth: 1,
            borderRadius: 8,
            maxBarThickness: 26,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 450 },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.label + ": " + moneyTick(ctx.parsed.y);
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { callback: moneyTick, maxTicksLimit: 6 },
            grid: { color: "rgba(17, 24, 39, 0.08)" },
          },
        },
      },
    });
  }

  function initCategoryPie(categories) {
    var canvas = document.getElementById("chartCategoryPie");
    if (!canvas || !window.Chart || !Array.isArray(categories)) return;

    var filtered = categories.filter(function (r) {
      return Number(r.total || 0) > 0;
    });

    var labels = filtered.map(function (r) {
      return r.category || "Other";
    });
    var totals = filtered.map(function (r) {
      return Number(r.total || 0);
    });

    if (totals.length === 0) {
      return;
    }

    var palette = [
      "rgba(37, 99, 235, 0.55)",
      "rgba(22, 163, 74, 0.45)",
      "rgba(99, 102, 241, 0.45)",
      "rgba(14, 165, 233, 0.40)",
      "rgba(168, 85, 247, 0.35)",
      "rgba(217, 119, 6, 0.35)",
      "rgba(220, 38, 38, 0.28)",
    ];

    new Chart(canvas, {
      type: "pie",
      data: {
        labels: labels,
        datasets: [
          {
            data: totals,
            backgroundColor: labels.map(function (_l, i) {
              return palette[i % palette.length];
            }),
            borderColor: "rgba(255,255,255,1)",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 450 },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var val = ctx.parsed || 0;
                return ctx.label + ": " + moneyTick(val);
              },
            },
          },
        },
      },
    });
  }

  function initExpenseTrendLine(monthly) {
    var canvas = document.getElementById("chartExpenseTrend");
    if (!canvas || !window.Chart || !Array.isArray(monthly)) return;

    var labels = monthly.map(function (r) {
      return r.label || r.month_label;
    });
    var expense = monthly.map(function (r) {
      return Number(r.expense || 0);
    });

    new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Expenses",
            data: expense,
            borderColor: "rgba(37, 99, 235, 0.85)",
            backgroundColor: "rgba(37, 99, 235, 0.10)",
            fill: true,
            tension: 0.35,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 450 },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return "Expenses: " + moneyTick(ctx.parsed.y);
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { callback: moneyTick, maxTicksLimit: 6 },
            grid: { color: "rgba(17, 24, 39, 0.08)" },
          },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var monthly = getJSONFromScript("dashboard-monthly-data") || [];
    var categories = getJSONFromScript("dashboard-category-data") || [];
    initIncomeExpenseBar(monthly);
    initCategoryPie(categories);
    initExpenseTrendLine(monthly);
  });
})();

