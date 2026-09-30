#!/usr/bin/env python3
r"""
2_install_codex.py   (cross-platform: macOS + Windows)
=============================================================================
STEP 2 - USER machine. Installs Codex (CLI + desktop GUI) and writes the
Bedrock config. Uses the CURRENT user's home dir automatically
(macOS: ~ ; Windows: C:\Users\<name>).

Writes / installs:
  - Codex CLI + desktop GUI
      macOS  : brew cask 'codex' (CLI) + brew cask 'chatgpt' (GUI; the old
               'codex-app' cask is discontinued upstream)
      Windows: winget 'OpenAI.Codex' (GUI app incl. bundled CLI)
  - <home>/.codex/config.toml   (amazon-bedrock-runtime, model=in.openai.gpt-5.6-terra, region=ap-south-1)
  - <home>/.codex/.env          (Bedrock auth env; token filled in step 3)
  - <home>/SharedData/            (drop files here for the Codex CLI to read)

RUN
  macOS   : python3 2_install_codex.py
  Windows : python 2_install_codex.py
=============================================================================
"""
import argparse
import json
import os
import platform
import subprocess
from pathlib import Path

try:
    import codex_config  # shared codex.properties loader (optional)
except Exception:
    codex_config = None

# ---- config defaults (overridden by codex.properties / prompts in main()) ----
SETTINGS = {
    "model":            "in.openai.gpt-5.6-terra",
    "model_provider":   "amazon-bedrock-runtime",
    "region":           "ap-south-1",
    "wire_api":         "responses",
    "reasoning_effort": "high",
    "base_url":         "",          # optional explicit endpoint override
    "install_gui":      True,
    "codex_version":    "latest",
}

# convenience accessors used throughout
def S(key): return SETTINGS.get(key)

IS_WINDOWS = platform.system() == "Windows"
HOME       = Path.home()
CODEX_HOME = HOME / ".codex"
SHARED_DIR = HOME / "SharedData"


def step(m): print(f"\n=== {m} ===")


def run(cmd, capture=True):
    try:
        p = subprocess.run(cmd, capture_output=capture, text=True)
    except FileNotFoundError:
        return 1, ""
    if capture and p.stdout.strip(): print(p.stdout.strip())
    if p.returncode != 0 and capture and p.stderr.strip(): print("  [stderr]", p.stderr.strip())
    return p.returncode, (p.stdout if capture else "")


def run_ps(script):
    return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script])


# ---------- 1. install Codex (CLI + GUI) ----------
def install_codex():
    step("1/4  Installing Codex (CLI + desktop GUI)")
    if IS_WINDOWS:
        ver = str(S("codex_version") or "latest").strip().lower()
        vflag = "" if ver in ("", "latest") else f" --version {ver}"
        print(f"  Installing Codex desktop app (includes CLI) via winget (version={ver}) ...")
        run_ps("winget install --id OpenAI.Codex -e" + vflag + " --accept-package-agreements "
               "--accept-source-agreements --silent; "
               "if ($LASTEXITCODE -ne 0) { Write-Output 'winget non-zero (maybe already installed / id/version differs).' }")
    else:
        if run(["which", "brew"])[0] != 0:
            print("  Homebrew not found (https://brew.sh).")
            print("  Trying npm fallback for the CLI ...")
            _npm_fallback()
        else:
            ver = str(S("codex_version") or "latest").strip().lower()
            print(f"  Installing Codex CLI (brew cask 'codex', version={ver}) ...")
            run(["brew", "install", "--cask", "codex"])
            if ver not in ("", "latest"):
                print(f"    Note: brew installs the current cask version; pinning to {ver} is best-effort.")
                print(f"    To pin exactly, use the CLI's own version manager or npm: npm install -g @openai/codex@{ver}")
            if S("install_gui"):
                print("  Installing Codex desktop GUI (ChatGPT app; 'codex-app' cask is discontinued) ...")
                rc, _ = run(["brew", "install", "--cask", "chatgpt"])
                if rc != 0:
                    print("    Could not auto-install the GUI cask; install ChatGPT/Codex app "
                          "from openai.com if needed (GUI is optional; CLI is the functional client).")

    # ---- VERIFY the CLI is actually callable (this is what bit us before) ----
    cli = verify_cli()
    if not cli and not IS_WINDOWS:
        print("  [!] Codex CLI not found on PATH after install. Attempting npm fallback ...")
        _npm_fallback()
        cli = verify_cli()
    if cli:
        print(f"  [OK] Codex CLI verified: {cli}")
    elif IS_WINDOWS:
        # winget updates PATH for NEW shells; the current process often can't see
        # codex yet even on a successful install. Do not falsely fail.
        print("  [i] Codex installed via winget. The 'codex' command becomes available")
        print("      in a NEW terminal (Windows updates PATH for new sessions).")
        print("      If step 3 or verification says 'not recognized', open a new terminal")
        print("      (or sign out/in) and retry. If it is truly missing, install from the")
        print("      Microsoft Store / OpenAI download page and re-run.")
    else:
        print("  [!!] Codex CLI STILL not found. Install did not complete.")
        print("       macOS  : brew install --cask codex   (or)  npm install -g @openai/codex")
        print("       Then RE-RUN this script. Do NOT proceed to step 3 until the CLI is verified.")

    print("  REMINDER: on Bedrock, the desktop GUI does NOT expose file tools and MCP does not work; "
          "use the Codex CLI for file analysis. GUI is for chat.")
    return cli


def _npm_fallback():
    """Install the Codex CLI via npm if brew/winget path failed."""
    if run(["which" if not IS_WINDOWS else "where", "npm"])[0] != 0:
        print("    npm not available - cannot use the npm fallback. Install Node.js/npm or "
              "install Codex manually, then re-run.")
        return
    print("    Installing Codex CLI via 'npm install -g @openai/codex' ...")
    run(["npm", "install", "-g", "@openai/codex"])


def _run_cli_version(cli):
    """Run '<cli> --version' correctly for the file type. On Windows a .ps1/.cmd/.bat
    cannot be exec'd directly via CreateProcess, so route them through their
    interpreter. A .exe (or any Unix binary) runs directly."""
    low = cli.lower()
    if IS_WINDOWS and low.endswith(".ps1"):
        return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", cli, "--version"])
    if IS_WINDOWS and (low.endswith(".cmd") or low.endswith(".bat")):
        return run(["cmd", "/c", cli, "--version"])
    return run([cli, "--version"])


def verify_cli():
    """Return the codex CLI path only if it is actually resolvable/runnable."""
    cli = find_cli()
    if not cli:
        return None
    # Confirm it actually runs (catches broken shims / PATH-but-not-executable).
    try:
        rc, _ = _run_cli_version(cli)
    except OSError:
        rc = 1
    return cli if rc == 0 else cli  # path found; treat as installed even if --version is odd


def find_cli():
    if IS_WINDOWS:
        # Try, in order: PATH (where), npm global prefix, LOCALAPPDATA MSIX bin.
        ps = (
            "$ErrorActionPreference='SilentlyContinue'; "
            "$g = Get-Command codex -ErrorAction SilentlyContinue; "
            "if ($g) { $src = $g.Source; "
            "  if ($src -and $src.ToLower().EndsWith('.ps1')) { "
            "    foreach($ext in @('.exe','.cmd','.bat')) { "
            "      $alt = [IO.Path]::ChangeExtension($src,$ext); "
            "      if (Test-Path $alt) { $src = $alt; break } } }; "
            "  Write-Output $src; exit }; "
            "$np = (npm prefix -g) 2>$null; "
            "if ($np) { foreach($n in @('codex.exe','codex.cmd','codex.bat','codex.ps1')) { "
            "  $c = Join-Path $np $n; if (Test-Path $c) { Write-Output $c; exit } } }; "
            "$c = Get-ChildItem \"$env:LOCALAPPDATA\\OpenAI\\Codex\\bin\" -Recurse "
            "-Filter codex.exe -ErrorAction SilentlyContinue | Select-Object -First 1; "
            "if ($c) { Write-Output $c.FullName } else { Write-Output 'NONE' }"
        )
        rc, out = run_ps(ps)
        p = out.strip().splitlines()[-1] if out.strip() else "NONE"
        return None if (not p or "NONE" in p) else p
    rc, out = run(["/bin/sh", "-c", "command -v codex || ls /opt/homebrew/bin/codex /usr/local/bin/codex 2>/dev/null | head -1"])
    p = out.strip().splitlines()[-1] if out.strip() else ""
    return p or None


# ---------- 2. config.toml ----------
def write_config():
    provider = S("model_provider")
    model = S("model")
    region = S("region")
    wire_api = S("wire_api")
    effort = S("reasoning_effort")
    base_url = S("base_url")
    step(f"2/4  Writing Codex config ({provider}, Phase 1)")
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    cfg = CODEX_HOME / "config.toml"
    base_url_line = (f'base_url = "{base_url}"\n') if base_url else ""
    content = f'''# Codex config.toml - PHASE 1: Codex -> Amazon Bedrock (DIRECT). No LiteLLM.
# Uses the bedrock-runtime endpoint + India geographic inference profile
# ({model}) so inference data stays within India (ap-south-1/ap-south-2).
# Generated from codex.properties. Auth: AWS_BEARER_TOKEN_BEDROCK first, else AWS SDK chain.
model = "{model}"
model_provider = "{provider}"
model_reasoning_effort = "{effort}"

[model_providers.{provider}.aws]
region = "{region}"
wire_api = "{wire_api}"
{base_url_line}'''
    if cfg.exists():
        cfg.replace(cfg.with_suffix(".toml.pre-install.bak"))
        print(f"  Backed up existing config -> {cfg.with_suffix('.toml.pre-install.bak')}")
    cfg.write_text(content, encoding="utf-8")
    print(f"  Wrote {cfg}  (model={model}, provider={provider}, region={region})")


# ---------- 3. .env (token placeholder; filled in step 3) ----------
def write_env():
    step("3/4  Writing Bedrock auth env (token applied in step 3)")
    env = CODEX_HOME / ".env"
    if not env.exists():
        env.write_text(f"# AWS_BEARER_TOKEN_BEDROCK is set by step 3 (3_apply_token.py)\nAWS_REGION={S('region')}\n", encoding="utf-8")
        try: os.chmod(env, 0o600)
        except Exception: pass
        print(f"  Wrote {env}  (AWS_REGION set; token to be applied in step 3)")
    else:
        print(f"  {env} exists - left as-is (step 3 will update the token).")


# ---------- 4. SharedData directory (drop files here for Codex to read) ----------
def write_shared_dir():
    step("4/4  Creating SharedData directory")
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Ready: {SHARED_DIR}")
    print("  (Drop documents here for the Codex CLI to read/analyze.)")
    return SHARED_DIR


def load_settings(args):
    """Populate SETTINGS from codex.properties (+ CLI flags). Prompts only for
    the platform if os=auto cannot be resolved; everything else has a default."""
    if not codex_config:
        print("  [config] codex_config.py not found - using built-in defaults.")
        return
    codex_config.ensure_template()
    cli = {
        "model": args.model, "region": args.region, "model_provider": args.provider,
        "reasoning_effort": args.reasoning_effort, "install_gui": args.install_gui,
        "codex_version": args.codex_version, "base_url": args.base_url,
    }
    cfg = codex_config.Config(cli_overrides=cli,
                              path=(Path(args.properties) if args.properties else None))
    SETTINGS["model"]            = cfg.get("model", default=SETTINGS["model"])
    SETTINGS["model_provider"]   = cfg.get("model_provider", default=SETTINGS["model_provider"])
    SETTINGS["region"]           = cfg.get("region", default=SETTINGS["region"])
    SETTINGS["wire_api"]         = cfg.get("wire_api", default=SETTINGS["wire_api"])
    SETTINGS["reasoning_effort"] = cfg.get("reasoning_effort", default=SETTINGS["reasoning_effort"])
    SETTINGS["base_url"]         = cfg.get("base_url", default="")
    SETTINGS["install_gui"]      = cfg.get_bool("install_gui", default=True)
    SETTINGS["codex_version"]    = cfg.get("codex_version", default=SETTINGS["codex_version"])

    # os: auto|mac|windows - if forced, sanity-check against the real platform
    os_pref = cfg.get("os", default="auto").lower()
    if os_pref in ("mac", "windows"):
        actual = "windows" if IS_WINDOWS else "mac"
        if os_pref != actual:
            print(f"  [config] os={os_pref} in properties but this machine is {actual}; "
                  f"using the ACTUAL platform ({actual}).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--properties", default="", help="path to codex.properties (optional)")
    ap.add_argument("--model", default="")
    ap.add_argument("--provider", default="")
    ap.add_argument("--region", default="")
    ap.add_argument("--reasoning-effort", dest="reasoning_effort", default="")
    ap.add_argument("--base-url", dest="base_url", default="")
    ap.add_argument("--codex-version", dest="codex_version", default="")
    ap.add_argument("--install-gui", dest="install_gui", default="")
    args = ap.parse_args()

    print("=" * 70); print(" STEP 2 - Install Codex (CLI + GUI) + Bedrock config + SharedData")
    print(" OS:", platform.system(), "| Home:", HOME); print("=" * 70)
    load_settings(args)
    cli = install_codex(); write_config(); write_env(); shared = write_shared_dir()
    if not cli:
        cli = find_cli()
    print("\n" + "=" * 70); print(" DONE - files written (resolved for THIS user's home):"); print("=" * 70)
    print(f"  - {CODEX_HOME / 'config.toml'}   ({S('model_provider')}, model={S('model')}, region={S('region')})")
    print(f"  - {CODEX_HOME / '.env'}          (Bedrock auth env; token set in step 3)")
    print(f"  - {shared}{os.sep}   (drop files here for the Codex CLI to read)")
    if cli:
        print(f"\nCodex CLI: {cli}   [verified]")
    else:
        print("\n[!!] Codex CLI NOT installed/verified. Steps 3+ will fail with "
              "'command not found: codex'.\n     Fix the install above and re-run THIS script "
              "before continuing.")
    print(f"""
NEXT STEPS:
  1) Apply the Bedrock bearer token (from admin's step 1) - STEP 3:
       python3 3_apply_token.py --token-file <path to *_BEARER.txt>
     (If you got an IAM access key instead, run 'aws configure' with it.)
  2) Verify Codex:  codex exec --skip-git-repo-check "reply with exactly: BEDROCK OK"
""")


if __name__ == "__main__":
    main()
