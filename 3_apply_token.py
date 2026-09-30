#!/usr/bin/env python3
r"""
3_update_codex_token.py  (cross-platform: macOS + Windows)
=============================================================================
STEP 3 of the Codex+Bedrock provisioning bundle.  END USER runs this on their
own desktop (or admin runs it during setup).

PURPOSE
  Apply a Bedrock BEARER token (AWS_BEARER_TOKEN_BEDROCK) to the local Codex
  setup so Codex can authenticate to Bedrock:
    - Writes/updates ~/.codex/.env    (the file the desktop app reads)
    - Ensures ~/.codex/config.toml points at the amazon-bedrock provider
    - On Windows also sets the User-scope env var (for the CLI/session)

  If you provisioned an IAM ACCESS KEY instead of a bearer token, you do NOT
  use this script - run `aws configure` with that key instead (Codex then uses
  the AWS SDK credential chain).

TOKEN INPUT (choose one)
  --token-file <path>   read the token from a file (recommended; from script 2)
  --token <value>       pass the token directly (will be visible in shell history)
  (neither)             you will be prompted (hidden input)

USAGE
  python3 3_update_codex_token.py --token-file codex-bedrock-user-alice_BEARER.txt
  python  3_update_codex_token.py                      (prompts)
=============================================================================
"""
import argparse
import getpass
import os
import platform
import re
import subprocess
from pathlib import Path

try:
    import codex_config  # shared codex.properties loader (optional)
except Exception:
    codex_config = None

IS_WINDOWS = platform.system() == "Windows"
CODEX_HOME = Path.home() / ".codex"

# Settings (overridden by codex.properties / flags in main()).
SETTINGS = {
    "region":           "ap-south-1",
    "model":            "in.openai.gpt-5.6-terra",
    "model_provider":   "amazon-bedrock-runtime",
    "wire_api":         "responses",
    "reasoning_effort": "high",
    "base_url":         "",
}
def S(key): return SETTINGS.get(key)


def build_config_toml() -> str:
    provider = S("model_provider")
    model = S("model")
    region = S("region")
    wire_api = S("wire_api")
    effort = S("reasoning_effort")
    base_url = S("base_url")
    base_url_line = (f'base_url = "{base_url}"\n') if base_url else ""
    return f'''# Codex config.toml - PHASE 1: Codex -> Amazon Bedrock (direct)
# Written/kept by 3_apply_token.py. Uses the bedrock-runtime endpoint + India
# geographic inference profile so inference data stays within India.
model = "{model}"
model_provider = "{provider}"
model_reasoning_effort = "{effort}"

[model_providers.{provider}.aws]
region = "{region}"
wire_api = "{wire_api}"
{base_url_line}'''


def _read_token_file(path: str) -> str:
    raw = Path(path).expanduser().read_text(encoding="utf-8").strip()
    m = re.search(r"AWS_BEARER_TOKEN_BEDROCK\s*=\s*(\S+)", raw)
    return (m.group(1) if m else raw).strip()


def load_token(args, props: dict) -> str:
    # precedence: --token-file > --token > properties token_file >
    #             properties bearer_token > prompt
    if args.token_file:
        return _read_token_file(args.token_file)
    if args.token:
        return args.token.strip()
    if props.get("token_file"):
        print(f"  [config] reading token from token_file: {props['token_file']}")
        return _read_token_file(props["token_file"])
    if props.get("bearer_token"):
        print("  [config] using inline bearer_token from codex.properties "
              "(reminder: do not commit that file).")
        return props["bearer_token"].strip()
    return getpass.getpass("Paste the Bedrock bearer token (hidden): ").strip()


def upsert_env_line(env_path: Path, key: str, value: str):
    """Insert or replace KEY=... in the .env file, preserving other lines."""
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    out, replaced = [], False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}"); replaced = True
        else:
            out.append(ln)
    if not replaced:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _codex_cli_present() -> bool:
    """Best-effort check that the codex CLI is installed/on PATH."""
    probe = ["where", "codex"] if IS_WINDOWS else ["/bin/sh", "-c", "command -v codex"]
    try:
        return subprocess.run(probe, capture_output=True, text=True).returncode == 0
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-file")
    ap.add_argument("--token")
    ap.add_argument("--properties", default="", help="path to codex.properties (optional)")
    args = ap.parse_args()

    print("=" * 70)
    print(" STEP 3  -  Apply Bedrock bearer token to Codex")
    print("=" * 70)

    # Load properties (for token_file/bearer_token + model/region/provider).
    props = {}
    if codex_config:
        codex_config.ensure_template()
        cfg = codex_config.Config(path=(Path(args.properties) if args.properties else None))
        props = cfg.props
        SETTINGS["region"]           = cfg.get("region", default=SETTINGS["region"])
        SETTINGS["model"]            = cfg.get("model", default=SETTINGS["model"])
        SETTINGS["model_provider"]   = cfg.get("model_provider", default=SETTINGS["model_provider"])
        SETTINGS["wire_api"]         = cfg.get("wire_api", default=SETTINGS["wire_api"])
        SETTINGS["reasoning_effort"] = cfg.get("reasoning_effort", default=SETTINGS["reasoning_effort"])
        SETTINGS["base_url"]         = cfg.get("base_url", default="")

    if not _codex_cli_present():
        print("  [!] WARNING: the 'codex' CLI was not found on this machine.")
        print("      The token/config below will still be written, but verification")
        print("      ('codex exec ...') will fail with 'command not found: codex'")
        print("      until you run STEP 2 (2_install_codex.py) to install Codex.")
        print("      Continuing to write config + token now.\n")

    token = load_token(args, props)
    if not token:
        print("ERROR: no token provided."); return
    if not (token.startswith("ABSK") or token.startswith("sk-") or len(token) > 20):
        print(f"  Warning: token looks unusual (head '{token[:4]}', len {len(token)}). Continuing anyway.")

    CODEX_HOME.mkdir(parents=True, exist_ok=True)

    # 1) config.toml - keep/point at amazon-bedrock (back up if changing)
    cfg = CODEX_HOME / "config.toml"
    config_toml = build_config_toml()
    want_provider = 'model_provider = "' + S("model_provider") + '"'
    if not cfg.exists():
        cfg.write_text(config_toml, encoding="utf-8")
        print(f"  Wrote {cfg}")
    else:
        txt = cfg.read_text(encoding="utf-8")
        # Require the CORRECT provider AND model id, else rewrite (a stale
        # amazon-bedrock/mantle config or wrong model id causes 404/403).
        ok = (want_provider in txt) and (S("model") in txt)
        if not ok:
            bak = cfg.with_suffix(".toml.bak")
            cfg.replace(bak)
            cfg.write_text(config_toml, encoding="utf-8")
            print(f"  Existing config was not on {S('model_provider')} + {S('model')}; "
                  f"backed up -> {bak} and rewrote.")
        else:
            print(f"  {cfg} already targets {S('model_provider')} + {S('model')} (left as-is).")

    # 2) ~/.codex/.env  (desktop app reads this)
    env_path = CODEX_HOME / ".env"
    upsert_env_line(env_path, "AWS_BEARER_TOKEN_BEDROCK", token)
    upsert_env_line(env_path, "AWS_REGION", S("region"))
    try:
        os.chmod(env_path, 0o600)
    except Exception:
        pass
    print(f"  Updated {env_path}  (AWS_BEARER_TOKEN_BEDROCK, AWS_REGION)")

    # 3) OS-specific session/user env
    if IS_WINDOWS:
        region = S("region")
        ps_cmd = (
            '[Environment]::SetEnvironmentVariable('
            '"AWS_BEARER_TOKEN_BEDROCK","' + token + '","User"); '
            '[Environment]::SetEnvironmentVariable("AWS_REGION","' + region + '","User")'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                       capture_output=True, text=True)
        print("  Set AWS_BEARER_TOKEN_BEDROCK + AWS_REGION at Windows User scope.")
        print("  IMPORTANT: fully restart the Codex desktop app (or log off/on) so it "
              "picks up the new value.")
    else:
        rc = Path.home() / (".zshrc" if os.environ.get("SHELL", "").endswith("zsh") else ".bash_profile")
        marker = "# [codex-bedrock] token"
        existing = rc.read_text(encoding="utf-8") if rc.exists() else ""
        # replace any prior managed block, else append
        block = (f"{marker}\nexport AWS_BEARER_TOKEN_BEDROCK={token}\n"
                 f"export AWS_REGION={S('region')}\n")
        if marker in existing:
            existing = re.sub(rf"{re.escape(marker)}\n(export .*\n){{0,2}}", block, existing)
            rc.write_text(existing, encoding="utf-8")
        else:
            with open(rc, "a", encoding="utf-8") as f:
                f.write("\n" + block)
        print(f"  Added/updated export lines in {rc} (open a NEW terminal to load them).")

    print("\n" + "=" * 70)
    print(" DONE. Token applied.")
    print("=" * 70)
    print(f"""
Verify (open a NEW terminal first so env loads):
  codex exec --skip-git-repo-check "reply with exactly: BEDROCK OK"

Token head: {token[:8]}...  (len {len(token)})   [full value not shown]
Config    : {cfg}
Env file  : {env_path}

Reminder: securely delete the token file after applying it.
""")


if __name__ == "__main__":
    main()
