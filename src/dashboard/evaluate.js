// Evaluate dashboard measures under filter states. Usage: node evaluate.js payload.json cases.json
"use strict";
const fs = require("fs");
const path = require("path");
const Measures = require(path.join(__dirname, "..", "..", "dashboard", "measures.js"));

const payload = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const results = cases.map((c) => Measures.evaluate(payload, c.measure, c.filter));
process.stdout.write(JSON.stringify(results));
