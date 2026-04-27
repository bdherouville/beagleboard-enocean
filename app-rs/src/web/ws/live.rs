//! `/ws/live` — pushes ERP1 telegrams to the live inspector page.

use axum::extract::State;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::response::IntoResponse;
use chrono::Utc;
use serde_json::json;

use crate::web::AppState;

pub async fn ws_live(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(mut ws: WebSocket, state: AppState) {
    let mut sub = state.controller.subscribe();
    loop {
        let erp1 = match sub.recv().await {
            Ok(e) => e,
            Err(_) => return, // controller stopped or lagged
        };
        let msg = json!({
            "type": "telegram",
            "ts": Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
            "payload": {
                "rorg":    format!("0x{:02x}", erp1.rorg),
                "sender":  format!("0x{:08x}", erp1.sender_id),
                "status":  format!("0x{:02x}", erp1.status),
                "dbm":     erp1.dbm,
                "payload": erp1.payload.iter().map(|b| format!("{:02x}", b)).collect::<String>(),
            },
        });
        if ws.send(Message::Text(msg.to_string().into())).await.is_err() {
            return;
        }
    }
}
