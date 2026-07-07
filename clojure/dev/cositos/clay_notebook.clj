(ns cositos.clay-notebook
  "A proper Clay notebook (cositos-059.8 follow-up (a)): renders a live cositos widget
  through Clay's `kind` system via `clay/make!` (HTML / Quarto-exportable), rather than the
  raw `update-page!` used by clay_demo.

  The @cositos/front runtime (buffers + Model + ClayChannel) is inlined as ONE portable
  ES module (a mini-bundle of front/src) so the rendered document is self-contained. The
  live two-way round-trip uses the same cositos.clay transport over Clay's websocket.

  REPL workflow (what a user does):
    (require '[scicloj.clay.v2.api :as clay])
    (clay/start!)          ; start Clay's server + browser
    (install-handlers!)    ; wire the JVM-side counter
    (render!)              ; make! the widget document

  Headless verification:  clojure -M:clay-notebook   (serves at :1971, then blocks)."
  (:require [cositos.clay :as tx]
            [scicloj.clay.v2.api :as clay]
            [scicloj.clay.v2.server :as server]
            [scicloj.kindly.v4.kind :as kind]
            [clojure.java.io :as io]
            [clojure.string :as str]))

;; ---- inline @cositos/front as one portable ES module ----

(defn- strip
  "Drop relative imports and leading `export ` so the module's symbols share one scope."
  [src]
  (->> (str/split-lines src)
       (remove #(str/starts-with? % "import "))
       (map #(if (str/starts-with? % "export ") (subs % (count "export ")) %))
       (str/join "\n")))

(def runtime-bundle
  "buffers + Model + ClayChannel + LocalChannel, concatenated in dependency order."
  (->> ["buffers.js" "model.js" "channels.js"]
       (map #(strip (slurp (io/file "../front/src" %))))
       (str/join "\n\n")))

(def widget-bootstrap
  "Mounts a JVM-authoritative counter: ClayChannel over Clay's websocket; the button sends
  a custom 'increment', the JVM bumps the count and pushes it back."
  "
const root = document.getElementById('cositos-counter');
const out = root.querySelector('.count');
const ws = new WebSocket('ws://' + location.host);
const channel = new ClayChannel(ws);            // listener attached before the server push
const model = new Model({ count: 0 }, channel);
model.on('change:count', (v) => { out.textContent = v; });
root.querySelector('button').addEventListener('click', () => {
  try { model.send({ kind: 'increment' }); } catch (e) { /* static export: no live server */ }
});
window.__widget = { model };
")

(defn widget-hiccup []
  (kind/hiccup
   [:div
    [:h2 "cositos on Clay"]
    [:p "A binding-free anywidget-style widget, hosted by "
     [:a {:href "https://scicloj.github.io/clay/"} "Clay"] " — "
     "not a Jupyter kernel, no comm protocol. State is authoritative on the JVM and "
     "syncs to the browser over Clay's websocket via the cositos.clay transport."]
    [:div {:id "cositos-counter"
           :style {:font "16px sans-serif" :padding "0.75em" :border "1px solid #ddd"
                   :border-radius "6px" :display "inline-block"}}
     "count = " [:span {:class "count"} "?"] " "
     [:button "increment"]]
    [:script {:type "module"} (str runtime-bundle "\n" widget-bootstrap)]]))

;; ---- JVM-side counter (reuses the cositos.clay transport) ----

(def state (atom {"count" 0}))

(defn on-open [_ch]
  (server/broadcast! (tx/update-frame @state)))

(defn on-receive [_ch msg]
  (when-let [parsed (tx/parse-frame msg)]
    (let [{:keys [type content]} (tx/apply-inbound parsed)]
      (when (and (= :custom type) (= "increment" (get content "kind")))
        (swap! state update "count" inc)
        (server/broadcast! (tx/update-frame @state))))))

(defn install-handlers! []
  (server/install-websocket-handler! :on-open #'on-open)
  (server/install-websocket-handler! :on-receive #'on-receive))

(defn render!
  "Render the widget document through Clay's kind system. Add :format [:quarto :html] for
  a Quarto export."
  ([] (render! {}))
  ([opts]
   (clay/make! (merge {:single-value (widget-hiccup)} opts))))

(defn -main [& _]
  (server/open! {:port 1971 :browse false})
  (install-handlers!)
  (render! {:show true})
  (println "NOTEBOOK_READY port=1971")
  (flush)
  @(promise))
