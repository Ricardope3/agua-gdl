import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../../web/reportes.html", import.meta.url), "utf8");
const helpers = source.match(/  const totalOf = \(c\)[\s\S]*?  const answerLabel = \(answer\)[^\n]+;\n/);
assert.ok(helpers, "the report-status helpers are present in /reportes");

const { statusOf, statusLabel, answerLabel } = vm.runInNewContext(
  `${helpers[0]}; ({ statusOf, statusLabel, answerLabel });`,
);
const counts = (sin_agua = 0, baja = 0, con_agua = 0) => ({ sin_agua, baja, con_agua });

const sourceOfBlock = source.match(/  function sourceOf\(p, byUrl\) \{[\s\S]*?\n  \}\n/);
assert.ok(sourceOfBlock, "sourceOf is present in /reportes");
const { sourceOf } = vm.runInNewContext(`${sourceOfBlock[0]}; ({ sourceOf });`, { URL });
const byUrl = new Map([
  ["https://www.facebook.com/traficozmg.periodismociudadano/posts/aaa", { fuente: "vecinos", red: "facebook", url: "https://www.facebook.com/traficozmg.periodismociudadano/posts/aaa" }],
  ["https://traficozmg.com/2026/11/nota", { fuente: "medio", quien: "Tráfico ZMG", red: "web", url: "https://traficozmg.com/2026/11/nota" }],
]);

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

test("a retold story counts as the post it names in de", () => {
  const story = { fuente: "medio", quien: "Tráfico ZMG", red: "web", url: "https://traficozmg.com/2026/11/copia", de: "https://www.facebook.com/traficozmg.periodismociudadano/posts/aaa" };
  assert.equal(sourceOf(story, byUrl), "f:traficozmg.periodismociudadano");
  const reel = { fuente: "medio", quien: "Tráfico ZMG", red: "facebook", url: "https://www.facebook.com/reel/123", de: "https://traficozmg.com/2026/11/nota" };
  assert.equal(sourceOf(reel, byUrl), "m:Tráfico ZMG");
});

test("a de outside the data falls back by URL, never to a fake facebook id", () => {
  const story = { fuente: "medio", quien: "Otro medio", red: "web", url: "https://ejemplo.com/x", de: "https://traficozmg.com/2026/12/otra" };
  assert.equal(sourceOf(story, byUrl), "w:traficozmg.com");
  const tuit = { fuente: "medio", quien: "Otro medio", red: "web", url: "https://ejemplo.com/y", de: "https://x.com/vecino/status/1" };
  assert.equal(sourceOf(tuit, byUrl), "x:vecino");
  const post = { fuente: "medio", quien: "Otro medio", red: "web", url: "https://ejemplo.com/z", de: "https://www.facebook.com/pagina/posts/9" };
  assert.equal(sourceOf(post, byUrl), "f:pagina");
});

test("sources without de keep counting as themselves", () => {
  assert.equal(sourceOf({ tipo: "comentario", url: "https://www.facebook.com/p/posts/1?comment_id=2" }, byUrl), "c:https://www.facebook.com/p/posts/1?comment_id=2");
  assert.equal(sourceOf({ fuente: "medio", quien: "Milenio", red: "web", url: "https://www.milenio.com/a" }, byUrl), "m:Milenio");
  assert.equal(sourceOf({ fuente: "vecinos", red: "x", url: "https://x.com/Vecino/status/5" }, byUrl), "x:vecino");
  assert.equal(sourceOf({ fuente: "vecinos", red: "facebook", url: "https://www.facebook.com/groups/99/posts/1" }, byUrl), "g:99");
});
