//! `AppState` — the shared, cheaply-cloneable bundle of services that every
//! axum handler depends on.

use std::sync::Arc;

use crate::transport::Controller;
use crate::web::templates::Templates;

#[derive(Clone)]
pub struct AppState {
    pub controller: Arc<Controller>,
    pub templates: Arc<Templates>,
}

impl AppState {
    pub fn new(controller: Arc<Controller>, templates: Templates) -> Self {
        Self {
            controller,
            templates: Arc::new(templates),
        }
    }
}
