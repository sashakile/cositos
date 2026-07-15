## ADDED Requirements

### Requirement: Full State Send Includes Immutable Identity Fields
When `send_state` performs a full state send (no `include` filter, equivalent to processing an inbound `request_state`), the resulting `update` message SHALL include the seven immutable anywidget identity fields in its state payload: `_model_module`, `_model_name`, `_model_module_version`, `_view_module`, `_view_name`, `_view_module_version`, and `_view_count`.

The identity fields act as a "lifeline" for the anywidget frontend — they allow the frontend `WidgetManager` to reconstruct a view class after JupyterLab reloads the page without restarting the kernel (the `_loadFromKernelModels` recovery path, which sends `request_state` and builds a fresh model purely from the `update` reply it receives).

#### Scenario: Full send_state includes model identity
- **GIVEN** an open widget
- **WHEN** `send_state(w)` is called with no `include` argument
- **THEN** the resulting `update` message's `state` SHALL contain `_model_module` set to `"anywidget"`
- **AND** `_model_name` SHALL be set to `"AnyModel"`
- **AND** `_model_module_version` SHALL be set to the configured anywidget module version

#### Scenario: Full send_state includes view identity
- **GIVEN** an open widget
- **WHEN** `send_state(w)` is called with no `include` argument
- **THEN** the resulting `update` message's `state` SHALL contain `_view_module` set to `"anywidget"`
- **AND** `_view_name` SHALL be set to `"AnyView"`
- **AND** `_view_module_version` SHALL be set to the configured anywidget module version

#### Scenario: Explicit include skips identity merge
- **GIVEN** an open widget
- **WHEN** `send_state(w; include=["value"])` is called
- **THEN** the resulting `update` message's `state` SHALL contain only the `"value"` key
- **AND** SHALL NOT contain any of the immutable identity fields

#### Scenario: RequestState handler produces identity-bearing reply
- **GIVEN** an open widget with a listener for incoming messages
- **WHEN** the widget receives a `request_state` message
- **THEN** the handler SHALL send an `update` reply whose `state` includes all seven immutable identity fields
