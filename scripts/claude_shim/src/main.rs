use std::os::windows::process::CommandExt;
use std::process::{Command, exit};

const CREATE_NO_WINDOW: u32 = 0x08000000;
const TARGET: &str = r"C:\Users\User\AppData\Roaming\npm\claude.cmd";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let status = Command::new("cmd")
        .arg("/c")
        .arg(TARGET)
        .args(&args)
        .creation_flags(CREATE_NO_WINDOW)
        .status();
    match status {
        Ok(s) => exit(s.code().unwrap_or(1)),
        Err(e) => {
            eprintln!("claude-shim: failed to launch {}: {}", TARGET, e);
            exit(127);
        }
    }
}
