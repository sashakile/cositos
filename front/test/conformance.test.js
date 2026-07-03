import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { remove_buffers } from "../src/buffers.js";

// The frontend shares the protocol-v2 buffer algorithm with the Python and Julia
// backends. This certifies front/buffers.js against the same golden fixtures, so all
// three implementations agree byte-for-byte on the split.
const fixturesDir = fileURLToPath(new URL("../../fixtures/", import.meta.url));

function loadFixture(name) {
  return JSON.parse(readFileSync(new URL(name, `file://${fixturesDir}`), "utf-8"));
}

function b64(buffers) {
  return buffers.map((b) => Buffer.from(b).toString("base64"));
}

/** Recursive JSON-structural equality tolerant of container concrete types. */
function jsonEqual(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => jsonEqual(x, b[i]));
  }
  if (a && b && typeof a === "object" && typeof b === "object") {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => jsonEqual(a[k], b[k]));
  }
  return a === b;
}

test("front remove_buffers reproduces the update_nested_buffer fixture split", () => {
  const fx = loadFixture("update_nested_buffer.json");
  const input = {
    img: { bytes: new Uint8Array(Buffer.from("PNGDATA")) },
    shape: [1, 1],
  };
  const { state, buffer_paths, buffers } = remove_buffers(input);

  assert.ok(jsonEqual(state, fx.data.state), "state matches fixture");
  assert.deepEqual(buffer_paths, fx.data.buffer_paths);
  assert.deepEqual(b64(buffers), fx.buffers_b64);
});

test("front produces no buffers for the plain update fixture", () => {
  const fx = loadFixture("update.json");
  const { state, buffer_paths, buffers } = remove_buffers({ value: 42 });
  assert.ok(jsonEqual(state, fx.data.state));
  assert.deepEqual(buffer_paths, fx.data.buffer_paths);
  assert.deepEqual(buffers, []);
});
