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
  "Mounts two independent JVM-authoritative counters over ONE websocket, each with its own
  ClayChannel id. Routing (cositos-059.8b) keeps their messages separate: clicking counter
  'a' only increments 'a'."
  "
const ws = new WebSocket('ws://' + location.host);
function mount(id, elId) {
  const root = document.getElementById(elId);
  const out = root.querySelector('.count');
  const channel = new ClayChannel(ws, id);        // id-tagged: shares the socket, routes by id
  const model = new Model({ count: 0 }, channel);
  model.on('change:count', (v) => { out.textContent = v; });
  root.querySelector('button').addEventListener('click', () => {
    try { model.send({ kind: 'increment' }); } catch (e) { /* static export: no live server */ }
  });
  return model;
}
window.__widgets = { a: mount('a', 'cositos-counter-a'), b: mount('b', 'cositos-counter-b') };
")

(defn- counter-box [id label]
  [:div {:id (str "cositos-counter-" id)
         :style {:font "16px sans-serif" :padding "0.75em" :border "1px solid #ddd"
                 :border-radius "6px" :display "inline-block" :margin-right "1em"}}
   label ": count = " [:span {:class "count"} "?"] " " [:button "increment"]])

(defn widget-hiccup []
  (kind/hiccup
   [:div
    [:h2 "cositos on Clay"]
    [:p "Two binding-free anywidget-style widgets, hosted by "
     [:a {:href "https://scicloj.github.io/clay/"} "Clay"] " — "
     "not a Jupyter kernel, no comm protocol. Each counter's state is authoritative on the "
     "JVM and syncs over a single Clay websocket via the cositos.clay transport; per-widget "
     "ids keep the two counters independent."]
    [:div (counter-box "a" "Counter A") (counter-box "b" "Counter B")]
    [:script {:type "module"} (str runtime-bundle "\n" widget-bootstrap)]]))

;; ---- JVM-side counters (reuses the cositos.clay transport) ----

(def state (atom {"a" 0 "b" 0}))

(defn on-open [_ch]
  (doseq [id ["a" "b"]]
    (server/broadcast! (tx/update-frame id {"count" (get @state id)}))))

(defn on-receive [_ch msg]
  (when-let [parsed (tx/parse-frame msg)]
    (let [id (:id parsed)
          {:keys [type content]} (tx/apply-inbound parsed)]
      (when (and (= :custom type) (= "increment" (get content "kind")) (contains? @state id))
        (swap! state update id inc)
        (server/broadcast! (tx/update-frame id {"count" (get @state id)}))))))

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
