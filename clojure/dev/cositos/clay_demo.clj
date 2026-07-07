(ns cositos.clay-demo
  "Live Clay demo (cositos-059.8): a JVM-authoritative counter widget rendered in the
  browser via the REAL @cositos/front runtime (Model + ClayChannel), talking to this JVM
  over Clay's websocket using the cositos.clay wire codec.

  Round trip: browser button -> model.send({kind:'increment'}) (custom frame) -> JVM
  :on-receive -> apply-inbound -> swap! count -> update-frame -> broadcast! -> browser
  Model 'change:count' -> re-render. No Jupyter comm, no Clay patch.

  Run headless for verification:  clojure -M:clay-demo
  (prints DEMO_READY port=1971, serves the widget, then blocks)."
  (:require [cositos.clay :as clay]
            [scicloj.clay.v2.server :as server]
            [clojure.java.io :as io]
            [clojure.string :as str]))

(def state (atom {"count" 0}))

(defn- copy-front!
  "Copy the @cositos/front ESM modules the page imports into the served dir."
  [dir]
  (io/make-parents (io/file dir "x"))
  (doseq [f ["buffers.js" "model.js" "channels.js"]]
    (io/copy (io/file "../front/src" f) (io/file dir f))))

(def page-html
  "<!doctype html><html><head><meta charset=\"utf-8\"><title>cositos on Clay</title></head>
<body>
  <div id=\"widget\" style=\"font:16px sans-serif;padding:1em\">
    <h3>cositos counter (JVM-authoritative, via Clay)</h3>
    count = <span id=\"count\">?</span>
    <button id=\"inc\">increment</button>
  </div>
  <script type=\"module\">
    import { Model } from './model.js';
    import { ClayChannel } from './channels.js';
    const ws = new WebSocket('ws://localhost:' + location.port);
    const channel = new ClayChannel(ws);
    const model = new Model({ count: 0 }, channel);
    const out = document.getElementById('count');
    model.on('change:count', (v) => { out.textContent = v; });
    document.getElementById('inc').addEventListener('click', () => {
      model.send({ kind: 'increment' });
    });
    // expose for headless verification
    window.__widget = { model };
  </script>
</body></html>")

(defn on-open
  "Push the authoritative initial state to a freshly connected client."
  [ch]
  (server/broadcast! (clay/update-frame @state)))

(defn on-receive
  "Handle inbound cositos frames: an 'increment' custom bumps the authoritative count and
  broadcasts the new state back."
  [_ch msg]
  (when-let [parsed (clay/parse-frame msg)]
    (let [{:keys [type content]} (clay/apply-inbound parsed)]
      (when (and (= :custom type) (= "increment" (get content "kind")))
        (swap! state update "count" inc)
        (server/broadcast! (clay/update-frame @state))))))

(defn -main [& _]
  (let [dir "/tmp/cositos-clay-demo"]
    (copy-front! dir)
    (server/open! {:port 1971 :browse false})
    (server/update-page! {:page page-html
                          :base-target-path dir
                          :full-target-path (str dir "/index.html")
                          :in-memory true})
    (server/install-websocket-handler! :on-open #'on-open)
    (server/install-websocket-handler! :on-receive #'on-receive)
    (println "DEMO_READY port=1971")
    (flush)
    @(promise)))
