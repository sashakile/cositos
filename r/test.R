# Fixture-conformance tests for the R protocol core. Dependency-free: base R + jsonlite.
# Run:  Rscript test.R   (or from the repo root:  mise run r-test)

source("core.R")

FIXTURES_DIR <- "../fixtures"
load_fixture <- function(name) {
  fromJSON(file.path(FIXTURES_DIR, paste0(name, ".json")), simplifyVector = FALSE)
}

# Recursive JSON equality, order-insensitive for objects and tolerant of numeric type.
json_equal <- function(a, b) {
  if (is.list(a) && is.list(b) && !is.raw(a) && !is.raw(b)) {
    na <- names(a)
    nb <- names(b)
    if (!is.null(na) || !is.null(nb)) {
      if (!setequal(na, nb)) return(FALSE)
      return(all(vapply(na, function(k) json_equal(a[[k]], b[[k]]), logical(1))))
    }
    if (length(a) != length(b)) return(FALSE)
    if (length(a) == 0L) return(TRUE)
    return(all(vapply(seq_along(a), function(i) json_equal(a[[i]], b[[i]]), logical(1))))
  }
  if (is.null(a) && is.null(b)) return(TRUE)
  if (is.null(a) || is.null(b)) return(FALSE)
  if (length(a) != length(b)) return(FALSE)
  all(a == b)
}

float32_le <- function(xs) writeBin(as.double(xs), raw(), size = 4L, endian = "little")
b64 <- function(buffers) vapply(buffers, base64_enc, character(1))

# ---- tiny assertion harness ----
.failures <- 0L
.count <- 0L
check <- function(cond, msg) {
  .count <<- .count + 1L
  if (!isTRUE(cond)) {
    .failures <<- .failures + 1L
    cat(sprintf("  FAIL: %s\n", msg))
  }
}
expect_error <- function(expr, msg) {
  check(inherits(try(force(expr), silent = TRUE), "try-error"), msg)
}

# ---- message-builder conformance ----
fx <- load_fixture("comm_open")
r <- build_comm_open(list("_esm" = "export default { render() {} }", "value" = 0))
check(json_equal(fx$data, r$data), "comm_open data matches fixture")
check(identical(unlist(fx$buffers_b64), b64(r$buffers)) || (length(fx$buffers_b64) == 0 && length(r$buffers) == 0), "comm_open buffers match")
check(json_equal(fx$metadata, r$metadata), "comm_open metadata matches fixture")

fx <- load_fixture("update")
r <- build_update(list("value" = 42))
check(json_equal(fx$data, r$data), "update data matches fixture")
check(length(r$buffers) == 0 && length(fx$buffers_b64) == 0, "update has no buffers")

fx <- load_fixture("update_nested_buffer")
r <- build_update(list("img" = list("bytes" = charToRaw("PNGDATA")), "shape" = list(1L, 1L)))
check(json_equal(fx$data, r$data), "update_nested_buffer data matches fixture")
check(identical(unlist(fx$buffers_b64), b64(r$buffers)), "update_nested_buffer buffers match")

fx <- load_fixture("custom")
check(json_equal(fx$data, build_custom(list("event" = "click", "n" = 3))), "custom matches fixture")

# ---- inbound parsing ----
m <- parse_message(list("method" = "update", "state" = list("a" = 1), "buffer_paths" = list()))
check(m$type == "update" && json_equal(m$state, list("a" = 1)), "parse update")
check(parse_message(list("method" = "request_state"))$type == "request_state", "parse request_state")
check(parse_message(list("method" = "custom", "content" = 42))$content == 42, "parse custom")
check(parse_message(list("method" = "bogus"))$type == "ignored", "parse ignores unknown method")
check(parse_message(list())$type == "ignored", "parse ignores missing method")

# ---- buffer split / merge ----
blob <- charToRaw("AB")
r <- remove_buffers(list("n" = 1, "x" = list("ar" = blob), "xs" = list(blob, 2)))
check(json_equal(r$stripped, list("n" = 1, "x" = list(), "xs" = list(NULL, 2))), "buffers stripped shape")
check(json_equal(r$paths, list(list("x", "ar"), list("xs", 0L))), "buffer paths (0-based)")
restored <- put_buffers(r$stripped, r$paths, r$buffers)
check(identical(restored[["x"]][["ar"]], blob), "restored nested map buffer")
check(identical(restored[["xs"]][[1]], blob), "restored list-slot buffer")

# ---- buffer-split edge cases: cycle detection and depth capping ----
# R's copy-on-write semantics make self-referential lists impossible through normal means
# (lists are always copied on mutation), so cycle detection is a no-op guard.

# Deep nesting must raise a clear error, not stack-overflow.
expect_error({
  state <- list()
  for (i in 1:2000) state <- list(n = state)
  remove_buffers(state)
}, "depth capping raises error")

# Shared acyclic subtrees (DAG) are fine.
shared <- list(v = 1L)
state <- list(a = shared, b = shared)
r <- remove_buffers(state)
check(json_equal(r$stripped, list(a = list(v = 1L), b = list(v = 1L))), "DAG not misreported as cycle")

# ---- serialization: dump/load_document vs widget-state.json ----
widget_state_entries <- function() {
  list(
    list("box", list(
      "_esm" = "export default { render({model, el}) { /* VBox */ } }",
      "children" = list("IPY_MODEL_plot")
    )),
    list("plot", list(
      "_esm" = "export default { render({model, el}) { /* float32 plot */ } }",
      "shape" = list(3L), "dtype" = "float32", "data" = float32_le(c(1.5, 2.5, -3.0))
    ))
  )
}
fx <- load_fixture("widget-state")
check(json_equal(fx, dump_document(widget_state_entries())), "dump_document reproduces fixture")

mr <- dump_model(list("plot", list(
  "_esm" = "e", "shape" = list(3L), "dtype" = "float32", "data" = float32_le(c(1.5, 2.5, -3.0))
)))
buf <- mr[[2]]$buffers[[1]]
check(json_equal(buf$path, list("data")), "buffer record path")
check(buf$encoding == "base64", "buffer record encoding")
check(buf$data == "AADAPwAAIEAAAEDA", "buffer record base64 matches fixture")

loaded <- load_document(load_fixture("widget-state"))
by_id <- list()
for (e in loaded) by_id[[e[[1]]]] <- e[[2]]
check(setequal(vapply(loaded, function(e) e[[1]], character(1)), c("box", "plot")), "load ids")
check(json_equal(by_id[["box"]][["children"]], list("IPY_MODEL_plot")), "composition ref survives")
check(identical(by_id[["plot"]][["data"]], float32_le(c(1.5, 2.5, -3.0))), "float32 buffer raw bytes")

# round-trip on a buffer-free document
entries <- list(list("box", list("children" = list("IPY_MODEL_child"))), list("child", list("value" = 42)))
doc <- dump_document(entries)
check(json_equal(doc, dump_document(load_document(doc))), "buffer-free round-trip law")

# validation
expect_error(dump_document(list(list("", list("value" = 1)))), "reject empty model_id")
expect_error(dump_document(list(list("dup", list("value" = 1)), list("dup", list("value" = 2)))), "reject duplicate model_id")
expect_error(
  load_model(list("m", list("state" = list("data" = NULL), "buffers" = list(list("path" = list("data"), "encoding" = "hex", "data" = "00"))))),
  "reject non-base64 encoding"
)

cat(sprintf("\nRan %d checks, %d failures.\n", .count, .failures))
if (.failures > 0L) quit(status = 1L)
