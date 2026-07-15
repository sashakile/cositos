(ns cositos.core-test
  "Certifies the Clojure protocol core against the shared golden fixtures
  (../fixtures/*.json), exactly as julia/test/runtests.jl and tests/test_conformance.py do.
  Buffers are compared by raw bytes."
  (:require [clojure.test :refer [deftest testing is]]
            [clojure.data.json :as json]
            [cositos.core :as c])
  (:import [java.util Base64]
           [java.nio ByteBuffer ByteOrder]))

(def fixtures-dir "../fixtures")

(defn load-fixture [name]
  (json/read-str (slurp (str fixtures-dir "/" name ".json"))))

(defn b64 [^bytes b] (.encodeToString (Base64/getEncoder) b))
(defn bytes-of [^String s] (.getBytes s "UTF-8"))

(defn float32-le
  "Little-endian float32 byte array for a seq of numbers (matches the fixture buffer)."
  [xs]
  (let [bb (doto (ByteBuffer/allocate (* 4 (count xs)))
             (.order ByteOrder/LITTLE_ENDIAN))]
    (doseq [x xs] (.putFloat bb (float x)))
    (.array bb)))

;; ---- message-builder conformance ----

(deftest comm-open-matches-fixture
  (let [fx (load-fixture "comm_open")
        [data buffers metadata]
        (c/build-comm-open {"_esm" "export default { render() {} }" "value" 0})]
    (is (= (get fx "data") data))
    (is (= (get fx "buffers_b64") (mapv b64 buffers)))
    (is (= (get fx "metadata") metadata))))

(deftest update-matches-fixture
  (let [fx (load-fixture "update")
        [data buffers] (c/build-update {"value" 42})]
    (is (= (get fx "data") data))
    (is (= (get fx "buffers_b64") (mapv b64 buffers)))))

(deftest update-nested-buffer-matches-fixture
  (let [fx (load-fixture "update_nested_buffer")
        [data buffers] (c/build-update {"img" {"bytes" (bytes-of "PNGDATA")}
                                        "shape" [1 1]})]
    (is (= (get fx "data") data))
    (is (= (get fx "buffers_b64") (mapv b64 buffers)))))

(deftest custom-matches-fixture
  (let [fx (load-fixture "custom")]
    (is (= (get fx "data") (c/build-custom {"event" "click" "n" 3})))))

;; ---- inbound parsing ----

(deftest parse-message-dispatch
  (is (= {:type :update :state {"a" 1} :buffer-paths []}
         (c/parse-message {"method" "update" "state" {"a" 1} "buffer_paths" []})))
  (is (= {:type :request-state} (c/parse-message {"method" "request_state"})))
  (is (= {:type :custom :content 42} (c/parse-message {"method" "custom" "content" 42})))
  ;; Unknown/missing method is ignored, not thrown (forward-compat, cositos-dow).
  (is (= {:type :ignored :method "bogus"} (c/parse-message {"method" "bogus"})))
  (is (= {:type :ignored :method nil} (c/parse-message {}))))

;; ---- buffer split / merge ----

(deftest buffers-round-trip
  (let [blob (bytes-of "AB")
        state {"n" 1 "x" {"ar" blob} "xs" [blob 2]}
        [stripped paths buffers] (c/remove-buffers state)]
    (is (= {"n" 1 "x" {} "xs" [nil 2]} stripped))
    (is (= [["x" "ar"] ["xs" 0]] paths))
    (let [restored (c/put-buffers stripped paths buffers)]
      (is (= (seq blob) (seq (get-in restored ["x" "ar"]))))
      (is (= (seq blob) (seq (get-in restored ["xs" 0])))))))

;; ---- buffer-split edge cases: cycle detection and depth capping ----

(deftest remove-buffers-caps-deep-nesting
  (let [nested (reduce (fn [acc _] {"n" acc}) {} (range 2001))]
    (is (thrown? clojure.lang.ExceptionInfo (c/remove-buffers nested)))))

(deftest remove-buffers-allows-dag
  (let [shared {"v" 1}
        state {"a" shared "b" shared}
        [stripped _ _] (c/remove-buffers state)]
    (is (= {"a" {"v" 1} "b" {"v" 1}} stripped))))

;; ---- serialization: dump/load_document certified vs widget-state.json ----

(defn widget-state-entries []
  [["box" {"_esm" "export default { render({model, el}) { /* VBox */ } }"
           "children" ["IPY_MODEL_plot"]}]
   ["plot" {"_esm" "export default { render({model, el}) { /* float32 plot */ } }"
            "shape" [3] "dtype" "float32" "data" (float32-le [1.5 2.5 -3.0])}]])

(deftest dump-document-reproduces-fixture
  (is (= (load-fixture "widget-state") (c/dump-document (widget-state-entries)))))

(deftest base64-buffer-codec-matches-fixture-string
  (let [[_ record] (c/dump-model ["plot" {"_esm" "e" "shape" [3] "dtype" "float32"
                                          "data" (float32-le [1.5 2.5 -3.0])}])
        buf (first (get record "buffers"))]
    (is (= ["data"] (get buf "path")))
    (is (= "base64" (get buf "encoding")))
    (is (= "AADAPwAAIEAAAEDA" (get buf "data")))))

(deftest load-document-reconstructs-entries
  (let [loaded (c/load-document (load-fixture "widget-state"))
        by-id (into {} loaded)]
    (is (= #{"box" "plot"} (set (map first loaded))))
    (is (= ["IPY_MODEL_plot"] (get-in by-id ["box" "children"])))
    (is (= (seq (float32-le [1.5 2.5 -3.0])) (seq (get-in by-id ["plot" "data"]))))))

(deftest buffer-free-document-round-trips
  (let [entries [["box" {"children" ["IPY_MODEL_child"]}]
                 ["child" {"value" 42}]]
        by-id (into {} (c/load-document (c/dump-document entries)))]
    (is (= ["IPY_MODEL_child"] (get-in by-id ["box" "children"])))
    (is (= 42 (get-in by-id ["child" "value"])))
    (let [doc (c/dump-document entries)]
      (is (= doc (c/dump-document (c/load-document doc)))))))

(deftest dump-document-validates-model-ids
  (is (thrown? clojure.lang.ExceptionInfo (c/dump-document [["" {"value" 1}]])))
  (is (thrown? clojure.lang.ExceptionInfo
               (c/dump-document [["dup" {"value" 1}] ["dup" {"value" 2}]]))))

(deftest load-model-rejects-non-base64-encoding
  (is (thrown? clojure.lang.ExceptionInfo
               (c/load-model ["m" {"state" {"data" nil}
                                   "buffers" [{"path" ["data"] "encoding" "hex" "data" "00"}]}]))))
