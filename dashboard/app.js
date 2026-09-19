/* Dashboard UI. Depends on window.Measures (measures.js) and window.PAYLOAD. */
(function () {
  "use strict";
  var P = window.PAYLOAD, X = window.Measures;
  var theme = new URLSearchParams(location.search).get("theme");
  if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
  var months = P.meta.months;
  var state = { tab: "executive", month: P.meta.latest_month, segments: [], plans: [], products: [],
    customer: null, dimension: "segment", threshold: P.meta.risk_threshold, severity: "all",
    rule: "all", query: "", page: 0, invoice: null };
  var PAGE_SIZE = 12;
  var TABS = [["executive", "Executive Overview"], ["revenue", "Revenue & Retention"],
    ["risk", "Customer Risk"], ["finance", "Finance Controls"]];
  var SERIES = { new: "var(--c-new)", expansion: "var(--c-exp)", reactivation: "var(--c-react)",
    contraction: "var(--c-con)", churned: "var(--c-churn)" };

  /* ---------- formatting ---------- */
  function esc(v) { return String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function money(n, digits) {
    if (n === null || n === undefined || isNaN(n)) return "n/a";
    if (Math.abs(n) < 0.005) n = 0; // avoid "-$0" from floating point noise
    var a = Math.abs(n), s = n < 0 ? "-" : "";
    if (a < 1e3 && digits !== undefined) return s + "$" + a.toFixed(digits);
    if (a >= 1e6) return s + "$" + (a / 1e6).toFixed(digits === undefined ? 2 : digits) + "M";
    if (a >= 1e3) return s + "$" + (a / 1e3).toFixed(digits === undefined ? 0 : digits) + "K";
    return s + "$" + a.toFixed(0);
  }
  function dollars(n) {
    return n === null || n === undefined ? "n/a" : (n < 0 ? "-" : "") + "$" + Math.round(Math.abs(n)).toLocaleString("en-US");
  }
  function exact(n) {
    return n === null || n === undefined ? "n/a" : (n < 0 ? "-" : "") + "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function tick(n) {
    var a = Math.abs(n), s = n < 0 ? "-" : "";
    if (a >= 1e6) return s + "$" + parseFloat((a / 1e6).toFixed(2)) + "M";
    if (a >= 1e3) return s + "$" + parseFloat((a / 1e3).toFixed(1)) + "K";
    return s + "$" + a;
  }
  function pct(n, d) { return n === null || n === undefined ? "n/a" : (n * 100).toFixed(d === undefined ? 1 : d) + "%"; }
  function num(n) { return Number(n).toLocaleString("en-US"); }
  function monthLabel(m) { var d = new Date(m + "-01T00:00:00Z");
    return d.toLocaleString("en-US", { month: "short", year: "numeric", timeZone: "UTC" }); }
  function tag(kind, text) { return '<span class="tag tag-' + kind + '">' + esc(text) + "</span>"; }
  function delta(cur, prev, kind) {
    if (prev === null || prev === undefined || cur === null) return '<span class="delta">no prior period</span>';
    var d = cur - prev, up = d >= 0;
    var text = kind === "pct" ? (up ? "+" : "") + (d * 100).toFixed(1) + " pts" : (up ? "+" : "-") + money(Math.abs(d));
    return '<span class="delta ' + (up ? "up" : "down") + '">' + (up ? "&#9650; " : "&#9660; ") + text + " vs prior month</span>";
  }

  /* ---------- svg helpers ---------- */
  function scale(d0, d1, r0, r1) { return function (v) { return d1 === d0 ? r0 : r0 + (v - d0) * (r1 - r0) / (d1 - d0); }; }
  function niceTicks(lo, hi, count) {
    var span = hi - lo || 1, step = Math.pow(10, Math.floor(Math.log10(span / count)));
    var err = span / count / step;
    step *= err >= 5 ? 5 : err >= 2 ? 2 : 1;
    var ticks = [], t = Math.ceil(lo / step) * step;
    for (; t <= hi + 1e-9; t += step) ticks.push(t);
    return ticks;
  }
  function svg(w, h, label, inner) {
    return '<svg viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + esc(label) + '" class="chart">' + inner + "</svg>";
  }
  function axisY(ticks, y, x0, x1, fmt) {
    return ticks.map(function (t) {
      return '<line x1="' + x0 + '" x2="' + x1 + '" y1="' + y(t) + '" y2="' + y(t) + '" class="grid"/>' +
        '<text x="' + (x0 - 6) + '" y="' + (y(t) + 4) + '" class="axis" text-anchor="end">' + fmt(t) + "</text>";
    }).join("");
  }
  function axisX(labels, x, y, every) {
    return labels.map(function (l, i) {
      return i % every === 0 ? '<text x="' + x(i) + '" y="' + y + '" class="axis" text-anchor="middle">' + esc(l) + "</text>" : "";
    }).join("");
  }

  function lineChart(values, opts) {
    var W = 720, H = 240, L = 58, R = 16, T = 14, B = 30;
    var lo = Math.min(0, Math.min.apply(null, values)), hi = Math.max.apply(null, values);
    var ticks = niceTicks(lo, hi, 4);
    hi = Math.max(hi, ticks[ticks.length - 1]);
    var x = scale(0, values.length - 1, L, W - R), y = scale(lo, hi, H - B, T);
    var path = values.map(function (v, i) { return (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1); }).join("");
    var mark = opts.marker;
    var inner = axisY(ticks, y, L, W - R, opts.fmt) + axisX(opts.labels, x, H - 8, opts.every || 6) +
      '<path d="' + path + " L" + x(values.length - 1) + " " + y(lo) + " L" + x(0) + " " + y(lo) + 'Z" class="area"/>' +
      '<path d="' + path + '" class="line"/>';
    if (mark !== undefined && mark >= 0) {
      inner += '<line x1="' + x(mark) + '" x2="' + x(mark) + '" y1="' + T + '" y2="' + (H - B) + '" class="marker"/>' +
        '<circle cx="' + x(mark) + '" cy="' + y(values[mark]) + '" r="4.5" class="dot"/>';
    }
    values.forEach(function (v, i) {
      inner += '<circle cx="' + x(i) + '" cy="' + y(v) + '" r="9" class="hit"><title>' + esc(opts.labels[i]) + ": " + opts.fmt(v) + "</title></circle>";
    });
    return svg(W, H, opts.label, inner);
  }

  function waterfall(b) {
    var steps = [["Opening", b.opening, "total"], ["New", b.new, "new"], ["Expansion", b.expansion, "expansion"],
      ["Reactivation", b.reactivation, "reactivation"], ["Contraction", -b.contraction, "contraction"],
      ["Churn", -b.churned, "churned"], ["Closing", b.closing, "total"]];
    var W = 720, H = 260, L = 58, R = 16, T = 22, B = 36;
    var run = 0, bars = [];
    steps.forEach(function (s) {
      if (s[2] === "total") { bars.push({ label: s[0], from: 0, to: s[1], kind: "total", value: s[1] }); run = s[1]; }
      else { bars.push({ label: s[0], from: run, to: run + s[1], kind: s[2], value: s[1] }); run += s[1]; }
    });
    var hi = Math.max.apply(null, bars.map(function (b2) { return Math.max(b2.from, b2.to); }));
    var ticks = niceTicks(0, hi, 4); hi = Math.max(hi, ticks[ticks.length - 1]);
    var y = scale(0, hi, H - B, T), step = (W - L - R) / bars.length, bw = step * 0.62;
    var inner = axisY(ticks, y, L, W - R, tick);
    bars.forEach(function (bar, i) {
      var x0 = L + i * step + (step - bw) / 2, top = y(Math.max(bar.from, bar.to)), h = Math.max(1.5, Math.abs(y(bar.from) - y(bar.to)));
      var color = bar.kind === "total" ? "var(--c-total)" : SERIES[bar.kind];
      var sign = bar.kind === "total" ? "" : bar.value >= 0 ? "+" : "-";
      inner += '<rect x="' + x0 + '" y="' + top + '" width="' + bw + '" height="' + h + '" rx="2" fill="' + color + '"><title>' +
        bar.label + ": " + sign + money(Math.abs(bar.value)) + "</title></rect>" +
        '<text x="' + (x0 + bw / 2) + '" y="' + (top - 5) + '" class="barlabel" text-anchor="middle">' + sign + money(Math.abs(bar.value)) + "</text>" +
        '<text x="' + (x0 + bw / 2) + '" y="' + (H - 12) + '" class="axis" text-anchor="middle">' + bar.label + "</text>";
    });
    return svg(W, H, "MRR movement waterfall for " + monthLabel(b.month), inner);
  }

  function divergingBars(bridge, marker) {
    var W = 720, H = 250, L = 58, R = 16, T = 14, B = 30;
    var ups = bridge.map(function (b) { return b.new + b.expansion + b.reactivation; });
    var downs = bridge.map(function (b) { return b.contraction + b.churned; });
    var hi = Math.max.apply(null, ups.concat([1])), lo = -Math.max.apply(null, downs.concat([1]));
    var ticks = niceTicks(lo, hi, 5);
    lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]);
    var y = scale(lo, hi, H - B, T), step = (W - L - R) / bridge.length, bw = step * 0.7;
    var inner = axisY(ticks, y, L, W - R, tick);
    bridge.forEach(function (b, i) {
      var x0 = L + i * step + (step - bw) / 2, base = 0, parts = [["new", b.new], ["expansion", b.expansion], ["reactivation", b.reactivation]];
      parts.forEach(function (p) { if (p[1] > 0) { inner += '<rect x="' + x0 + '" y="' + y(base + p[1]) + '" width="' + bw + '" height="' + (y(base) - y(base + p[1])) + '" fill="' + SERIES[p[0]] + '"><title>' + monthLabel(b.month) + " " + p[0] + ": " + money(p[1]) + "</title></rect>"; base += p[1]; } });
      base = 0;
      [["contraction", b.contraction], ["churned", b.churned]].forEach(function (p) { if (p[1] > 0) { inner += '<rect x="' + x0 + '" y="' + y(base) + '" width="' + bw + '" height="' + (y(base - p[1]) - y(base)) + '" fill="' + SERIES[p[0]] + '"><title>' + monthLabel(b.month) + " " + p[0] + ": " + money(p[1]) + "</title></rect>"; base -= p[1]; } });
    });
    inner += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(0) + '" y2="' + y(0) + '" class="zero"/>';
    inner += axisX(bridge.map(function (b) { return b.month; }), function (i) { return L + i * step + step / 2; }, H - 8, 6);
    if (marker >= 0) inner += '<rect x="' + (L + marker * step) + '" y="' + T + '" width="' + step + '" height="' + (H - B - T) + '" class="band"/>';
    return svg(W, H, "Monthly MRR movement, additions above zero and losses below", inner);
  }

  function heatmap() {
    var cohorts = months.filter(function (m) { return P.cohorts.some(function (c) { return c.cohort === m; }); });
    var cell = {}; var maxAge = 0;
    P.cohorts.forEach(function (c) { cell[c.cohort + "|" + c.age] = c; if (c.age > maxAge) maxAge = c.age; });
    var W = 720, L = 62, T = 36, size = Math.min(17, (W - L - 12) / (maxAge + 1)), H = T + cohorts.length * 15 + 12;
    var inner = "";
    for (var a = 0; a <= maxAge; a += 6) inner += '<text x="' + (L + a * size + size / 2) + '" y="' + (T - 6) + '" class="axis" text-anchor="middle">' + a + "</text>";
    inner += '<text x="' + L + '" y="11" class="axis">Months since first MRR</text>';
    cohorts.forEach(function (co, r) {
      inner += '<text x="' + (L - 6) + '" y="' + (T + r * 15 + 11) + '" class="axis" text-anchor="end">' + co + "</text>";
      for (var age = 0; age <= maxAge; age++) {
        var c = cell[co + "|" + age]; if (!c) continue;
        var alpha = 0.12 + 0.88 * Math.max(0, Math.min(1, c.logo));
        inner += '<rect x="' + (L + age * size) + '" y="' + (T + r * 15) + '" width="' + (size - 1) + '" height="14" rx="1.5" fill="var(--c-heat)" fill-opacity="' + alpha.toFixed(3) + '"><title>' +
          co + " cohort, month " + age + ": " + pct(c.logo) + " of " + c.size + " customers active, " + pct(c.ndr) + " of starting MRR</title></rect>";
      }
    });
    return svg(W, H, "Cohort logo retention heatmap", inner);
  }

  function calibrationChart(bins) {
    var W = 340, H = 260, L = 44, R = 12, T = 14, B = 34;
    var hi = Math.max.apply(null, bins.map(function (b) { return Math.max(b.predicted, b.observed); })) * 1.15;
    var ticks = niceTicks(0, hi, 4); hi = Math.max(hi, ticks[ticks.length - 1]);
    var x = scale(0, hi, L, W - R), y = scale(0, hi, H - B, T);
    var inner = axisY(ticks, y, L, W - R, function (t) { return pct(t, 1); }) +
      '<line x1="' + x(0) + '" y1="' + y(0) + '" x2="' + x(hi) + '" y2="' + y(hi) + '" class="diag"/>';
    bins.forEach(function (b) { inner += '<circle cx="' + x(b.predicted) + '" cy="' + y(b.observed) + '" r="5" class="cal"><title>Bin ' + b.bin + ": predicted " + pct(b.predicted, 2) + ", observed " + pct(b.observed, 2) + " (" + b.n + " snapshots)</title></circle>"; });
    inner += '<text x="' + ((L + W - R) / 2) + '" y="' + (H - 6) + '" class="axis" text-anchor="middle">Mean predicted risk</text>';
    return svg(W, H, "Calibration: predicted versus observed 90-day churn rate by risk bin", inner);
  }

  /* ---------- controls ---------- */
  function options(list, selected, allLabel) {
    return '<option value="">' + allLabel + "</option>" + list.map(function (item, i) {
      return '<option value="' + i + '"' + (selected[0] === i ? " selected" : "") + ">" + esc(item) + "</option>"; }).join("");
  }
  function monthSelect() {
    return '<label>Month<select id="f-month">' + months.slice().reverse().map(function (m) {
      return '<option value="' + m + '"' + (m === state.month ? " selected" : "") + ">" + monthLabel(m) + "</option>"; }).join("") + "</select></label>";
  }
  function card(label, value, sub, extra) {
    return '<div class="card"><div class="card-label">' + label + '</div><div class="card-value">' + value + '</div><div class="card-sub">' + sub + "</div>" + (extra || "") + "</div>";
  }
  function legend(items) {
    return '<div class="legend">' + items.map(function (i) { return '<span><i style="background:' + i[1] + '"></i>' + i[0] + "</span>"; }).join("") + "</div>";
  }
  function filters() { return { segments: state.segments, plans: state.plans, products: state.products, customer: state.customer }; }
  function currentIndex() { return X.monthIndex(P, state.month); }

  /* ---------- pages ---------- */
  function pageExecutive() {
    var bridge = X.bridgeByMonth(P, {}), i = currentIndex(), b = bridge[i], prev = i ? bridge[i - 1] : null;
    var cash = X.cashFor(P, state.month), prevCash = i ? X.cashFor(P, months[i - 1]) : null;
    var exc = X.exceptionSummary(P, {}), open = X.openInvoiceSummary(P);
    var totalInvoiced = P.cash.reduce(function (s, c) { return s + c.invoiced; }, 0);
    var cc = X.contractConflictProfile(P), edge = P.meta.cancellation_boundary;
    var boundaryNote = state.month === P.meta.latest_month ?
      " " + num(edge.last_day_cancellations) + " of " + num(edge.month_cancellations) + " cancellations this month are dated " + edge.last_day + ", the last day of the data window, against a typical " + num(Math.round(edge.typical_month_cancellations)) + " a month." : "";
    var decline = b.netNew < 0;
    var lossShare = decline && (b.churned + b.contraction) ? b.churned / (b.churned + b.contraction) : null;
    var html = '<div class="controls">' + monthSelect() + "</div>" +
      '<div class="cards">' +
      card("MRR", money(b.closing), delta(b.closing, prev && prev.closing)) +
      card("ARR", money(b.arr), delta(b.arr, prev && prev.arr)) +
      card("Net revenue retention", pct(b.nrr), delta(b.nrr, prev && prev.nrr, "pct")) +
      card("Gross revenue retention", pct(b.grr), delta(b.grr, prev && prev.grr, "pct")) +
      card("Net new MRR", money(b.netNew), delta(b.netNew, prev && prev.netNew)) +
      card("Cash collected", money(cash.net_cash), delta(cash.net_cash, prevCash && prevCash.net_cash)) +
      card("Exception exposure", money(exc.exposure), esc(num(exc.invoices)) + " flagged invoices, all periods") +
      "</div>" +
      '<div class="panel wide"><h2>MRR, ' + months.length + " months " + tag("fact", "Observed dataset fact") + "</h2>" +
      lineChart(bridge.map(function (x) { return x.closing; }), { labels: months, fmt: tick, marker: i, label: "Closing MRR by month" }) + "</div>" +
      '<div class="panel wide"><h2>' + monthLabel(state.month) + " MRR movement " + tag("fact", "Observed dataset fact") + "</h2>" + waterfall(b) + "</div>" +
      '<div class="panel wide"><h2>What the data says</h2><div class="callouts">' +
      '<div class="callout"><h3>Churn drives the drop; check the dates first</h3><p>' + monthLabel(state.month) + ": churned MRR of " + money(b.churned) + " against " + money(b.new) + " of new MRR gives net new MRR of " + money(b.netNew) + "." +
      (lossShare !== null ? " Churn is " + pct(lossShare, 0) + " of all MRR lost." : "") + boundaryNote + "</p>" + tag("rec", "Recommendation") + " Customer Success and Data Engineering: confirm how cancellation dates are set at the end of the extract window before reading this as customer behavior.</div>" +
      '<div class="callout"><h3>Failed payments hold back cash</h3><p>' + num(open.invoices) + " invoices carry a failed payment attempt with " + money(open.exposure) + " unpaid, " + pct(open.exposure / totalInvoiced, 1) + " of all billed amounts.</p>" + tag("rec", "Recommendation") + " Finance Ops: work the list by exposed amount and measure cash recovered within 14 days.</div>" +
      '<div class="callout"><h3>Contract exceptions are a dating convention</h3><p>' + num(cc.beforeStart) + " of " + num(cc.records) + " contract-date exceptions are invoices dated before the contract start; " + num(cc.sameMonthAsStart) + " fall in the contract's start month and " + num(cc.afterEnd) + " fall after its end. That points to first-of-month invoice dating, not lifecycle errors. " + money(exc.exposure) + " of billing is flagged.</p>" + tag("rec", "Recommendation") + " RevOps: align invoice dating with contract start, then re-run the rule.</div>" +
      "</div></div>";
    return html;
  }

  function pageRevenue() {
    var f = filters(), bridge = X.bridgeByMonth(P, f), i = currentIndex(), b = bridge[i], prev = i ? bridge[i - 1] : null;
    var mv = P.movement;
    var dimRows = breakdown(state.dimension, i);
    var accounts = accountRows(i);
    var scope = [];
    if (state.segments.length) scope.push(mv.segments[state.segments[0]]);
    if (state.plans.length) scope.push(mv.plans[state.plans[0]]);
    if (state.products.length) scope.push(mv.products[state.products[0]]);
    if (state.customer !== null) scope.push(mv.customers[state.customer][1] + " (" + mv.customers[state.customer][0] + ")");
    var html = '<div class="controls">' + monthSelect() +
      '<label>Segment<select id="f-segment">' + options(mv.segments, state.segments, "All segments") + "</select></label>" +
      '<label>Plan<select id="f-plan">' + options(mv.plans, state.plans, "All plans") + "</select></label>" +
      '<label>Product<select id="f-product">' + options(mv.products, state.products, "All products") + "</select></label>" +
      '<button id="f-reset" type="button">Reset filters</button></div>' +
      '<p class="scope">Showing ' + (scope.length ? esc(scope.join(", ")) : "all customers") + " for " + monthLabel(state.month) + ". " + tag("fact", "Observed dataset fact") + "</p>";
    if (b.opening === 0 && b.closing === 0) return html + '<div class="empty">No MRR for this filter combination in ' + monthLabel(state.month) + ". Clear a filter to continue.</div>";
    html += '<div class="cards">' +
      card("MRR", money(b.closing), delta(b.closing, prev && prev.closing)) +
      card("Net revenue retention", pct(b.nrr), delta(b.nrr, prev && prev.nrr, "pct")) +
      card("Gross revenue retention", pct(b.grr), delta(b.grr, prev && prev.grr, "pct")) +
      card("Net new MRR", money(b.netNew), delta(b.netNew, prev && prev.netNew)) +
      card("Bridge variance", money(b.variance, 2), "opening + movements - closing") + "</div>" +
      '<div class="panel wide"><h2>New, expansion, contraction and churn by month</h2>' + divergingBars(bridge, i) +
      legend([["New", SERIES.new], ["Expansion", SERIES.expansion], ["Reactivation", SERIES.reactivation], ["Contraction", SERIES.contraction], ["Churn", SERIES.churned]]) + "</div>" +
      '<div class="panel wide"><h2>Slice by ' + '<span class="seg">' + ["segment", "plan", "product"].map(function (d) {
        return '<button type="button" class="pill' + (state.dimension === d ? " on" : "") + '" data-dim="' + d + '">' + d + "</button>"; }).join("") + "</span></h2>" +
      table(["", "MRR", "Churned", "Net new", "NRR", "GRR"], dimRows.map(function (r) {
        return ['<button type="button" class="link" data-slice="' + esc(state.dimension + ":" + r.index) + '">' + esc(r.name) + "</button>", money(r.closing), money(r.churned), money(r.netNew), pct(r.nrr), pct(r.grr)];
      }), [1, 2, 3, 4, 5]) + "</div>" +
      '<div class="panel wide"><h2>Cohort logo retention ' + tag("fact", "Observed dataset fact") + "</h2>" + heatmap() +
      '<p class="note">Cohort is the first month a customer holds MRR. Darker means more of the cohort is still active. Source: mart_cohort_retention.</p></div>' +
      '<div class="panel wide"><h2>Account drill-through, ' + monthLabel(state.month) + '</h2><p class="note">Largest absolute MRR change first. Select an account to filter the whole page to it.</p>' +
      table(["Account", "Segment", "Opening", "Closing", "Change", "Movement"], accounts.map(function (a) {
        return ['<button type="button" class="link" data-customer="' + a.customer + '">' + esc(a.name) + "</button>", esc(a.segment), dollars(a.opening), dollars(a.closing), dollars(a.change), esc(a.movement)];
      }), [2, 3, 4]) + "</div>";
    return html;
  }

  function breakdown(dim, mi) {
    var mv = P.movement, names = mv[dim + "s"];
    var f = filters(); // each row overrides its own dimension filter below
    var out = names.map(function (name, index) {
      var ff = { segments: f.segments, plans: f.plans, products: f.products, customer: f.customer };
      ff[dim + "s"] = [index];
      var b = X.bridgeByMonth(P, ff)[mi];
      return { name: name, index: index, closing: b.closing, churned: b.churned, netNew: b.netNew, nrr: b.nrr, grr: b.grr };
    });
    return out.sort(function (a, c) { return c.closing - a.closing; });
  }

  function accountRows(mi) {
    var mv = P.movement, f = filters(), byCustomer = {};
    mv.rows.forEach(function (r) {
      if (r[0] !== mi) return;
      if ((f.segments.length && f.segments.indexOf(r[1]) < 0) || (f.plans.length && f.plans.indexOf(r[2]) < 0) ||
        (f.products.length && f.products.indexOf(r[3]) < 0) || (f.customer !== null && f.customer !== r[4])) return;
      var a = byCustomer[r[4]] || (byCustomer[r[4]] = { customer: r[4], opening: 0, closing: 0, movements: {} });
      a.opening += r[5]; a.closing += r[6];
      var types = ["new", "expansion", "contraction", "churned", "reactivation"];
      types.forEach(function (t, k) { if (r[7 + k] > 0) a.movements[t] = true; });
    });
    return Object.keys(byCustomer).map(function (k) {
      var a = byCustomer[k], c = mv.customers[a.customer];
      return { customer: a.customer, name: c[1], segment: c[2], opening: a.opening, closing: a.closing, change: a.closing - a.opening,
        movement: Object.keys(a.movements).join(", ") || "no change" };
    }).sort(function (a, c) { return Math.abs(c.change) - Math.abs(a.change); }).slice(0, 10);
  }

  function table(headers, rows, numeric) {
    numeric = numeric || [];
    return '<div class="table-wrap"><table><thead><tr>' + headers.map(function (h, i) { return "<th" + (numeric.indexOf(i) >= 0 ? ' class="num"' : "") + ' scope="col">' + esc(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + rows.map(function (r) { return "<tr>" + r.map(function (c, i) { return "<td" + (numeric.indexOf(i) >= 0 ? ' class="num"' : "") + ">" + c + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>";
  }

  function pageRisk() {
    var s = X.riskSummary(P, state.threshold), queue = X.riskQueue(P, state.threshold), drivers = X.driverTable(P, state.threshold);
    var cal = X.calibration(P, 10), lift = X.liftDeciles(P), mm = P.meta.model_metrics, e = P.meta.economics;
    var html = '<div class="controls"><label class="range">Risk threshold <output id="thr-out">' + pct(state.threshold, 0) + '</output>' +
      '<input id="f-threshold" type="range" min="0.01" max="0.20" step="0.01" value="' + state.threshold + '" aria-label="Risk threshold"></label>' +
      '<span class="note">Cost-selected threshold is ' + pct(P.meta.risk_threshold, 0) + ". Scored: held-out future snapshots after " + esc(P.meta.split.calibration_end) + ".</span></div>" +
      '<div class="cards">' +
      card("Snapshots at or above threshold", num(s.flagged), "of " + num(s.scored) + " scored " + tag("model", "Model estimate")) +
      card("Exposed MRR", money(s.exposedMrr), "sum of MRR on flagged snapshots") +
      card("Precision", pct(s.precision), num(s.truePositives) + " churned of " + num(s.flagged) + " flagged") +
      card("Recall", pct(s.recall), "of " + num(s.positives) + " churned snapshots") +
      card("Lift over base rate", s.lift === null ? "n/a" : s.lift.toFixed(2) + "x", "base rate " + pct(s.prevalence, 2)) +
      card("Holdout net value", money(s.netValue), "scenario economics " + tag("scenario", "Scenario")) + "</div>" +
      '<div class="panel wide"><h2>Prioritized account queue ' + tag("model", "Model estimate") + "</h2>" +
      '<p class="note">Latest scored snapshot per account, ranked by risk times MRR. ' + num(queue.length) + " accounts at this threshold; top 15 shown.</p>" +
      (queue.length ? table(["Account", "As of", "Risk", "MRR", "MRR at risk", "Usage change", "Adoption", "Tickets", "Failed pmts", "Observed churn"],
        queue.slice(0, 15).map(function (q) { return [esc(q.account), esc(q.as_of), pct(q.risk, 1), dollars(q.mrr), dollars(q.mrrAtRisk), pct(q.usage_change, 0), pct(q.adoption, 0), q.tickets, q.failed_payments, q.churned ? "yes" : "no"]; }),
        [2, 3, 4, 5, 6, 7, 8]) : '<div class="empty">No snapshots at this threshold. Lower the threshold.</div>') + "</div>" +
      '<div class="panel"><h2>Why they are flagged ' + tag("fact", "Observed dataset fact") + "</h2>" +
      table(["Driver", "Flagged", "Not flagged"], drivers.map(function (d) {
        var isPct = d.key === "usage_change" || d.key === "adoption";
        var fmt = function (v) { return v === null ? "n/a" : isPct ? pct(v, 1) : v.toFixed(2); };
        return [esc(d.label), fmt(d.flagged), fmt(d.other)]; }), [1, 2]) + "</div>" +
      '<div class="panel"><h2>Calibration ' + tag("model", "Model estimate") + "</h2>" + calibrationChart(cal) +
      '<p class="note">Points on the diagonal mean predicted risk matches the observed churn rate. Ten equal-count bins.</p></div>' +
      '<div class="panel"><h2>Validation ' + tag("model", "Model estimate") + "</h2>" +
      table(["Metric", "Value"], [["ROC-AUC", mm.roc_auc.toFixed(3)], ["PR-AUC", mm.pr_auc.toFixed(3)], ["Brier score", mm.brier_score.toFixed(4)],
        ["Base rate", pct(s.prevalence, 2)], ["Train end", esc(P.meta.split.train_end)], ["Calibration end", esc(P.meta.split.calibration_end)]], [1]) +
      '<p class="note">Signal is modest, so PR-AUC is judged against the base rate. A calibrated logistic baseline is the shipped model.</p></div>' +
      '<div class="panel"><h2>Lift by risk decile ' + tag("model", "Model estimate") + "</h2>" +
      table(["Decile", "Snapshots", "Churned", "Rate", "Lift", "Captured"], lift.map(function (d) { return [d.decile, num(d.n), d.churners, pct(d.rate, 2), d.lift.toFixed(2) + "x", pct(d.cumulativeCapture, 0)]; }), [1, 2, 3, 4, 5]) + "</div>" +
      '<div class="panel"><h2>Threshold economics ' + tag("scenario", "Scenario") + "</h2>" +
      "<p>Contact cost " + money(e.contact_cost, 0) + " per flagged account; retained margin " + money(e.retained_margin, 0) + " if a save succeeds; success rate " + pct(e.success_rate, 0) + ". A true positive is worth " + money(e.retained_margin * e.success_rate - e.contact_cost, 0) + " and a false positive costs " + money(e.contact_cost, 0) + ". The cost-selected threshold maximizes that net value on the calibration period, and these figures apply it to the held-out period. They are simulated assumptions, not observed results.</p></div>";
    return html;
  }

  function pageFinance() {
    var i = currentIndex(), cash = X.cashFor(P, state.month), open = X.openInvoiceSummary(P);
    var all = P.cash.reduce(function (t, c) { ["invoiced", "successful_payments", "failed_exposure", "refunded", "net_cash", "recognized", "deferred"].forEach(function (k) { t[k] = (t[k] || 0) + c[k]; }); return t; }, {});
    var rules = Array.from(new Set(P.exceptions.map(function (e) { return e.exception_type; }))).sort();
    var sevs = Array.from(new Set(P.exceptions.map(function (e) { return e.severity; }))).sort();
    var list = X.exceptionList(P, { severity: state.severity, rule: state.rule });
    var q = state.query.trim().toLowerCase();
    if (q) list = list.filter(function (e) { return (e.invoice_id + " " + e.customer_id + " " + e.segment).toLowerCase().indexOf(q) >= 0; });
    var summary = X.exceptionSummary(P, { severity: state.severity, rule: state.rule });
    var pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE)); if (state.page >= pages) state.page = pages - 1;
    var slice = list.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
    function tie(label, a) {
      var v = a.invoiced - a.successful_payments - a.failed_exposure, ties = Math.abs(v) < 0.005;
      return [label, exact(a.invoiced), exact(a.successful_payments), exact(a.failed_exposure), exact(a.refunded), exact(a.net_cash), exact(a.recognized), exact(a.deferred),
        '<span class="' + (ties ? "ok" : "bad") + '">' + exact(ties ? 0 : v) + (ties ? " ties" : " breaks") + "</span>"];
    }
    var html = '<div class="controls">' + monthSelect() + "</div>" +
      '<div class="cards">' +
      card("Invoiced, " + monthLabel(state.month), money(cash.invoiced), num(cash.invoices) + " invoices") +
      card("Cash collected", money(cash.net_cash), "successful payments less refunds") +
      card("Failed-payment exposure", money(open.exposure), num(open.invoices) + " invoices, all periods") +
      card("Exception invoices", num(X.exceptionSummary(P, {}).invoices), money(X.exceptionSummary(P, {}).exposure) + " billed amount") + "</div>" +
      '<div class="panel wide"><h2>Invoice, payment, refund and revenue tie-out ' + tag("fact", "Observed dataset fact") + "</h2>" +
      table(["Scope", "Invoiced", "Paid", "Unpaid (failed)", "Refunded", "Net cash", "Recognized", "Deferred", "Invoiced - paid - unpaid"],
        [tie(monthLabel(state.month), cash), tie("All periods", all)], [1, 2, 3, 4, 5, 6, 7, 8]) +
      '<p class="note">Invoices should equal successful payments plus unpaid exposure, and recognized plus deferred revenue should equal what was invoiced. Invoiced less recognized less deferred is ' + exact(all.invoiced - all.recognized - all.deferred) + " across all periods.</p></div>" +
      '<div class="panel wide"><h2>Failed-payment exposure by month</h2>' + lineChart(P.cash.map(function (c) { return c.failed_exposure; }), { labels: months, fmt: tick, marker: i, label: "Failed payment exposure by invoice month" }) + "</div>" +
      '<div class="panel wide"><h2>Exception queue ' + tag("fact", "Observed dataset fact") + "</h2>" +
      '<div class="controls"><label>Rule<select id="f-rule"><option value="all">All rules</option>' + rules.map(function (r) { return '<option value="' + esc(r) + '"' + (state.rule === r ? " selected" : "") + ">" + esc(r.replace(/_/g, " ")) + "</option>"; }).join("") + "</select></label>" +
      '<label>Severity<select id="f-severity"><option value="all">All severities</option>' + sevs.map(function (r) { return '<option value="' + esc(r) + '"' + (state.severity === r ? " selected" : "") + ">" + esc(r) + "</option>"; }).join("") + "</select></label>" +
      '<label>Search<input id="f-query" type="search" placeholder="Invoice or customer" value="' + esc(state.query) + '"></label></div>' +
      '<p class="note">' + num(list.length) + " records" + (q ? " match the search" : "") + "; " + num(summary.invoices) + " invoices and " + money(summary.exposure) + " billed amount before search. Select an invoice to see its source record.</p>" +
      (slice.length ? table(["Invoice", "Rule", "Severity", "Date", "Customer", "Segment", "Billed"], slice.map(function (e) {
        return ['<button type="button" class="link" data-invoice="' + esc(e.invoice_id) + "|" + esc(e.exception_type) + '">' + esc(e.invoice_id) + "</button>", esc(e.exception_type.replace(/_/g, " ")), esc(e.severity), esc(e.invoice_date), esc(e.customer_id), esc(e.segment), dollars(e.total_amount)]; }), [6]) : '<div class="empty">No exceptions for this combination of filters.</div>') +
      '<div class="pager"><button type="button" id="pg-prev"' + (state.page === 0 ? " disabled" : "") + '>Previous</button><span>Page ' + (state.page + 1) + " of " + pages + '</span><button type="button" id="pg-next"' + (state.page >= pages - 1 ? " disabled" : "") + ">Next</button></div></div>" +
      '<div class="panel wide"><h2>Failed-payment worklist ' + tag("rec", "Action queue") + "</h2><p class=\"note\">Largest unpaid invoices first, 10 of " + num(open.invoices) + ".</p>" +
      table(["Invoice", "Date", "Customer", "Segment", "Unpaid"], P.open_invoices.slice(0, 10).map(function (o) { return [esc(o.invoice_id), esc(o.invoice_date), esc(o.customer_id), esc(o.segment), dollars(o.failed_payment_exposure)]; }), [4]) + "</div>";
    if (state.invoice) {
      var parts = state.invoice.split("|");
      var rec = P.exceptions.filter(function (e) { return e.invoice_id === parts[0] && e.exception_type === parts[1]; })[0];
      if (rec) html += '<div class="drawer" role="dialog" aria-modal="true" aria-label="Source record for ' + esc(rec.invoice_id) + '"><div class="drawer-body"><button type="button" id="drawer-close" class="close" aria-label="Close source record">Close</button>' +
        "<h2>Source record " + esc(rec.invoice_id) + "</h2><p>" + esc(rec.details) + "</p><dl>" +
        [["Rule", rec.exception_type], ["Severity", rec.severity], ["Customer", rec.customer_id + " (" + rec.segment + ")"], ["Subscription", rec.subscription_id], ["Invoice date", rec.invoice_date],
          ["Contract window", (rec.contract_start || "n/a") + " to " + (rec.contract_end || "open ended")], ["Status", rec.status], ["Currency", rec.currency], ["Subtotal", exact(rec.subtotal)], ["Discount", exact(rec.discount_amount)],
          ["Tax", exact(rec.tax_amount)], ["Total", exact(rec.total_amount)], ["Successful payments", exact(rec.successful_payments)], ["Failed payment exposure", exact(rec.failed_payment_exposure)],
          ["Refunded", exact(rec.refunded_amount)], ["Recognized", exact(rec.recognized_amount)], ["Deferred", exact(rec.deferred_amount)]].map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd>"; }).join("") +
        "</dl></div></div>";
    }
    return html;
  }

  /* ---------- shell ---------- */
  function render() {
    var page = { executive: pageExecutive, revenue: pageRevenue, risk: pageRisk, finance: pageFinance }[state.tab]();
    document.getElementById("view").innerHTML = page;
    document.querySelectorAll("[data-tab]").forEach(function (t) {
      var on = t.getAttribute("data-tab") === state.tab; t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1;
    });
    document.getElementById("view").setAttribute("aria-labelledby", "tab-" + state.tab);
    var closer = document.getElementById("drawer-close");
    if (closer) closer.focus();
    document.getElementById("status").textContent = "Data as of " + monthLabel(P.meta.latest_month) + ". Synthetic dataset, no real customers.";
  }
  function set(patch, keepFocus) {
    Object.keys(patch).forEach(function (k) { state[k] = patch[k]; });
    var active = document.activeElement && document.activeElement.id;
    render();
    if (keepFocus && active) { var el = document.getElementById(active); if (el) { el.focus(); if (el.setSelectionRange && el.type === "search") { var n = el.value.length; el.setSelectionRange(n, n); } } }
  }
  function pick(v) { return v === "" ? [] : [parseInt(v, 10)]; }

  document.addEventListener("change", function (ev) {
    var t = ev.target;
    if (t.id === "f-month") set({ month: t.value }, true);
    else if (t.id === "f-segment") set({ segments: pick(t.value), customer: null }, true);
    else if (t.id === "f-plan") set({ plans: pick(t.value), customer: null }, true);
    else if (t.id === "f-product") set({ products: pick(t.value), customer: null }, true);
    else if (t.id === "f-rule") set({ rule: t.value, page: 0 }, true);
    else if (t.id === "f-severity") set({ severity: t.value, page: 0 }, true);
  });
  document.addEventListener("input", function (ev) {
    var t = ev.target;
    if (t.id === "f-threshold") set({ threshold: parseFloat(t.value) }, true);
    else if (t.id === "f-query") set({ query: t.value, page: 0 }, true);
  });
  document.addEventListener("click", function (ev) {
    var t = ev.target.closest("button, [data-tab]"); if (!t) return;
    if (t.hasAttribute("data-tab")) return set({ tab: t.getAttribute("data-tab"), invoice: null });
    if (t.id === "f-reset") return set({ segments: [], plans: [], products: [], customer: null, month: P.meta.latest_month });
    if (t.hasAttribute("data-dim")) return set({ dimension: t.getAttribute("data-dim") });
    if (t.hasAttribute("data-slice")) { var s = t.getAttribute("data-slice").split(":"), idx = [parseInt(s[1], 10)]; var patch = { customer: null }; patch[s[0] + "s"] = idx; return set(patch); }
    if (t.hasAttribute("data-customer")) { var c = parseInt(t.getAttribute("data-customer"), 10); return set({ customer: c, segments: [], plans: [], products: [] }); }
    if (t.hasAttribute("data-invoice")) return set({ invoice: t.getAttribute("data-invoice") });
    if (t.id === "drawer-close") return set({ invoice: null });
    if (t.id === "pg-prev") return set({ page: state.page - 1 });
    if (t.id === "pg-next") return set({ page: state.page + 1 });
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && state.invoice) return set({ invoice: null });
    var t = ev.target;
    if (t.hasAttribute && t.hasAttribute("data-tab") && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) {
      var i = TABS.findIndex(function (x) { return x[0] === state.tab; }), n = (i + (ev.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
      set({ tab: TABS[n][0], invoice: null }); document.getElementById("tab-" + TABS[n][0]).focus();
    }
  });

  document.getElementById("tabs").innerHTML = TABS.map(function (t) { return '<button type="button" role="tab" id="tab-' + t[0] + '" data-tab="' + t[0] + '" aria-selected="false">' + t[1] + "</button>"; }).join("");
  var hash = (location.hash || "").replace("#", ""); if (TABS.some(function (t) { return t[0] === hash; })) state.tab = hash;
  window.__state = state; window.__set = set;
  render();
})();
