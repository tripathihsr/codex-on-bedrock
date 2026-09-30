#!/usr/bin/env python3
r"""
codex_config.py  -  shared properties loader for the Codex+Bedrock bundle.

Single source of truth for engineer-editable settings. All scripts import this.

Resolution precedence for every setting (first non-empty wins):
    1) explicit CLI flag         (passed by the script)
    2) codex.properties value    (KEY=VALUE file next to the scripts, or $CODEX_PROPERTIES)
    3) interactive prompt         (only if prompt=True and still empty)
    4) built-in default           (the `default` argument)

Design goals:
    - NEVER break if the file is absent: behaves exactly like the old prompt/flag flow.
    - If the file is missing, write a commented template (codex.properties.template)
      so engineers have something to copy, then continue with prompts.
    - Stdlib only. Cross-platform (macOS + Windows).

File format (codex.properties):
    # comments start with '#'
    KEY = value            # inline comments after a value are stripped
    KEY=value
    # blank lines ignored; values may be quoted with single or double quotes
"""
import os
import getpass
from pathlib import Path

# Where to look for the properties file (in order):
#   1) $CODEX_PROPERTIES env var (absolute path)
#   2) codex.properties next to the scripts
#   3) codex.properties in the current working directory
_HERE = Path(__file__).resolve().parent
_CANDIDATES = []
if os.environ.get("CODEX_PROPERTIES"):
    _CANDIDATES.append(Path(os.environ["CODEX_PROPERTIES"]).expanduser())
_CANDIDATES.append(_HERE / "codex.properties")
_CANDIDATES.append(Path.cwd() / "codex.properties")

TEMPLATE_NAME = "codex.properties.template"


def _strip_inline_comment(val: str) -> str:
    # remove an unquoted trailing " # comment"; keep '#' inside quotes
    if not val:
        return val
    q = None
    out = []
    for ch in val:
        if q:
            out.append(ch)
            if ch == q:
                q = None
        else:
            if ch in ("'", '"'):
                q = ch
                out.append(ch)
            elif ch == "#":
                break
            else:
                out.append(ch)
    return "".join(out).strip()


def _dequote(val: str) -> str:
    v = val.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def load_properties(path: Path = None) -> dict:
    """Parse the first existing codex.properties into a dict (lowercased keys)."""
    paths = [path] if path else _CANDIDATES
    for p in paths:
        try:
            if p and p.exists():
                data = {}
                for raw in p.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    key = k.strip().lower()
                    val = _dequote(_strip_inline_comment(v.strip()))
                    if key:
                        data[key] = val
                data["__source__"] = str(p)
                return data
        except Exception:
            continue
    return {}


class Config:
    """Resolver with precedence: flag > properties > prompt > default."""

    def __init__(self, cli_overrides: dict = None, path: Path = None, quiet: bool = False):
        self.props = load_properties(path)
        self.cli = {k: v for k, v in (cli_overrides or {}).items() if v not in (None, "")}
        self.source = self.props.get("__source__")
        if not quiet:
            if self.source:
                print(f"  [config] using properties: {self.source}")
            else:
                print("  [config] no codex.properties found - using flags/prompts/defaults.")

    def get(self, key, default="", prompt=False, prompt_text=None,
            secret=False, choices=None):
        key_l = key.lower()
        # 1) CLI flag
        if key_l in self.cli:
            return self._validate(key, self.cli[key_l], choices)
        # 2) properties file
        if self.props.get(key_l):
            return self._validate(key, self.props[key_l], choices)
        # 3) prompt
        if prompt:
            label = prompt_text or f"{key}"
            suffix = f" [{default}]" if default else ""
            if choices:
                suffix = f" ({'/'.join(choices)})" + (f" [{default}]" if default else "")
            while True:
                if secret:
                    val = getpass.getpass(f"{label}{suffix}: ").strip()
                else:
                    val = input(f"{label}{suffix}: ").strip()
                if not val and default:
                    return default
                if not val and not default:
                    print("  value required.")
                    continue
                try:
                    return self._validate(key, val, choices)
                except ValueError as e:
                    print(f"  {e}")
        # 4) default
        return default

    def get_bool(self, key, default=False, prompt=False, prompt_text=None):
        raw = self.get(key, default=("true" if default else "false"),
                       prompt=prompt, prompt_text=prompt_text,
                       choices=["true", "false", "yes", "no"])
        return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")

    def _validate(self, key, val, choices):
        if choices and val not in choices:
            raise ValueError(f"{key} must be one of {choices}, got '{val}'")
        return val


def ensure_template(dest_dir: Path = None):
    """Write codex.properties.template if it does not exist. Returns its path."""
    dest_dir = dest_dir or _HERE
    tpl = dest_dir / TEMPLATE_NAME
    if not tpl.exists():
        tpl.write_text(TEMPLATE_TEXT, encoding="utf-8")
    return tpl


# The canonical, fully-commented template. Also written to disk on demand.
TEMPLATE_TEXT = r'''# =====================================================================
#  codex.properties  -  Codex + Amazon Bedrock (India) setup
#  Edit the values below, then run the scripts. Any value left blank is
#  asked for at the prompt (or a sensible default is used).
#  Precedence: CLI flag > this file > prompt > built-in default.
#  Format: KEY = VALUE   (# starts a comment; quotes optional)
#  To use a custom location: set CODEX_PROPERTIES=/abs/path/codex.properties
# =====================================================================

# ---------- Platform ----------
# os: auto | mac | windows   (auto = detect this machine)
os = auto

# ---------- Codex install (step 2) ----------
# codex_version: latest | a pinned version string (e.g. 0.154.0)
#   mac (brew):    latest recommended; pinning a cask version is best-effort.
#   windows:       latest recommended.
codex_version = latest
# install_gui: true | false  (desktop GUI in addition to the CLI)
install_gui = true

# ---------- Model / endpoint (writes ~/.codex/config.toml) ----------
# model: the INFERENCE PROFILE id (India geo). Terra or Luna:
#   in.openai.gpt-5.6-terra   |   in.openai.gpt-5.6-luna
model = in.openai.gpt-5.6-terra
# model_provider: MUST be amazon-bedrock-runtime for the India geo profile.
#   (amazon-bedrock -> old mantle endpoint -> 404. Do not use.)
model_provider = amazon-bedrock-runtime
# region: ap-south-1 (Mumbai) or ap-south-2 (Hyderabad)
region = ap-south-1
# wire_api: responses  (OpenAI Responses API surface)
wire_api = responses
# reasoning_effort: none | low | medium | high | xhigh | max
reasoning_effort = high
# base_url: OPTIONAL explicit endpoint override. Leave blank to let Codex
#   derive it from the provider + region (recommended). Example if needed:
#   https://bedrock-runtime.ap-south-1.amazonaws.com/openai/v1
base_url =

# ---------- Auth ----------
# auth_type: bearer | iamkey
#   bearer = Amazon Bedrock API key (recommended for end users)
#   iamkey = IAM access key (SigV4 via AWS SDK credential chain)
auth_type = bearer
# username: short name for the Codex end user (step 1 creates
#   IAM user codex-bedrock-user-<username>)
username =
# token_file: path to the *_BEARER.txt produced by step 1 (PREFERRED).
#   Used by step 3 to apply the token.
token_file =
# bearer_token: OPTIONAL inline token. Leave blank and use token_file instead.
#   WARNING: if you put a token here, DO NOT commit this file anywhere.
bearer_token =

# ---------- AWS (admin steps 0-1) ----------
# admin_profile: AWS CLI profile with admin perms (blank = default chain)
admin_profile = codex-bedrock-admin
# account_id: OPTIONAL; auto-detected from admin identity if blank
account_id =

'''
