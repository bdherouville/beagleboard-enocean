//! axum app factory: routes + WS + static-file serving.

use axum::Router;
use axum::http::{HeaderValue, header};
use axum::response::IntoResponse;
use axum::routing::get;

use crate::web::AppState;
use crate::web::routes::pages;
use crate::web::ws::live;

/// Build the full axum `Router` for the production app. The caller wires
/// `AppState`, then runs the router with a tokio listener.
pub fn build_app(state: AppState) -> Router {
    Router::new()
        .route("/", get(pages::index))
        .route("/telegrams", get(pages::telegrams))
        .route("/devices", get(pages::devices))
        .route("/pair", get(pages::pair))
        .route("/api/leds", get(pages::leds_api))
        .route("/static/*file", get(static_file))
        .route("/ws/live", get(live::ws_live))
        .with_state(state)
}

/// Serve a baked-in static asset by path. We embed the small set of static
/// files at compile time; no runtime `templates/` or `static/` directory.
async fn static_file(
    axum::extract::Path(path): axum::extract::Path<String>,
) -> impl IntoResponse {
    let (body, content_type) = match path.as_str() {
        "app.css" => (
            &include_bytes!("static/app.css")[..],
            "text/css; charset=utf-8",
        ),
        "app.js" => (
            &include_bytes!("static/app.js")[..],
            "application/javascript; charset=utf-8",
        ),
        "leds.js" => (
            &include_bytes!("static/leds.js")[..],
            "application/javascript; charset=utf-8",
        ),
        "pair.js" => (
            &include_bytes!("static/pair.js")[..],
            "application/javascript; charset=utf-8",
        ),
        "device.js" => (
            &include_bytes!("static/device.js")[..],
            "application/javascript; charset=utf-8",
        ),
        "htmx.min.js" => (
            &include_bytes!("static/htmx.min.js")[..],
            "application/javascript; charset=utf-8",
        ),
        _ => return (axum::http::StatusCode::NOT_FOUND, "").into_response(),
    };
    (
        [(header::CONTENT_TYPE, HeaderValue::from_static(content_type))],
        body.to_vec(),
    )
        .into_response()
}
