(ns cositos.clay-test
  "Certifies the pure Clay wire codec (cositos.clay) against the shared golden fixtures.
  No Clay/server/browser dependency here \u2014 the live glue lives in dev/cositos/clay_demo.clj
  and is exercised by the L3 round-trip. This is the JVM mirror of front/test/clay_channel.test.js."
  (:require [clojure.test :refer [deftest testing is]]
            [clojure.data.json :as json]
            [clojure.java.io :as io]
            [cositos.clay :as clay]))

(def prefix "cositos ")

(defn- load-fixture [name]
  (with-open [r (io/reader (io/file "../fixtures" name))]
    (json/read r)))

(defn- bytes= [a b] (java.util.Arrays/equals ^bytes a ^bytes b))

(deftest update-frame-matches-fixture
  (testing "update-frame emits a cositos-prefixed frame with the core split + base64 buffers"
    (let [fx (load-fixture "update_nested_buffer.json")
          state {"img" {"bytes" (.getBytes "PNGDATA")} "shape" [1 1]}
          frame (clay/update-frame state)]
      (is (.startsWith frame prefix))
      (let [{:strs [msg buffers]} (json/read-str (subs frame (count prefix)))]
        (is (= (get fx "data") msg) "msg equals the fixture comm_msg (state + buffer_paths)")
        (is (= (get fx "buffers_b64") buffers) "buffers are the fixture's base64")))))

(deftest parse-frame-ignores-non-cositos
  (testing "Clay's own broadcast frames are not cositos frames"
    (is (nil? (clay/parse-frame "refresh")))
    (is (nil? (clay/parse-frame "scittle-eval-string (println :hi)")))
    (is (nil? (clay/parse-frame nil)))))

(deftest inbound-update-round-trips-buffers
  (testing "a frame produced by update-frame parses + applies back to the original state"
    (let [state {"img" {"bytes" (.getBytes "PNGDATA")} "shape" [1 1]}
          parsed (clay/parse-frame (clay/update-frame state))
          applied (clay/apply-inbound parsed)]
      (is (= :update (:type applied)))
      (is (= [1 1] (get-in applied [:state "shape"])))
      (is (bytes= (.getBytes "PNGDATA") (get-in applied [:state "img" "bytes"]))
          "the binary buffer survives frame -> parse -> apply byte-for-byte"))))

(deftest custom-round-trips
  (testing "custom-frame and inbound custom carry content unchanged"
    (let [frame (clay/custom-frame {"kind" "ping"})
          applied (clay/apply-inbound (clay/parse-frame frame))]
      (is (= :custom (:type applied)))
      (is (= {"kind" "ping"} (:content applied))))))

(deftest inbound-request-state-and-ignored
  (testing "request_state and unknown methods are surfaced, never thrown"
    (is (= :request-state
           (:type (clay/apply-inbound (clay/parse-frame (str prefix (json/write-str {"msg" {"method" "request_state"} "buffers" []})))))))
    (is (= :ignored
           (:type (clay/apply-inbound (clay/parse-frame (str prefix (json/write-str {"msg" {"method" "bogus"} "buffers" []})))))))))
