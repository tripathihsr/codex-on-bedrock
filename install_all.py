#!/usr/bin/env python3
r"""
install_all.py  -  MASTER installer for Codex + Amazon Bedrock (India), Phase 1
=============================================================================
Runs the bundle scripts in sequence so you can set up Codex in one shot.

  Step 0  0_setup_admin_credentials.py       (admin) configure admin AWS profile
  Step 1  1_create_codex_user_and_token.py   (admin) create IAM user + bearer token
  Step 2  2_install_codex.py                 (user)  install Codex + write config
  Step 3  3_apply_token.py                   (user)  apply the bearer token

All settings come from codex.properties (edit that ONE file). Missing values are
prompted by the individual scripts. Precedence: CLI flag > properties > prompt > default.

ROLES
  --admin      run only the admin steps (0, 1)  -> produces the *_BEARER.txt file
  --user       run only the user steps  (2, 3)  -> installs Codex on this machine
  (no flag)    run ALL steps 0-1-2-3 on this machine (single-operator setup)

OTHER FLAGS
  --properties <path>   use a specific codex.properties (else auto-discovered)
  --from <n>            resume starting at step n (0..3)
  --skip <n[,n...]>     skip specific step numbers (e.g. --skip 0)
  --yes                 assume "yes" for the master's own confirmation prompt
  --dry-run             print the exact commands without executing them

BEHAVIOUR
  - Stops immediately if any step fails, and tells you how to resume.
  - After step 1 creates the token file, step 3 is auto-pointed at it
    (via --token-file), so the hand-off is seamless in an all-in-one run.

USAGE
  python3 install_all.py                 # macOS - all steps
  python  install_all.py --user          # Windows - user steps only
  python3 install_all.py --admin --yes   # admin steps, no prompt
=============================================================================
"""
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

try:
    import codex_config
except Exception:
    codex_config = None

HERE = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"
PYEXE = sys.executable or ("python" if IS_WINDOWS else "python3")

SCRIPTS = {
    0: "0_setup_admin_credentials.py",
    1: "1_create_codex_user_and_token.py",
    2: "2_install_codex.py",
    3: "3_apply_token.py",
}
ADMIN_STEPS = [0, 1]
USER_STEPS = [2, 3]


def hr(c="="): print(c * 70)


def run_step(n, extra_args, dry_run):
    script = HERE / SCRIPTS[n]
    if not script.exists():
        print(f"  ERROR: {script.name} not found next to install_all.py.")
        return 1
    if n == 99:
        return run_bedrock_meter_config(dry_run)
    cmd = [PYEXE, str(script)] + extra_args
    print()
    hr()
    print(f" MASTER -> STEP {n}: {script.name}")
    if extra_args:
        print(f"          args: {' '.join(extra_args)}")
    hr()
    if dry_run:
        print("  [dry-run] would execute:", " ".join(cmd))
        return 0
    return subprocess.run(cmd).returncode


def resolve_token_file(props_path):
    """Best-effort: figure out the token file path step 1 will produce, so step 3
    can be pointed at it in an all-in-one run."""
    username = out_dir = ""
    if codex_config:
        cfg = codex_config.Config(path=props_path, quiet=True)
        username = cfg.get("username", default="")
        out_dir = cfg.get("out_dir", default=".")
    if not username:
        return None
    cand = (Path(out_dir) if out_dir else HERE) / f"codex-bedrock-user-{username}_BEARER.txt"
    # normalize relative to HERE if not absolute
    if not cand.is_absolute():
        cand = (HERE / cand)
    return cand


STEP_LABELS = {
    0: "Setup admin AWS profile            (admin machine)",
    1: "Create Codex user + bearer token   (admin machine)",
    2: "Install Codex UI + CLI             (user machine)",
    3: "Apply bearer token + Codex config  (user machine)",
    99: "Configure Bedrock Meter gateway    (user machine)",
}


def choose_steps_menu():
    """Interactive menu: let the operator pick which steps to run.
    Returns a sorted list of step numbers, or None if the user quits."""
    hr()
    print(" What would you like to do? Select one or more steps.")
    hr()
    for n in (0, 1, 2, 3):
        print(f"   {n} - {STEP_LABELS[n]}")
    print()
    print("   Presets:")
    print("     a - ALL steps        (0,1,2,3)  full setup on one machine")
    print("     admin - admin only   (0,1)      create user + token, then hand off")
    print("     user  - user only    (2,3)      install Codex + apply token")
    print("     q - quit")
    print()
    print(" Examples:  1        (just create user+token)")
    print("            2,3      (install + apply token on a user's laptop)")
    print("            1,2,3    (skip admin-profile setup; you already did it)")
    print()
    while True:
        raw = input(" Your choice: ").strip().lower()
        if raw in ("q", "quit", "exit"):
            return None
        if raw in ("a", "all"):
            return [0, 1, 2, 3]
        if raw == "admin":
            return [0, 1]
        if raw == "user":
            return [2, 3]
        if raw == "bm":
            return [2, 99]  # 99 = Bedrock Meter config step
        # parse comma/space separated digits
        parts = [x for x in raw.replace(",", " ").split() if x]
        try:
            nums = sorted({int(x) for x in parts})
        except ValueError:
            print("   Enter step numbers like 1,2,3 (or a/admin/user/q)."); continue
        if not nums or any(n not in (0, 1, 2, 3, 99) for n in nums):
            print("   Valid steps are 0,1,2,3,99 (99=Bedrock Meter config)."); continue
        return nums



def run_bedrock_meter_config(dry_run):
    """Step 99: Configure Codex to use Bedrock Meter gateway instead of direct Bedrock."""
    print()
    hr()
    print(" STEP 99: Configure Bedrock Meter gateway")
    hr()
    if dry_run:
        print("  [dry-run] would configure Bedrock Meter in ~/.codex/config.toml")
        return 0

    CODEX_HOME = Path.home() / ".codex"
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    cfg = CODEX_HOME / "config.toml"

    # Gather Bedrock Meter details
    print("  Bedrock Meter lets you route Codex through a governance gateway")
    print("  that provides per-user budgets, usage tracking, and admin controls.")
    print("  You need: (1) the gateway URL and (2) your bm_ API key from the admin.")
    print()

    gateway_url = ""
    while not gateway_url:
        gateway_url = input("  Bedrock Meter gateway URL (e.g. http://my-alb.ap-south-1.elb.amazonaws.com): ").strip()
        if not gateway_url:
            print("    Gateway URL is required.")

    api_key = ""
    while not api_key:
        api_key = input("  Your bm_ API key: ").strip()
        if not api_key.startswith("bm_"):
            print("    Key should start with bm_ (from the Bedrock Meter admin console).")
            api_key = ""

    model = input("  Model ID [in.openai.gpt-5.6-terra]: ").strip() or "in.openai.gpt-5.6-terra"
    effort = input("  Reasoning effort (low/medium/high) [high]: ").strip() or "high"

    # Write config.toml with Bedrock Meter custom provider
    content = f"""# Codex config.toml - Codex -> Bedrock Meter gateway -> Amazon Bedrock
# The gateway translates /v1/responses to Bedrock Converse (SigV4) and
# enforces per-user budgets. Auth: bm_ API key (bearer token to gateway).
model = "{model}"
model_provider = "bedrock-meter"
model_reasoning_effort = "{effort}"

[model_providers.bedrock-meter]
name = "Bedrock Meter Gateway"
base_url = "{gateway_url}/v1"
experimental_bearer_token = "{api_key}"
wire_api = "responses"
"""
    if cfg.exists():
        bak = cfg.with_suffix(".toml.pre-bm.bak")
        cfg.replace(bak)
        print(f"  Backed up existing config -> {bak}")
    cfg.write_text(content, encoding="utf-8")
    print(f"  Wrote {cfg}")
    print(f"    provider = bedrock-meter")
    print(f"    gateway  = {gateway_url}")
    print(f"    model    = {model}")
    print()
    print("  DONE. Restart Codex and verify it works through the gateway.")
    print("  Your usage and budget are now tracked in the Bedrock Meter admin console.")
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--admin", action="store_true", help="run only admin steps (0,1)")
    ap.add_argument("--user", action="store_true", help="run only user steps (2,3)")
    ap.add_argument("--properties", default="", help="path to codex.properties")
    ap.add_argument("--from", dest="from_step", type=int, default=0, help="resume at step n (0..3)")
    ap.add_argument("--skip", default="", help="comma-separated step numbers to skip")
    ap.add_argument("--yes", action="store_true", help="skip the master confirmation prompt")
    ap.add_argument("--dry-run", action="store_true", help="print commands without executing")
    ap.add_argument("--menu", action="store_true", help="force the interactive step-selection menu")
    args = ap.parse_args()

    hr()
    print(" CODEX + AMAZON BEDROCK (India) - MASTER INSTALLER  (Phase 1)")
    hr()
    print(f" OS: {platform.system()}   Python: {PYEXE}")

    # which steps? Priority: explicit flags > interactive menu > all
    used_flags = args.admin or args.user or args.from_step or args.skip
    show_menu = args.menu or (not used_flags and sys.stdin.isatty())
    if args.admin and args.user:
        steps = [0, 1, 2, 3]
    elif args.admin:
        steps = list(ADMIN_STEPS)
    elif args.user:
        steps = list(USER_STEPS)
    elif show_menu:
        chosen = choose_steps_menu()
        if chosen is None:
            print(" Aborted."); return 0
        steps = chosen
    else:
        steps = [0, 1, 2, 3]

    skip = {int(x) for x in args.skip.split(",") if x.strip().isdigit()}
    steps = [n for n in steps if n >= args.from_step and n not in skip]

    # properties discovery + a short summary so the operator sees what will happen
    props_path = Path(args.properties) if args.properties else None
    prop_args = ["--properties", str(props_path)] if props_path else []
    if codex_config:
        codex_config.ensure_template()
        cfg = codex_config.Config(path=props_path, quiet=False)
        print("\n Planned settings (from properties/defaults):")
        for k in ("os", "auth_type", "username", "model", "model_provider", "region",
                  "reasoning_effort", "install_gui", "codex_version"):
            print(f"   - {k:16s}: {cfg.get(k, default='(prompt/default)')}")
        tf = cfg.get('token_file', default='')
        if tf:
            print(f"   - token_file       : {tf}")
    else:
        print("\n [config] codex_config.py not found - scripts will use prompts/defaults.")

    print("\n Steps to run:")
    for n in steps:
        print(f"   {n} - {STEP_LABELS.get(n, '')}")
    if not steps:
        print("   (none)")
    if not steps:
        print(" Nothing to do."); return 0

    if not args.yes and not args.dry_run:
        if input('\n Type "yes" to begin: ').strip().lower() != "yes":
            print(" Aborted."); return 0

    # figure out the token file for the auto hand-off (all-in-one runs)
    token_file = resolve_token_file(props_path)

    for n in steps:
        extra = list(prop_args)
        # Step 3: if we just ran step 1 in this session (or a token file exists),
        # point step 3 at it explicitly so the hand-off is seamless.
        if n == 3 and token_file and token_file.exists():
            extra += ["--token-file", str(token_file)]
        rc = run_step(n, extra, args.dry_run)
        if rc != 0:
            print()
            hr("!")
            print(f" STEP {n} ({SCRIPTS[n]}) FAILED (exit {rc}).")
            print(f" Fix the issue above, then resume with:")
            print(f"   {Path(PYEXE).name} install_all.py --from {n}"
                  + (f" --properties {props_path}" if props_path else ""))
            hr("!")
            return rc
        # after step 1, the token file should now exist - refresh the pointer
        if n == 1 and not (token_file and token_file.exists()):
            token_file = resolve_token_file(props_path)

    print()
    hr()
    print(" MASTER: all requested steps completed.")
    hr()
    if 3 in steps or 2 in steps:
        print("""
 VERIFY (open a NEW terminal so env vars load):
   unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
   codex exec --skip-git-repo-check "reply with exactly: BEDROCK OK"

 Expected: BEDROCK OK
""")
    if 1 in steps:
        print(" ADMIN: securely hand the *_BEARER.txt file to the user, then delete the local copy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
