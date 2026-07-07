(ns cositos.test-runner
  "Minimal clojure.test runner: exits non-zero on any failure/error so `clojure -M:test`
  can gate CI without an external test-runner dependency."
  (:require [clojure.test :as t]
            cositos.core-test
            cositos.clay-test))

(defn -main [& _]
  (let [{:keys [fail error]} (t/run-tests 'cositos.core-test 'cositos.clay-test)]
    (System/exit (if (pos? (+ fail error)) 1 0))))
