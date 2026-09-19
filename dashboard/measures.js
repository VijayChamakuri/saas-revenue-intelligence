/* Pure measure library for the SaaS Revenue Intelligence dashboard.
 *
 * Runs unchanged in the browser (inlined into index.html) and in Node
 * (src/dashboard/validate.py evaluates it against warehouse SQL).
 * No DOM access, no globals other than the exported object.
 */
(function (root) {
  "use strict";

  var M = {}; // movement column indexes
  ["month", "segment", "plan", "product", "customer", "opening", "closing", "new",
    "expansion", "contraction", "churned", "reactivation"].forEach(function (name, i) { M[name] = i; });

  var COMPONENTS = ["opening", "closing", "new", "expansion", "contraction", "churned", "reactivation"];

  function round2(value) { return Math.round(value * 100) / 100; }

  function matches(list, value) { return !list || list.length === 0 || list.indexOf(value) !== -1; }

  /* filters: {segments:[idx], plans:[idx], products:[idx], customer:idx|null} */
  function movementPasses(row, f) {
    return matches(f.segments, row[M.segment]) && matches(f.plans, row[M.plan]) &&
      matches(f.products, row[M.product]) &&
      (f.customer === null || f.customer === undefined || f.customer === row[M.customer]);
  }

  /* Sum movement components per month for the rows passing the filters. */
  function bridgeByMonth(P, f) {
    var n = P.meta.months.length;
    var out = [];
    for (var i = 0; i < n; i++) {
      out.push({ month: P.meta.months[i], opening: 0, closing: 0, new: 0, expansion: 0,
        contraction: 0, churned: 0, reactivation: 0 });
    }
    var rows = P.movement.rows;
    for (var r = 0; r < rows.length; r++) {
      var row = rows[r];
      if (!movementPasses(row, f || {})) continue;
      var bucket = out[row[M.month]];
      for (var c = 0; c < COMPONENTS.length; c++) bucket[COMPONENTS[c]] += row[M[COMPONENTS[c]]];
    }
    out.forEach(function (b) {
      COMPONENTS.forEach(function (k) { b[k] = round2(b[k]); });
      b.netNew = round2(b.new + b.expansion + b.reactivation - b.contraction - b.churned);
      b.arr = round2(b.closing * 12);
      b.nrr = b.opening > 0 ?
        (b.opening + b.expansion + b.reactivation - b.contraction - b.churned) / b.opening : null;
      b.grr = b.opening > 0 ? (b.opening - b.contraction - b.churned) / b.opening : null;
      b.variance = round2(b.opening + b.new + b.expansion + b.reactivation - b.contraction -
        b.churned - b.closing);
    });
    return out;
  }

  function monthIndex(P, month) {
    var i = P.meta.months.indexOf(month);
    if (i < 0) throw new Error("Unknown month " + month);
    return i;
  }

  function cashFor(P, month) {
    var row = P.cash.filter(function (c) { return c.ym === month; })[0];
    if (!row) throw new Error("No cash row for " + month);
    return row;
  }

  /* Exceptions: filter {severity, rule} ("all" or a value). */
  function exceptionList(P, f) {
    return P.exceptions.filter(function (e) {
      return (!f || !f.severity || f.severity === "all" || e.severity === f.severity) &&
        (!f || !f.rule || f.rule === "all" || e.exception_type === f.rule);
    });
  }

  /* Exposure counts each flagged invoice once, at its billed total. */
  function exceptionSummary(P, f) {
    var list = exceptionList(P, f);
    var seen = {};
    var exposure = 0;
    list.forEach(function (e) {
      if (seen[e.invoice_id]) return;
      seen[e.invoice_id] = true;
      exposure += e.total_amount || 0;
    });
    return { records: list.length, invoices: Object.keys(seen).length, exposure: round2(exposure) };
  }

  /* Where contract_date_conflict exceptions fall relative to the contract window. */
  function contractConflictProfile(P) {
    var out = { records: 0, beforeStart: 0, sameMonthAsStart: 0, afterEnd: 0 };
    P.exceptions.forEach(function (e) {
      if (e.exception_type !== "contract_date_conflict") return;
      out.records++;
      if (e.contract_start && e.invoice_date < e.contract_start) {
        out.beforeStart++;
        if (e.invoice_date.slice(0, 7) === e.contract_start.slice(0, 7)) out.sameMonthAsStart++;
      } else if (e.contract_end && e.invoice_date > e.contract_end) {
        out.afterEnd++;
      }
    });
    return out;
  }

  function openInvoiceSummary(P) {
    var exposure = 0;
    P.open_invoices.forEach(function (o) { exposure += o.failed_payment_exposure; });
    return { invoices: P.open_invoices.length, exposure: round2(exposure) };
  }

  /* ---------------- risk ---------------- */

  var R = {};
  ["account", "as_of", "risk", "churned", "mrr", "usage_change", "adoption", "tickets",
    "failed_payments", "recency_days", "plan_type", "size"].forEach(function (name, i) { R[name] = i; });

  function riskSummary(P, threshold) {
    var e = P.meta.economics;
    var rows = P.risk.rows;
    var flagged = 0, tp = 0, positives = 0, exposed = 0, expectedRisk = 0;
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var isPositive = row[R.churned] === 1;
      if (isPositive) positives++;
      if (row[R.risk] >= threshold) {
        flagged++;
        exposed += row[R.mrr];
        expectedRisk += row[R.risk] * row[R.mrr];
        if (isPositive) tp++;
      }
    }
    var fp = flagged - tp;
    var tpValue = e.retained_margin * e.success_rate - e.contact_cost;
    return {
      scored: rows.length, flagged: flagged, truePositives: tp, falsePositives: fp,
      positives: positives,
      prevalence: rows.length ? positives / rows.length : null,
      precision: flagged ? tp / flagged : null,
      recall: positives ? tp / positives : null,
      lift: flagged && positives ? (tp / flagged) / (positives / rows.length) : null,
      exposedMrr: round2(exposed),
      expectedMrrAtRisk: round2(expectedRisk),
      netValue: round2(tp * tpValue - fp * e.contact_cost)
    };
  }

  /* Latest snapshot per account at or above the threshold, ranked by risk x MRR. */
  function riskQueue(P, threshold) {
    var latest = {};
    P.risk.rows.forEach(function (row) {
      var current = latest[row[R.account]];
      if (!current || row[R.as_of] > current[R.as_of]) latest[row[R.account]] = row;
    });
    return Object.keys(latest).map(function (k) { return latest[k]; })
      .filter(function (row) { return row[R.risk] >= threshold; })
      .map(function (row) {
        return { account: row[R.account], as_of: row[R.as_of], risk: row[R.risk], mrr: row[R.mrr],
          mrrAtRisk: round2(row[R.risk] * row[R.mrr]), usage_change: row[R.usage_change],
          adoption: row[R.adoption], tickets: row[R.tickets],
          failed_payments: row[R.failed_payments], recency_days: row[R.recency_days],
          plan_type: row[R.plan_type], size: row[R.size], churned: row[R.churned] };
      })
      .sort(function (a, b) { return b.mrrAtRisk - a.mrrAtRisk || (a.account < b.account ? -1 : 1); });
  }

  /* Average of each driver for flagged versus not-flagged scored snapshots. */
  function driverTable(P, threshold) {
    var drivers = [["usage_change", "Usage change, 30 days"], ["adoption", "Feature adoption rate"],
      ["tickets", "Support tickets, 90 days"], ["failed_payments", "Failed payments, 90 days"],
      ["recency_days", "Days since last engagement"]];
    return drivers.map(function (d) {
      var sums = [0, 0], counts = [0, 0];
      P.risk.rows.forEach(function (row) {
        var value = row[R[d[0]]];
        if (value === null || value === undefined) return; // missing observations are not zeros
        var g = row[R.risk] >= threshold ? 0 : 1;
        sums[g] += value;
        counts[g] += 1;
      });
      return { key: d[0], label: d[1], flagged: counts[0] ? sums[0] / counts[0] : null,
        other: counts[1] ? sums[1] / counts[1] : null };
    });
  }

  /* Ten equal-count risk bins: mean predicted risk versus observed churn rate. */
  function calibration(P, bins) {
    bins = bins || 10;
    var sorted = P.risk.rows.slice().sort(function (a, b) { return a[R.risk] - b[R.risk]; });
    var out = [];
    for (var b = 0; b < bins; b++) {
      var lo = Math.floor(b * sorted.length / bins), hi = Math.floor((b + 1) * sorted.length / bins);
      var chunk = sorted.slice(lo, hi);
      if (!chunk.length) continue;
      var predicted = 0, observed = 0;
      chunk.forEach(function (row) { predicted += row[R.risk]; observed += row[R.churned]; });
      out.push({ bin: b + 1, n: chunk.length, predicted: predicted / chunk.length,
        observed: observed / chunk.length, churners: observed });
    }
    return out;
  }

  /* Lift by risk decile, highest decile first. */
  function liftDeciles(P) {
    var cal = calibration(P, 10).slice().reverse();
    var total = 0, positives = 0;
    P.risk.rows.forEach(function (row) { total++; positives += row[R.churned]; });
    var prevalence = positives / total;
    var cumulative = 0;
    return cal.map(function (c, i) {
      cumulative += c.churners;
      return { decile: i + 1, n: c.n, churners: c.churners, rate: c.observed,
        lift: c.observed / prevalence, cumulativeCapture: cumulative / positives };
    });
  }

  /* ---------------- evidence dispatcher ---------------- */

  /* Translate dimension names (segment, plan, product, customer id) to payload indexes. */
  function resolve(P, f) {
    function index(list, value, label) {
      var i = list.indexOf(value);
      if (i < 0) throw new Error("Unknown " + label + " " + value);
      return [i];
    }
    var out = Object.assign({}, f);
    if (f.segment) out.segments = index(P.movement.segments, f.segment, "segment");
    if (f.plan) out.plans = index(P.movement.plans, f.plan, "plan");
    if (f.product) out.products = index(P.movement.products, f.product, "product");
    if (f.customerId) {
      var ids = P.movement.customers.map(function (c) { return c[0]; });
      var at = ids.indexOf(f.customerId);
      if (at < 0) throw new Error("Unknown customer " + f.customerId);
      out.customer = at;
    }
    return out;
  }

  /* Evaluate a named measure under a filter state. Used by validate.py. */
  function evaluate(P, name, filter) {
    var f = resolve(P, filter || {});
    var month = f.month;
    var bridge, b;
    switch (name) {
      case "closing_mrr": case "arr": case "net_new_mrr": case "new_mrr": case "expansion_mrr":
      case "contraction_mrr": case "churned_mrr": case "reactivation_mrr": case "opening_mrr":
      case "nrr": case "grr": case "bridge_variance":
        bridge = bridgeByMonth(P, f);
        b = bridge[monthIndex(P, month)];
        return ({ closing_mrr: b.closing, arr: b.arr, net_new_mrr: b.netNew, new_mrr: b.new,
          expansion_mrr: b.expansion, contraction_mrr: b.contraction, churned_mrr: b.churned,
          reactivation_mrr: b.reactivation, opening_mrr: b.opening, nrr: b.nrr, grr: b.grr,
          bridge_variance: b.variance })[name];
      case "cash_collected": return round2(cashFor(P, month).net_cash);
      case "invoiced": return round2(cashFor(P, month).invoiced);
      case "failed_payment_exposure": return round2(cashFor(P, month).failed_exposure);
      case "refunded": return round2(cashFor(P, month).refunded);
      case "recognized": return round2(cashFor(P, month).recognized);
      case "deferred": return round2(cashFor(P, month).deferred);
      case "tie_out_variance": // invoiced less successful payments less unpaid exposure
        b = cashFor(P, month);
        return round2(b.invoiced - b.successful_payments - b.failed_exposure);
      case "conflicts_before_contract_start": return contractConflictProfile(P).beforeStart;
      case "conflicts_same_month_as_start": return contractConflictProfile(P).sameMonthAsStart;
      case "conflicts_after_contract_end": return contractConflictProfile(P).afterEnd;
      case "cancellations_in_latest_month": return P.meta.cancellation_boundary.month_cancellations;
      case "cancellations_on_last_day": return P.meta.cancellation_boundary.last_day_cancellations;
      case "cash_collected_total": return round2(P.cash.reduce(function (s, c) { return s + c.net_cash; }, 0));
      case "invoiced_total": return round2(P.cash.reduce(function (s, c) { return s + c.invoiced; }, 0));
      case "failed_payment_exposure_total": return openInvoiceSummary(P).exposure;
      case "failed_payment_attempts": return openInvoiceSummary(P).invoices;
      case "exception_records": return exceptionSummary(P, f).records;
      case "exception_invoices": return exceptionSummary(P, f).invoices;
      case "exception_exposure": return exceptionSummary(P, f).exposure;
      case "cohort_logo_retention": case "cohort_customers": case "cohort_ndr":
        var cell = P.cohorts.filter(function (c) { return c.cohort === f.cohort && c.age === f.age; })[0];
        if (!cell) throw new Error("No cohort cell");
        return ({ cohort_logo_retention: cell.logo, cohort_customers: cell.size, cohort_ndr: cell.ndr })[name];
      case "risk_scored": return riskSummary(P, f.threshold).scored;
      case "risk_flagged": return riskSummary(P, f.threshold).flagged;
      case "risk_true_positives": return riskSummary(P, f.threshold).truePositives;
      case "risk_precision": return riskSummary(P, f.threshold).precision;
      case "risk_recall": return riskSummary(P, f.threshold).recall;
      case "risk_exposed_mrr": return riskSummary(P, f.threshold).exposedMrr;
      case "risk_net_value": return riskSummary(P, f.threshold).netValue;
      case "risk_queue_accounts": return riskQueue(P, f.threshold).length;
      default: throw new Error("Unknown measure " + name);
    }
  }

  var api = { bridgeByMonth: bridgeByMonth, cashFor: cashFor, exceptionList: exceptionList,
    exceptionSummary: exceptionSummary, contractConflictProfile: contractConflictProfile, openInvoiceSummary: openInvoiceSummary,
    riskSummary: riskSummary, riskQueue: riskQueue, driverTable: driverTable,
    calibration: calibration, liftDeciles: liftDeciles, evaluate: evaluate, monthIndex: monthIndex };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Measures = api;
})(typeof window !== "undefined" ? window : globalThis);
