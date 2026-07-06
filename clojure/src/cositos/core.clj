(ns cositos.core
  "Binding-free anywidget-style backend core for a Clojure Jupyter kernel (clojupyter).

  Pure port of the cositos protocol core: builds/parses ipywidgets widget-messaging
  protocol v2.1.0 messages, performs binary-buffer split/merge (protocol v2 nested rules),
  and serializes widget state to the Widget State JSON schema v2. No kernel/transport code;
  a host supplies that. Certified against the shared golden fixtures in ../fixtures/*.json.

  Conventions: state is a map with string keys; lists are vectors; binary values are Java
  byte arrays (`bytes?`). Wire `buffer_paths` use 0-based integer indices for list
  positions and string keys for map entries."
  (:import [java.util Base64]))

(def protocol-version-major 2)
(def protocol-version-minor 1)
(def protocol-version "2.1.0")

(def anywidget-module-version "~0.11.*")

;; Widget State JSON schema version (distinct from the protocol version 2.1.0).
(def state-version-major 2)
(def state-version-minor 0)

(defn- immutable-fields [version]
  {"_model_module" "anywidget"
   "_model_name" "AnyModel"
   "_model_module_version" version
   "_view_module" "anywidget"
   "_view_name" "AnyView"
   "_view_module_version" version
   "_view_count" nil})

;; ---- buffer split / merge (protocol v2 nested rules) ----

(defn- binary? [x] (bytes? x))
(defn- container? [x] (and (or (map? x) (vector? x)) (not (binary? x))))

(defn- separate
  "Recurse into maps/vectors extracting binary values. Returns [stripped paths buffers],
  threading the accumulated `paths` and `buffers` through. A binary at a map key removes
  the key; at a list index it becomes nil."
  [sub path paths buffers]
  (cond
    (map? sub)
    (reduce (fn [[out ps bs] [k v]]
              (let [p (conj path k)]
                (cond
                  (binary? v) [out (conj ps p) (conj bs v)]
                  (container? v) (let [[cv ps2 bs2] (separate v p ps bs)]
                                   [(assoc out k cv) ps2 bs2])
                  :else [(assoc out k v) ps bs])))
            [{} paths buffers] sub)

    (vector? sub)
    (reduce (fn [[out ps bs] [i v]]
              (let [p (conj path i)]              ; 0-based wire index
                (cond
                  (binary? v) [(conj out nil) (conj ps p) (conj bs v)]
                  (container? v) (let [[cv ps2 bs2] (separate v p ps bs)]
                                   [(conj out cv) ps2 bs2])
                  :else [(conj out v) ps bs])))
            [[] paths buffers] (map-indexed vector sub))

    :else [sub paths buffers]))

(defn remove-buffers
  "Strip binary values out of `state`. Returns [stripped buffer-paths buffers] where
  buffer-paths records each binary's location (string map keys, 0-based list indices)."
  [state]
  (separate state [] [] []))

(defn put-buffers
  "Inverse of `remove-buffers`: return `state` with each buffer merged back at its path.
  Integer path segments index vectors directly (already 0-based)."
  [state paths buffers]
  (reduce (fn [s [p buf]] (assoc-in s p buf)) state (map vector paths buffers)))

;; ---- base64 buffer codec ----

(defn- b64-encode ^String [^bytes b] (.encodeToString (Base64/getEncoder) b))
(defn- b64-decode ^bytes [^String s] (.decode (Base64/getDecoder) s))

(defn- decode-buffer ^bytes [entry]
  (let [enc (get entry "encoding")]
    (when-not (= enc "base64")
      (throw (ex-info (str "Unsupported buffer encoding: " (pr-str enc) " (expected 'base64')")
                      {:encoding enc})))
    (b64-decode (get entry "data"))))

;; ---- message builders ----

(defn build-comm-open
  "Build the comm_open payload. Returns [data buffers metadata]."
  ([state] (build-comm-open state anywidget-module-version))
  ([state anywidget-version]
   (let [full (merge (immutable-fields anywidget-version) state)
         [stripped paths buffers] (remove-buffers full)]
     [{"state" stripped "buffer_paths" paths} buffers {"version" protocol-version}])))

(defn build-update
  "Build an update (comm_msg) payload. Returns [data buffers]."
  [state]
  (let [[stripped paths buffers] (remove-buffers state)]
    [{"method" "update" "state" stripped "buffer_paths" paths} buffers]))

(defn build-custom
  "Build a custom message payload."
  [content]
  {"method" "custom" "content" content})

;; ---- inbound parsing ----

(defn parse-message
  "Parse an inbound comm_msg data map into a tagged map. Throws on an unknown method."
  [data]
  (case (get data "method")
    "update" {:type :update
              :state (get data "state" {})
              :buffer-paths (get data "buffer_paths" [])}
    "request_state" {:type :request-state}
    "custom" {:type :custom :content (get data "content")}
    (throw (ex-info (str "Unrecognized comm message method: " (pr-str (get data "method")))
                    {:method (get data "method")}))))

;; ---- serialization: widget-state JSON schema v2 (dump/load) ----

(defn dump-model
  "Serialize one [model-id state] entry to [model-id record] per schema v2. The anywidget
  identity is read from `state` (`_model_*`) or defaulted; binary values move to a base64
  `buffers` array; the rest of `state` is preserved so `load-model` is the exact inverse."
  ([entry] (dump-model entry anywidget-module-version))
  ([[model-id state] anywidget-version]
   (let [[stripped paths buffers] (remove-buffers state)
         record (cond-> {"model_name" (get state "_model_name" "AnyModel")
                         "model_module" (get state "_model_module" "anywidget")
                         "model_module_version" (get state "_model_module_version" anywidget-version)
                         "state" stripped}
                  (seq buffers)
                  (assoc "buffers"
                         (mapv (fn [p b] {"path" p "encoding" "base64" "data" (b64-encode b)})
                               paths buffers)))]
     [model-id record])))

(defn load-model
  "Inverse of `dump-model`: rebuild [model-id state], decoding base64 buffers to byte
  arrays and merging them back into `state`."
  [[model-id record]]
  (let [state (get record "state")
        entries (get record "buffers" [])
        paths (mapv #(get % "path") entries)
        buffers (mapv decode-buffer entries)]
    [model-id (put-buffers state paths buffers)]))

(defn dump-document
  "Serialize many [model-id state] entries into a v2 Widget-State envelope
  {version_major, version_minor, state}. Model ids must be non-empty and unique."
  ([entries] (dump-document entries anywidget-module-version))
  ([entries anywidget-version]
   (let [state (reduce (fn [acc entry]
                         (let [[model-id record] (dump-model entry anywidget-version)]
                           (when (or (nil? model-id) (= "" model-id))
                             (throw (ex-info "model_id must be a non-empty string (it is the document key)"
                                             {:model-id model-id})))
                           (when (contains? acc model-id)
                             (throw (ex-info (str "duplicate model_id " (pr-str model-id)
                                                  ": document keys must be unique")
                                             {:model-id model-id})))
                           (assoc acc model-id record)))
                       {} entries)]
     {"version_major" state-version-major
      "version_minor" state-version-minor
      "state" state})))

(defn load-document
  "Inverse of `dump-document`: rebuild a vector of [model-id state]. References between
  models are plain \"IPY_MODEL_<id>\" strings, so loading is a flat id-keyed pass."
  [doc]
  (mapv load-model (get doc "state")))
