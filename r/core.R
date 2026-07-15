# Cositos protocol core (R port) --- pure logic, no kernel/transport code.
#
# Binding-free anywidget-style backend core for an R Jupyter kernel (IRkernel). Builds and
# parses ipywidgets widget-messaging protocol v2.1.0 messages, performs binary-buffer
# split/merge (v2 nested rules), and serializes widget state to the Widget State JSON
# schema v2. Certified against the shared golden fixtures in ../fixtures/*.json.
#
# Conventions: state is a named list (JSON object); arrays are unnamed lists; binary values
# are R `raw` vectors. buffer_paths are lists of segments: string map keys and 0-based
# integer list indices (the wire convention).

library(jsonlite)

PROTOCOL_VERSION_MAJOR <- 2L
PROTOCOL_VERSION_MINOR <- 1L
PROTOCOL_VERSION <- "2.1.0"

ANYWIDGET_MODULE_VERSION <- "~0.11.*"

# Widget State JSON schema version (distinct from the protocol version 2.1.0).
STATE_VERSION_MAJOR <- 2L
STATE_VERSION_MINOR <- 0L

immutable_fields <- function(version = ANYWIDGET_MODULE_VERSION) {
  list(
    "_model_module" = "anywidget",
    "_model_name" = "AnyModel",
    "_model_module_version" = version,
    "_view_module" = "anywidget",
    "_view_name" = "AnyView",
    "_view_module_version" = version,
    "_view_count" = NULL
  )
}

# ---- buffer split / merge (protocol v2 nested rules) ----

MAX_DEPTH <- 500L

is_binary <- function(x) is.raw(x)
is_object <- function(x) is.list(x) && !is.null(names(x))
is_array <- function(x) is.list(x) && is.null(names(x))
is_container <- function(x) is.list(x) && !is.raw(x)

# Get a unique identifier for an R object's reference (memory address-like).
# Uses tracemem's return value (a hex address string) which is unique per reference.
# suppressWarnings handles the case where the object is already traced.
.obj_id <- function(x) suppressWarnings(tracemem(x))

# Recurse into objects/arrays, extracting binary values. Returns a list(stripped, paths,
# buffers), threading paths/buffers through. Binary at an object key removes the key; at an
# array index it becomes null.
# Detects cyclic references (via object identity) and caps nesting at MAX_DEPTH, both
# raising a clear error rather than stack-overflowing.
.separate <- function(sub, path, paths, buffers, ancestors = list(), depth = 0L) {
  if (!is_container(sub)) {
    return(list(stripped = sub, paths = paths, buffers = buffers))
  }
  if (depth > MAX_DEPTH) {
    stop(sprintf("state nesting exceeds %d levels at path %s", MAX_DEPTH,
      paste(sapply(path, deparse), collapse = ", ")))
  }
  addr <- .obj_id(sub)
  for (a in ancestors) {
    if (identical(a, addr)) {
      stop(sprintf("cyclic reference detected in state at path %s",
        paste(sapply(path, deparse), collapse = ", ")))
    }
  }
  ancestors <- c(ancestors, list(addr))

  if (is_object(sub)) {
    out <- list()
    for (k in names(sub)) {
      v <- sub[[k]]
      seg <- c(path, list(k))
      if (is_binary(v)) {
        paths[[length(paths) + 1L]] <- seg
        buffers[[length(buffers) + 1L]] <- v
      } else if (is_container(v)) {
        r <- .separate(v, seg, paths, buffers, ancestors, depth + 1L)
        out[[k]] <- r$stripped
        paths <- r$paths
        buffers <- r$buffers
      } else {
        out[k] <- list(v) # single-bracket preserves a NULL value (e.g. _view_count)
      }
    }
    list(stripped = out, paths = paths, buffers = buffers)
  } else if (is_array(sub)) {
    out <- list()
    for (i in seq_along(sub)) {
      v <- sub[[i]]
      seg <- c(path, list(i - 1L)) # 0-based wire index
      if (is_binary(v)) {
        out[i] <- list(NULL)
        paths[[length(paths) + 1L]] <- seg
        buffers[[length(buffers) + 1L]] <- v
      } else if (is_container(v)) {
        r <- .separate(v, seg, paths, buffers, ancestors, depth + 1L)
        out[[i]] <- r$stripped
        paths <- r$paths
        buffers <- r$buffers
      } else {
        out[i] <- list(v)
      }
    }
    list(stripped = out, paths = paths, buffers = buffers)
  } else {
    list(stripped = sub, paths = paths, buffers = buffers)
  }
}

remove_buffers <- function(state) {
  r <- .separate(state, list(), list(), list())
  list(stripped = r$stripped, paths = r$paths, buffers = r$buffers)
}

.put_one <- function(obj, path, buf) {
  key <- path[[1]]
  idx <- if (is.numeric(key)) as.integer(key) + 1L else key
  if (length(path) == 1L) {
    obj[[idx]] <- buf
  } else {
    obj[[idx]] <- .put_one(obj[[idx]], path[-1], buf)
  }
  obj
}

put_buffers <- function(state, paths, buffers) {
  for (i in seq_along(paths)) {
    state <- .put_one(state, paths[[i]], buffers[[i]])
  }
  state
}

# ---- message builders ----

build_comm_open <- function(state, anywidget_version = ANYWIDGET_MODULE_VERSION) {
  full <- modifyList(immutable_fields(anywidget_version), state)
  r <- remove_buffers(full)
  list(
    data = list(state = r$stripped, buffer_paths = r$paths),
    buffers = r$buffers,
    metadata = list(version = PROTOCOL_VERSION)
  )
}

build_update <- function(state) {
  r <- remove_buffers(state)
  list(
    data = list(method = "update", state = r$stripped, buffer_paths = r$paths),
    buffers = r$buffers
  )
}

build_custom <- function(content) {
  list(method = "custom", content = content)
}

# ---- inbound parsing ----

parse_message <- function(data) {
  method <- data[["method"]]
  if (identical(method, "update")) {
    list(
      type = "update",
      state = if ("state" %in% names(data)) data[["state"]] else list(),
      buffer_paths = if ("buffer_paths" %in% names(data)) data[["buffer_paths"]] else list()
    )
  } else if (identical(method, "request_state")) {
    list(type = "request_state")
  } else if (identical(method, "custom")) {
    list(type = "custom", content = data[["content"]])
  } else {
    # Unknown/missing method is ignored, not rejected (forward-compat, cositos-dow).
    list(type = "ignored", method = method)
  }
}

# ---- serialization: widget-state JSON schema v2 (dump/load) ----

.get_or <- function(state, key, default) {
  if (key %in% names(state)) state[[key]] else default
}

.decode_buffer <- function(entry) {
  if (!identical(entry[["encoding"]], "base64")) {
    stop(sprintf(
      "Unsupported buffer encoding: %s (expected 'base64')", deparse(entry[["encoding"]])
    ))
  }
  base64_dec(entry[["data"]])
}

dump_model <- function(entry, anywidget_version = ANYWIDGET_MODULE_VERSION) {
  model_id <- entry[[1]]
  state <- entry[[2]]
  r <- remove_buffers(state)
  record <- list(
    model_name = .get_or(state, "_model_name", "AnyModel"),
    model_module = .get_or(state, "_model_module", "anywidget"),
    model_module_version = .get_or(state, "_model_module_version", anywidget_version),
    state = r$stripped
  )
  if (length(r$buffers) > 0L) {
    record[["buffers"]] <- lapply(seq_along(r$buffers), function(i) {
      list(path = r$paths[[i]], encoding = "base64", data = base64_enc(r$buffers[[i]]))
    })
  }
  list(model_id, record)
}

load_model <- function(item) {
  model_id <- item[[1]]
  record <- item[[2]]
  state <- record[["state"]]
  entries <- if ("buffers" %in% names(record)) record[["buffers"]] else list()
  paths <- lapply(entries, function(e) e[["path"]])
  buffers <- lapply(entries, .decode_buffer)
  list(model_id, put_buffers(state, paths, buffers))
}

dump_document <- function(entries, anywidget_version = ANYWIDGET_MODULE_VERSION) {
  state <- list()
  for (entry in entries) {
    mr <- dump_model(entry, anywidget_version)
    model_id <- mr[[1]]
    record <- mr[[2]]
    if (is.null(model_id) || !nzchar(model_id)) {
      stop("model_id must be a non-empty string (it is the document key)")
    }
    if (model_id %in% names(state)) {
      stop(sprintf("duplicate model_id %s: document keys must be unique", deparse(model_id)))
    }
    state[[model_id]] <- record
  }
  list(
    version_major = STATE_VERSION_MAJOR,
    version_minor = STATE_VERSION_MINOR,
    state = state
  )
}

load_document <- function(doc) {
  st <- doc[["state"]]
  lapply(names(st), function(id) load_model(list(id, st[[id]])))
}

# ---- lifecycle types ----

.UNOPENED <- "unopened"
.OPEN <- "open"
.CLOSED <- "closed"

make_capabilities <- function(supports_receive = TRUE, supports_request_state = TRUE,
                                supports_custom = TRUE, supports_buffers = TRUE) {
  list(
    supports_receive = supports_receive,
    supports_request_state = supports_request_state,
    supports_custom = supports_custom,
    supports_buffers = supports_buffers
  )
}

.default_capabilities <- make_capabilities()

# Effect constructors
make_send <- function(msg_type, data, buffers = list(), metadata = NULL) {
  list(kind = "send", msg_type = msg_type, data = data, buffers = buffers, metadata = metadata)
}
make_listen <- function() list(kind = "listen")
make_apply_state <- function(state) list(kind = "apply_state", state = state)
make_invoke_custom <- function(content, buffers = list()) list(kind = "invoke_custom", content = content, buffers = buffers)
make_error <- function(message) list(kind = "error", message = message)

# Event constructors
make_open <- function() list(kind = "open")
make_send_state <- function(include = NULL) list(kind = "send_state", include = include)
make_send_custom <- function(content, buffers = list()) list(kind = "send_custom", content = content, buffers = buffers)
make_inbound <- function(message, buffers = list()) list(kind = "inbound", message = message, buffers = buffers)
make_close <- function() list(kind = "close")
make_comm_id_assigned <- function(id) list(kind = "comm_id_assigned", id = id)

# ---- lifecycle reducer ----

reduce <- function(phase, event, current_state, capabilities = .default_capabilities) {
  kind <- event$kind
  if (kind == "open") {
    .reduce_open(phase, current_state, capabilities)
  } else if (kind == "send_state") {
    .reduce_send_state(phase, event, current_state, capabilities)
  } else if (kind == "send_custom") {
    .reduce_send_custom(phase, event, capabilities)
  } else if (kind == "inbound") {
    .reduce_inbound(phase, event, current_state, capabilities)
  } else if (kind == "close") {
    .reduce_close(phase)
  } else if (kind == "comm_id_assigned") {
    list(.OPEN, list())
  } else {
    list(phase, list(make_error(paste("unknown event kind:", kind))))
  }
}

.reduce_open <- function(phase, current_state, capabilities) {
  if (phase == .UNOPENED || phase == .CLOSED) {
    full_state <- modifyList(immutable_fields(), current_state)
    msg <- build_comm_open(full_state)
    effects <- list(make_send("comm_open", msg$data, msg$buffers, msg$metadata))
    if (isTRUE(capabilities$supports_receive)) {
      effects <- c(effects, list(make_listen()))
    }
    list(.OPEN, effects)
  } else {
    list(.OPEN, list())
  }
}

.reduce_send_state <- function(phase, event, current_state, capabilities) {
  if (phase != .OPEN) {
    return(list(phase, list(make_error("send_state() requires an open comm; call open() first"))))
  }
  if (is.null(event$include)) {
    state <- modifyList(immutable_fields(), current_state)
  } else {
    state <- current_state[names(current_state) %in% event$include]
  }
  msg <- build_update(state)
  list(phase, list(make_send("comm_msg", msg$data, msg$buffers)))
}

.reduce_send_custom <- function(phase, event, capabilities) {
  if (phase != .OPEN) {
    return(list(phase, list(make_error("send_custom() requires an open comm; call open() first"))))
  }
  if (!isTRUE(capabilities$supports_custom)) {
    return(list(phase, list(make_error("custom messages are not supported by this transport"))))
  }
  if (!isTRUE(capabilities$supports_buffers) && length(event$buffers) > 0) {
    return(list(phase, list(make_error("buffers are not supported by this transport"))))
  }
  list(phase, list(make_send("comm_msg", build_custom(event$content), event$buffers)))
}

.reduce_inbound <- function(phase, event, current_state, capabilities) {
  if (phase != .OPEN) {
    return(list(phase, list()))
  }
  msg <- parse_message(event$message)
  if (identical(msg$type, "update")) {
    state <- msg$state
    if (length(msg$buffer_paths) > 0) {
      state <- put_buffers(state, msg$buffer_paths, event$buffers)
    }
    list(phase, list(make_apply_state(state)))
  } else if (identical(msg$type, "request_state")) {
    if (!isTRUE(capabilities$supports_request_state)) {
      return(list(phase, list()))
    }
    .reduce_send_state(phase, make_send_state(), current_state, capabilities)
  } else if (identical(msg$type, "custom")) {
    list(phase, list(make_invoke_custom(msg$content, event$buffers)))
  } else {
    list(phase, list())
  }
}

.reduce_close <- function(phase) {
  if (phase == .OPEN) {
    list(.CLOSED, list(make_send("comm_close", list())))
  } else {
    list(phase, list())
  }
}

`%||%` <- function(a, b) if (is.null(a)) b else a

