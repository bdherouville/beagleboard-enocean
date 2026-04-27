//! Container entry-point. Settings-driven; assembles Controller, DB, MQTT,
//! and the axum app, then runs forever. CLI subcommands for `sniff`,
//! `probe`, `reset`, `serve` are added module-by-module per the migration
//! plan.

use std::env;
use std::sync::Arc;
use std::time::Duration;

use vdsensor::transport::{Controller, FakeLink, LinkKind, SerialLink};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing();

    let args: Vec<String> = env::args().collect();
    let subcommand = args.get(1).map(String::as_str).unwrap_or("");
    let fake = args.iter().any(|a| a == "--fake");
    let port = args
        .windows(2)
        .find(|w| w[0] == "--port")
        .map(|w| w[1].clone())
        .unwrap_or_else(|| "/dev/ttyS4".to_string());

    let link = if fake {
        LinkKind::Fake(FakeLink::new(Duration::from_secs(1)))
    } else {
        LinkKind::Serial(SerialLink::new(port.clone(), 57_600))
    };
    let controller = Controller::new(link);
    controller.start().await;

    match subcommand {
        "sniff" => sniff(&controller).await?,
        "probe" => probe(&controller).await?,
        "reset" => reset(&controller).await?,
        "" | "--help" | "-h" => {
            println!(
                "vdsensor (rust) — milestones R1+R2 of the migration\n\
                 \n\
                 USAGE:\n  \
                 vdsensor <sniff|probe|reset> [--fake | --port /dev/ttyS4]\n"
            );
        }
        cmd => {
            eprintln!("unknown subcommand: {cmd}");
            std::process::exit(2);
        }
    }
    Ok(())
}

async fn sniff(c: &Arc<Controller>) -> anyhow::Result<()> {
    eprintln!("# sniffing on {} — Ctrl-C to exit", c.port());
    let mut sub = c.subscribe();
    loop {
        let erp1 = sub.recv().await?;
        println!(
            "RORG=0x{:02x} sender=0x{:08x} status=0x{:02x} dbm={:?} payload={}",
            erp1.rorg,
            erp1.sender_id,
            erp1.status,
            erp1.dbm,
            hex(&erp1.payload),
        );
    }
}

async fn probe(c: &Arc<Controller>) -> anyhow::Result<()> {
    let v = c.read_version().await?;
    let i = c.read_idbase().await?;
    println!(
        "app_version  = {}",
        v.app_version
            .iter()
            .map(|x| x.to_string())
            .collect::<Vec<_>>()
            .join(".")
    );
    println!(
        "api_version  = {}",
        v.api_version
            .iter()
            .map(|x| x.to_string())
            .collect::<Vec<_>>()
            .join(".")
    );
    println!("chip_id      = 0x{:08x}", v.chip_id);
    println!("chip_version = 0x{:08x}", v.chip_version);
    println!("description  = {:?}", v.description);
    println!(
        "idbase       = 0x{:08x} (remaining writes: {})",
        i.base_id, i.remaining_writes
    );
    Ok(())
}

async fn reset(c: &Arc<Controller>) -> anyhow::Result<()> {
    let r = c.reset().await?;
    println!("CO_WR_RESET return code = 0x{:02x}", r.return_code);
    Ok(())
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

fn init_tracing() {
    use tracing_subscriber::{EnvFilter, fmt};
    let filter = EnvFilter::try_from_env("VDSENSOR_LOG")
        .or_else(|_| EnvFilter::try_new("info"))
        .unwrap();
    fmt().with_env_filter(filter).with_target(false).init();
}
