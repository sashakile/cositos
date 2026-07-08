(ns dump
  "Clojure implementation of the cross-language e2e contract (cositos-1wi.6).

  See examples/e2e/README.md for the full contract. This program:

    1. builds the FIXED input (an anywidget counter, {_esm, value: 42}) into a
       widget-state Document via cositos.core/dump-document;
    2. asserts the round-trip law load(dump(x)) == x via cositos.core/load-document;
    3. diffs the produced document against the pinned expected.json shared by every
       language example (../expected.json, one level up from this directory);
    4. prints \"OK clojure\" and exits 0 on success, or a readable diff and a non-zero
       exit on any divergence.

  Run it with `mise run e2e-clojure` (or `clojure -M:dump` from this directory)."
  (:require [clojure.data :as data]
            [clojure.data.json :as json]
            [clojure.java.io :as io]
            [cositos.core :as core])
  (:gen-class))

(def esm
  "export default { render({ model, el }) { el.textContent = model.get(\"value\"); } }")

(def model-id "counter")

;; The FIXED input state the whole contract is pinned to (see README "The fixed input").
(def input-state {"_esm" esm "value" 42})

(defn build-document
  "Serialize the fixed counter into a widget-state Document."
  []
  (core/dump-document [[model-id input-state]]))

(defn load-expected
  "The pinned golden document this port certifies against (shared with the other
  language examples: examples/e2e/expected.json)."
  []
  (json/read-str (slurp (io/file "../expected.json"))))

(defn round-trip-failures
  "Check load(dump(x)) == x; return failure messages (empty means it holds)."
  []
  (let [doc (build-document)
        loaded (core/load-document doc)
        expected-entries [[model-id input-state]]]
    (if (= loaded expected-entries)
      []
      [(str "round-trip law violated: load(dump(x)) = " (pr-str loaded)
            ", expected " (pr-str expected-entries))])))

(defn json-diff
  "Human-readable structural diff between expected and actual; empty means equal."
  [expected actual]
  (if (= expected actual)
    []
    (let [[only-expected only-actual] (data/diff expected actual)]
      ["produced document diverges from expected.json:"
       (str "  only in expected.json: " (pr-str only-expected))
       (str "  only in produced doc: " (pr-str only-actual))])))

(defn verify
  "Run the full contract; return a list of failure messages (empty means pass)."
  [expected]
  (concat (round-trip-failures) (json-diff expected (build-document))))

(defn -main [& _args]
  (let [failures (verify (load-expected))]
    (if (seq failures)
      (do (binding [*out* *err*] (doseq [line failures] (println line)))
          (System/exit 1))
      (do (println "OK clojure")
          (System/exit 0)))))
