import assert from "node:assert/strict";
import { test } from "node:test";

import { remove_buffers, put_buffers } from "../src/buffers.js";

test("remove_buffers extracts a top-level binary by key", () => {
  const { state, buffer_paths, buffers } = remove_buffers({ n: 1, blob: new Uint8Array([1, 2]) });
  assert.deepEqual(state, { n: 1 });
  assert.deepEqual(buffer_paths, [["blob"]]);
  assert.equal(buffers.length, 1);
});

test("list slot becomes null", () => {
  const b = new Uint8Array([9]);
  const { state, buffer_paths } = remove_buffers({ xs: [b, 2, b] });
  assert.deepEqual(state, { xs: [null, 2, null] });
  assert.deepEqual(buffer_paths, [["xs", 0], ["xs", 2]]);
});

test("nested round-trip is lossless", () => {
  const original = { x: { ar: new Uint8Array([1]) }, y: [new Uint8Array([2]), 3] };
  const { state, buffer_paths, buffers } = remove_buffers(original);
  put_buffers(state, buffer_paths, buffers);
  assert.deepEqual(state, original);
});

test("no binary returns the same object identity", () => {
  const original = { a: 1, b: [1, 2] };
  const { state, buffers } = remove_buffers(original);
  assert.equal(state, original);
  assert.equal(buffers.length, 0);
});
