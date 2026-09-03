# claude.exe shim

Tiny Windows wrapper that lets Rust's `Command::new("claude")` find the
npm-installed Claude Code CLI.

**Why this exists:** the npm install ships `claude.cmd` (a Windows batch
wrapper) and `claude` (a bash shell-script, no `.exe` header). Rust's
`std::process::Command::new("claude")` on Windows calls `CreateProcessW`,
which only launches `.exe` binaries — it does NOT resolve `.cmd`/`.bat`
the way `cmd.exe` does. So OpenFang's `claude_code` driver
([vibemind-os/openfang/crates/openfang-runtime/src/drivers/claude_code.rs:118](../../vibemind-os/openfang/crates/openfang-runtime/src/drivers/claude_code.rs))
fails with "Claude Code CLI not found" even though `claude.cmd` is on PATH.

This shim is a 30-line Rust program compiled to `claude.exe` that forwards
to `cmd /c claude.cmd <args>`. Drop it into any PATH entry that is searched
*before* the npm dir (e.g. `C:\Users\User\bin`) and the driver picks it up.

## Build & deploy

```powershell
cd scripts/claude_shim
cargo build --release
Copy-Item target/release/claude.exe C:\Users\User\bin\claude.exe -Force
```

The target path is hard-coded in `src/main.rs` (`C:\Users\User\AppData\Roaming\npm\claude.cmd`).
Adjust it there if your npm global dir differs.

## Verify

```powershell
C:\Users\User\bin\claude.exe --version
# expected: 2.1.62 (Claude Code)
```
