/**
 * Buffer split/merge on the frontend — the mirror of the Python core's `buffers.py`,
 * following protocol v2 nested rules. Binary values are `ArrayBuffer` or `ArrayBufferView`.
 */

function isBinary(v) {
  return v instanceof ArrayBuffer || ArrayBuffer.isView(v);
}

function clone(container) {
  return Array.isArray(container) ? container.slice() : { ...container };
}

/**
 * @param {*} state
 * @returns {{state: *, buffer_paths: Array<Array<string|number>>, buffers: any[]}}
 */
export function remove_buffers(state) {
  const acc = { buffer_paths: [], buffers: [] };
  const result = separate(state, [], acc);
  return { state: result, buffer_paths: acc.buffer_paths, buffers: acc.buffers };
}

function entriesOf(sub) {
  return Array.isArray(sub) ? sub.map((v, i) => [i, v]) : Object.entries(sub);
}

function extractBinary(out, key, value, path, acc) {
  if (Array.isArray(out)) out[key] = null;
  else delete out[key];
  acc.buffers.push(value);
  acc.buffer_paths.push([...path, key]);
}

function separate(sub, path, acc) {
  if (sub === null || typeof sub !== "object" || isBinary(sub)) return sub;
  let out = null;
  for (const [key, value] of entriesOf(sub)) {
    if (isBinary(value)) {
      out = out ?? clone(sub);
      extractBinary(out, key, value, path, acc);
    } else if (value !== null && typeof value === "object") {
      const nested = separate(value, [...path, key], acc);
      if (nested !== value) {
        out = out ?? clone(sub);
        out[key] = nested;
      }
    }
  }
  return out ?? sub;
}

/**
 * Inverse of {@link remove_buffers}; mutates `state` in place.
 * @param {*} state
 * @param {Array<Array<string|number>>} buffer_paths
 * @param {any[]} buffers
 */
export function put_buffers(state, buffer_paths, buffers) {
  buffer_paths.forEach((path, i) => {
    let obj = state;
    for (const key of path.slice(0, -1)) obj = obj[key];
    obj[path[path.length - 1]] = buffers[i];
  });
}
