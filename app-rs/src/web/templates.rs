//! minijinja environment with every template baked into the binary.
//!
//! Templates are loaded via `include_str!` at compile time so the final
//! ELF is a single self-contained file — no `templates/` directory needs
//! to exist at runtime.

use minijinja::{Environment, Error, Value};

pub struct Templates {
    env: Environment<'static>,
}

impl Templates {
    pub fn new() -> Self {
        let mut env = Environment::new();

        // Custom filter `format(int)` — Python-style %x / %02x via a helper.
        // Used in templates as: `{{ "%08x" | format(sender_id) }}`.
        env.add_filter("format", filter_format);

        env.add_template("base.html", include_str!("templates/base.html"))
            .expect("base.html");
        env.add_template("index.html", include_str!("templates/index.html"))
            .expect("index.html");
        env.add_template("telegrams.html", include_str!("templates/telegrams.html"))
            .expect("telegrams.html");
        env.add_template("devices.html", include_str!("templates/devices.html"))
            .expect("devices.html");
        env.add_template(
            "device_detail.html",
            include_str!("templates/device_detail.html"),
        )
        .expect("device_detail.html");
        env.add_template("pair.html", include_str!("templates/pair.html"))
            .expect("pair.html");
        env.add_template(
            "fragments/device_row.html",
            include_str!("templates/fragments/device_row.html"),
        )
        .expect("fragments/device_row.html");

        Self { env }
    }

    pub fn render(&self, name: &str, ctx: Value) -> Result<String, Error> {
        let tmpl = self.env.get_template(name)?;
        tmpl.render(ctx)
    }
}

impl Default for Templates {
    fn default() -> Self {
        Self::new()
    }
}

/// Implements Jinja2's `format(value, *args)` -- specifically the `%08x` /
/// `%02x` patterns used in templates. Python's `"%08x" | format(N)` becomes
/// `format(N, "%08x")` semantics here; minijinja calls the filter as
/// `value | format(arg1, arg2, ...)` where `value` is the format string.
fn filter_format(spec: &str, args: Value) -> Result<String, Error> {
    // Convert the value to an integer if possible.
    let n = if let Some(i) = args.as_i64() {
        i as i128
    } else if let Some(u) = args.as_usize() {
        u as i128
    } else {
        return Err(Error::new(
            minijinja::ErrorKind::InvalidOperation,
            format!("format(): can't render {args:?} as an integer"),
        ));
    };
    // Minimal subset that the templates actually need.
    Ok(match spec {
        "%08x" => format!("{:08x}", n),
        "%02x" => format!("{:02x}", n),
        "%04x" => format!("{:04x}", n),
        "%x" => format!("{:x}", n),
        "%d" => format!("{}", n),
        other => {
            return Err(Error::new(
                minijinja::ErrorKind::InvalidOperation,
                format!("format(): unsupported spec {other:?}"),
            ));
        }
    })
}
