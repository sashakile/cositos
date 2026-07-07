(ns cositos.clay
  "Pure Clay wire codec for cositos widgets: encode/parse the `cositos <json>` text frames
  that ride Clay's websocket, on top of the fixture-certified protocol core (cositos.core).

  Clay (Scicloj's REPL notebook tool) is not a Jupyter kernel and has no comm protocol;
  it exposes a full-duplex public websocket instead. cositos frames share that socket with
  Clay's own control frames (refresh/loading/scittle-eval-string), so they are tagged with
  a `cositos ` prefix (mirroring Clay's `scittle-eval-string ` convention). Because Clay
  frames are text, binary buffers travel base64-encoded inline.

  Wire envelope (JSON after the prefix): {\"msg\": <comm_msg>, \"buffers\": [<base64>, ...]}.

  This namespace is deliberately transport-free: no `scicloj.clay.v2.server` dependency, so
  it is certified with the core by `clojure -M:test`. The thin server binding (broadcast! /
  install-websocket-handler!) lives in dev/cositos/clay_demo.clj and is exercised live."
  (:require [cositos.core :as core]
            [clojure.data.json :as json]
            [clojure.string :as str])
  (:import [java.util Base64]))

(def prefix "cositos ")

(defn- encode-buffers [byte-buffers]
  (mapv #(.encodeToString (Base64/getEncoder) ^bytes %) byte-buffers))

(defn- decode-buffers [b64s]
  (mapv #(.decode (Base64/getDecoder) ^String %) b64s))

(defn frame
  "Encode an outbound comm_msg `msg` plus its `byte-buffers` (a seq of byte arrays) as a
  cositos wire frame string."
  [msg byte-buffers]
  (str prefix (json/write-str {"msg" msg "buffers" (encode-buffers byte-buffers)})))

(defn update-frame
  "Frame an `update` for `state` (buffers split by the core, then base64-encoded)."
  [state]
  (let [[data buffers] (core/build-update state)]
    (frame data buffers)))

(defn custom-frame
  "Frame a `custom` message carrying `content`."
  [content]
  (frame (core/build-custom content) []))

(defn parse-frame
  "Parse an inbound wire frame. Returns {:msg <comm_msg> :buffers [<byte-array>...]} for a
  cositos frame, or nil for anything else (Clay's own frames, non-strings)."
  [s]
  (when (and (string? s) (str/starts-with? s prefix))
    (let [{:strs [msg buffers]} (json/read-str (subs s (count prefix)))]
      {:msg msg :buffers (decode-buffers (or buffers []))})))

(defn apply-inbound
  "Dispatch a parsed frame through the core parser. For an update, merge the decoded
  buffers back into the state at their buffer_paths, so callers get ready-to-use state.
  Returns the core's tagged map ({:type :update|:custom|:request-state|:ignored}, with
  `:state` already merged for updates)."
  [{:keys [msg buffers]}]
  (let [parsed (core/parse-message msg)]
    (if (= :update (:type parsed))
      (assoc parsed :state (core/put-buffers (:state parsed) (:buffer-paths parsed) buffers))
      parsed)))
