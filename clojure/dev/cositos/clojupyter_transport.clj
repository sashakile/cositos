(ns cositos.clojupyter-transport
  "clojupyter Transport adapter (cositos-ex2.5), built on the current-context crack
  confirmed live in cositos-059.9. See probe/README.md (\"clojupyter comm surface\") for
  the full mechanism and probe/kernel_probe.py's `clojure` program for the minimal
  reproduction this is built from.

  CAVEAT -- NOT A PUBLIC/UPSTREAM API. This reaches into `clojupyter.state/current-context`,
  an internal, version-coupled implementation detail (not documented, not part of
  clojupyter's public API, and free to change or disappear in a future clojupyter release
  without notice). Dev-only by design (like `cositos.clay-demo`): certified core
  (`cositos.core`) never depends on this namespace, and it requires a live clojupyter
  kernel to run at all -- there is nothing here to unit-test without one.

  SCOPE -- what this Transport actually supports, and why it's narrower than the Python
  (`cositos.jupyter.CommTransport`) / Julia (`CositosIJuliaExt`) transports:

    - `comm_open` with the full anywidget-enriched state: YES, via the *public*
      `comm-atom/create-and-insert` (no private-fn access needed for this step).
    - Bidirectional `update` (kernel<->frontend state sync): YES, via the *public*
      `comm-atom/state-update!` (outbound) and `comm-atom/watch` (inbound) -- this is
      exactly the round trip confirmed in cositos-059.9.
    - Binary buffers: NO. `comm-atom/state-update!` always emits `buffer_paths: []` on
      the wire regardless of binary values in the state passed to it; there is no public
      (or discovered private) path to attach real Jupyter binary buffers through
      comm-atom. Buffer-carrying widgets are out of scope for this transport -- use Clay
      (`cositos.clay`) instead.
    - `custom` messages (`model.send()` / `on(\"msg:custom\")`, i.e. content outside the
      state-sync shape): NO. Every public *and* private sender on `comm-atom`
      (`state-update!`, `state-set!`, and even the private `send-comm-msg!` reached via
      `var-get`) unconditionally wraps its argument as `{\"method\" \"update\" \"state\"
      <argument> \"buffer_paths\" []}` -- comm-atom is a state-sync atom, not a generic
      message-passing comm, all the way down. There is no raw-send escape hatch.
    - `request_state` (inbound): NO. comm-atom's inbound dispatch understands `update`
      messages (merges into state, notifies watchers); other inbound methods were not
      exercised and are not assumed to work here.

  This is enough to drive the reference-style counter widget (matching
  `examples/notebooks/python_counter.ipynb`'s `model.set()` + `model.save_changes()`
  pattern, which is itself just an `update` message) but not a fully general Transport.

  KEY-REPRESENTATION CAVEAT (discovered live, cositos-ex2.5). clojupyter parses ALL inbound
  Jupyter message content -- including a frontend's comm_msg `data`/`state` -- into
  keyword-keyed Clojure maps (its own internal convention; see `current-context`'s
  `:req-message` in probe/README.md, which is keyword-keyed throughout). cositos' core
  and wire fixtures use STRING keys (matching JSON / anywidget's JS side). Left
  unreconciled, comm-atom's internal state atom accumulates BOTH representations of the
  same field after any inbound update (`\"count\"` from our own writes, plus a *separate*
  `:count` from the frontend's merge) -- a real, silent state-corruption bug, not just an
  API nuisance. This namespace keywordizes state on the way IN to comm-atom (`open!`,
  `send-state!`) and stringifies it on the way OUT (`on-update!`), so callers only ever
  see/pass the STRING-keyed convention every other cositos backend uses; comm-atom's
  internal atom stays consistently keyword-keyed throughout, matching clojupyter's own
  parsing.

  ASYNC WATCH CAVEAT. `comm-atom` is backed by a Clojure *agent* (`agentfld` in the jar's
  private fields), so `comm-atom/watch` notifications are asynchronous and NOT
  distinguished by direction: a watch fires identically whether the state changed because
  of an inbound frontend `comm_msg` or because *this process* called `send-state!`. A
  naive watch handler that reacts unconditionally would echo its own sends back out,
  looping forever (this is exactly the bug hit -- and fixed -- while confirming the crack
  in cositos-059.9). `on-update!` below guards against this by predicting the merged
  value our own `send-state!` calls will produce and skipping the watch notification when
  it matches (a best-effort value comparison, not a synchronization primitive -- a
  colliding real inbound update is possible in principle, if astronomically unlikely for
  real widget state; a more likely gap is two back-to-back `send-state!` calls before the
  first's watch notification fires, which clobbers `pending` and lets the first echo
  through as if it were a genuine inbound update -- fine for a single-writer counter demo,
  worth a real mailbox/queue if this namespace ever needs concurrent local writers)."
  (:require [clojupyter.state :as state]
            [clojupyter.kernel.comm-atom :as comm-atom]
            [clojure.walk :as walk]
            [cositos.core :as core]))

(def target-name
  "The Jupyter comm target every ipywidgets-protocol widget opens against."
  "jupyter.widget")

(defn- current-jup+req
  "Pull :jup + :req-message off clojupyter's current-context (the crack). Throws with a
  clear message if called outside a running clojupyter cell, where current-context is
  empty and the crack has nothing to chain into."
  []
  (let [ctx (state/current-context)
        jup (:jup ctx)
        req (:req-message ctx)]
    (when (or (nil? jup) (nil? req))
      (throw (ex-info
              (str "cositos.clojupyter-transport/open! must run inside a live clojupyter "
                   "cell: current-context is missing :jup/:req-message outside cell "
                   "execution (see probe/README.md \"clojupyter comm surface\")")
              {:current-context ctx})))
    [jup req]))

(defrecord ClojupyterTransport [comm-atom pending])

(defn open!
  "Open a comm for `initial-state` (a plain state map, e.g. {\"_esm\" ... \"count\" 0})
  from inside a running clojupyter cell. Returns a ClojupyterTransport. `initial-state` is
  run through cositos.core/build-comm-open first so the frontend sees the same
  anywidget-enriched state (_model_module, AnyModel/AnyView, etc.) every other backend
  sends -- comm-atom/create-and-insert then wraps it in the standard
  {\"state\" ..., \"buffer_paths\" []} comm_open envelope itself."
  [initial-state]
  (let [[jup req] (current-jup+req)
        comm-id (str (java.util.UUID/randomUUID))
        [data] (core/build-comm-open initial-state)
        merged-state (get data "state")
        ca (comm-atom/create-and-insert jup req target-name comm-id (walk/keywordize-keys merged-state))]
    (->ClojupyterTransport ca (atom nil))))

(defn send-state!
  "Merge `delta` into the widget's frontend-visible state and broadcast the update
  (comm-atom/state-update!, which merges server-side and pushes the resulting full state
  as a standard `update` comm_msg). Records the predicted merged value so `on-update!`
  can recognize and skip this send's own watch notification."
  [transport delta]
  (let [kw-delta (walk/keywordize-keys delta)]
    (reset! (:pending transport) kw-delta)
    (comm-atom/state-update! (:comm-atom transport) kw-delta)))

(defn on-update!
  "Register `handler` (a fn of one arg, the new full state map) to run when the FRONTEND
  sends an inbound `update`. Filters out the notification caused by our own `send-state!`
  calls (see the ASYNC WATCH CAVEAT in the namespace docstring): comm-atom/watch cannot
  distinguish direction, so this compares the observed delta against what send-state! most
  recently predicted and skips a match once."
  [transport handler]
  (comm-atom/watch (:comm-atom transport) ::clojupyter-transport
    (fn [_key _ref _old new-state]
      (let [expected @(:pending transport)]
        (if (and (some? expected) (= expected (select-keys new-state (keys expected))))
          (reset! (:pending transport) nil)
          (handler (walk/stringify-keys new-state)))))))

(def widget-view-mimetype
  "The anywidget/ipywidgets mimetype a widget-view display bundle carries."
  "application/vnd.jupyter.widget-view+json")

(defn widget-view
  "The widget-view mimebundle value for `transport`, referencing the comm it opened. Put
  `(display/render-mime widget-view-mimetype (widget-view transport))` as a cell's last
  expression to render the widget live -- clojupyter has no `_repr_mimebundle_`-style
  auto-display hook for arbitrary types the way Python/Julia's cositos ports register one,
  so this must be called explicitly (see clojure/dev/cositos/clojupyter_demo.clj)."
  [transport]
  {"version_major" core/protocol-version-major
   "version_minor" core/protocol-version-minor
   "model_id" (comm-atom/comm-id (:comm-atom transport))})
