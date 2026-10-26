import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("reportes-before-c3.html", import.meta.url), "utf8");
const generated = readFileSync(new URL("../../web/reportes.html", import.meta.url), "utf8");
const helpers = source.match(/  const totalOf = \(c\)[\s\S]*?  const answerLabel = \(answer\)[^\n]+;\n/);
assert.ok(helpers, "the report-status helpers are present in the generator source");
assert.ok(generated.includes(helpers[0]), "the generated page contains the same status helpers");

const { statusOf, statusLabel, answerLabel } = vm.runInNewContext(
  `${helpers[0]}; ({ statusOf, statusLabel, answerLabel });`,
);
const counts = (sin_agua = 0, baja = 0, con_agua = 0) => ({ sin_agua, baja, con_agua });

test("a strict majority keeps its actual status", () => {
  assert.equal(statusOf(counts(3, 1, 1)), "dry");
  assert.equal(statusOf(counts(1, 3, 1)), "low");
  assert.equal(statusOf(counts(1, 1, 3)), "ok");
  assert.equal(statusOf(counts(1)), "dry");
  assert.equal(statusOf(counts(0, 1)), "low");
  assert.equal(statusOf(counts(0, 0, 1)), "ok");
});

test("ties and splits without a majority are mixed, never low pressure by default", () => {
  assert.equal(statusOf(counts(5, 0, 5)), "mixed");
  assert.equal(statusOf(counts(2, 2, 1)), "mixed");
  assert.equal(statusOf(counts(1, 1, 1)), "mixed");
  assert.equal(statusOf(counts(0, 1, 1)), "mixed");
  assert.equal(statusLabel(counts(5, 0, 5)), "Reportes mixtos");
});

test("missing and unknown answers are not presented as known water states", () => {
  assert.equal(statusOf(null), null);
  assert.equal(statusLabel(null), "Sin reportes");
  assert.equal(answerLabel("sin_agua"), "sin agua");
  assert.equal(answerLabel("baja"), "baja presión");
  assert.equal(answerLabel("con_agua"), "con agua");
  assert.equal(answerLabel("invented"), "estado no disponible");
});
