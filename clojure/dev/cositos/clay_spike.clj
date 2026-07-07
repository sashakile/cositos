(ns cositos.clay-spike
  "L3 of the Clay-host spike (cositos-059.7): a LIVE Clay websocket round-trip.

  Starts Clay's built-in server and installs an :on-receive handler that echoes any
  inbound `cositos <json>` frame back to all clients (with :echoed true). A browser then
  opens a WebSocket to this same server, sends one cositos envelope, and must receive the
  echo — proving Clay is a full-duplex (Tier 1 / BIDIRECTIONAL) host for cositos widgets
  WITHOUT any Jupyter comm and WITHOUT patching Clay.

  Run: clojure -M:clay-spike   (prints `SPIKE_READY port=<n>`, then blocks)."
  (:require [scicloj.clay.v2.server :as server]
            [clojure.data.json :as json]
            [clojure.string :as str]))

(def prefix "cositos ")

(defn echo-handler
  "Echo cositos frames back to every client, tagged :echoed. Ignore Clay's own frames."
  [_ch msg]
  (when (and (string? msg) (str/starts-with? msg prefix))
    (let [payload (json/read-str (subs msg (count prefix)) :key-fn keyword)
          reply   (assoc payload :echoed true)]
      (server/broadcast! (str prefix (json/write-str reply))))))

(defn -main [& _]
  (server/open! {:port 1971 :browse false})
  (server/install-websocket-handler! :on-receive #'echo-handler)
  (println "SPIKE_READY port=1971")
  (flush)
  @(promise))
