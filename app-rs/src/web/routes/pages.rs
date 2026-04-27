//! HTML pages + the `/api/leds` JSON endpoint.

use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{Html, IntoResponse, Json};
use minijinja::context;
use serde_json::json;

use crate::web::AppState;

pub async fn index(State(state): State<AppState>) -> impl IntoResponse {
    let info = state.controller.info().await;
    let port = state.controller.port();
    let info_ctx = info_to_template_value(&info);
    match state
        .templates
        .render("index.html", context!(info => info_ctx, port => port))
    {
        Ok(html) => Html(html).into_response(),
        Err(e) => template_error(e),
    }
}

pub async fn telegrams(State(state): State<AppState>) -> impl IntoResponse {
    match state.templates.render("telegrams.html", context!()) {
        Ok(html) => Html(html).into_response(),
        Err(e) => template_error(e),
    }
}

pub async fn devices(State(state): State<AppState>) -> impl IntoResponse {
    // R4 will populate the real device list; for now the template renders
    // its empty-state copy when given no devices.
    match state
        .templates
        .render("devices.html", context!(devices => Vec::<String>::new()))
    {
        Ok(html) => Html(html).into_response(),
        Err(e) => template_error(e),
    }
}

pub async fn pair(State(state): State<AppState>) -> impl IntoResponse {
    match state.templates.render(
        "pair.html",
        context!(state => "idle", profiles => Vec::<String>::new()),
    ) {
        Ok(html) => Html(html).into_response(),
        Err(e) => template_error(e),
    }
}

pub async fn leds_api(State(_state): State<AppState>) -> impl IntoResponse {
    // R7 wires real GPIO state. Until then return a stable, well-formed
    // response so the dashboard panel renders correctly.
    Json(json!({
        "state":      { "green": false, "orange": false, "red": false },
        "gpios":      { "green": 67, "orange": 68, "red": 66 },
        "test_gpios": [66, 67, 68, 69],
    }))
}

fn template_error(e: minijinja::Error) -> axum::response::Response {
    tracing::error!("template render failed: {e}");
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        format!("template error: {e}"),
    )
        .into_response()
}

/// Project `GatewayInfo` into a minijinja-friendly nested structure that
/// matches what the `index.html` template expects.
fn info_to_template_value(info: &crate::transport::GatewayInfo) -> minijinja::Value {
    let version = info.version.as_ref().map(|v| {
        minijinja::context!(
            app_version => v.app_version.to_vec(),
            api_version => v.api_version.to_vec(),
            chip_id     => v.chip_id,
            chip_version => v.chip_version,
            description => v.description.clone(),
        )
    });
    let idbase = info.idbase.as_ref().map(|i| {
        minijinja::context!(
            base_id => i.base_id,
            remaining_writes => i.remaining_writes,
        )
    });
    minijinja::context!(
        version => version,
        idbase => idbase,
        learn_mode => info.learn_mode,
    )
}
