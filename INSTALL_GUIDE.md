# Codex + Amazon Bedrock (India) - Installation Guide (Phase 1)

End-to-end, validated guide to run **OpenAI Codex** against **Amazon Bedrock
GPT-5.6 Terra** in the **India region (ap-south-1)** using a **bearer token**.
Cross-platform (macOS + Windows). Phase 1 = Codex talks DIRECTLY to Bedrock
(no LiteLLM gateway). Every script auto-resolves the current user's home dir.

> Validated end-to-end: a fresh IAM user + bearer token (no SDK/CLI profile
> creds) returned `BEDROCK OK` from `in.openai.gpt-5.6-terra` in ap-south-1.

---

## 0. Prerequisites

| Requirement | macOS | Windows |
|---|---|---|
| Python 3 | `brew install python` (or preinstalled) | from python.org / Microsoft Store |
| AWS CLI v2 | `brew install awscli` | `winget install Amazon.AWSCLI` |
| Installer for Codex | Homebrew (`brew`) | `winget` (or Microsoft Store) |
| Admin AWS identity | must be able to create IAM users, inline policies, and Bedrock API keys (service-specific credentials) | same |

- **Account:** `<YOUR_ACCOUNT_ID>` (12-digit AWS account id)  |  **Region:** ap-south-1 (Mumbai), with ap-south-2 (Hyderabad) as the cross-Region destination. Data stays in India.
- **Roles:** the **Admin** runs scripts 0-1; the **End user** runs scripts 2-3 on their own machine.

---

## 1. The bundle (four scripts, run in order)

| # | Script | Who / Where | What it does |
|---|---|---|---|
| 0 | `0_setup_admin_credentials.py` | Admin, once | Store admin AWS creds in a named CLI profile + verify identity. Creates NO resources. |
| 1 | `1_create_codex_user_and_token.py` | Admin, per user | Create low-priv IAM user `codex-bedrock-user-<name>`, attach the blog-validated Bedrock policy, issue a **bearer token** (default) or IAM access key, save secret to a 600-perm file. |
| 2 | `2_install_codex.py` | User machine | Install Codex **CLI + desktop GUI**, write `~/.codex/config.toml` + `~/.codex/.env`, create `~/SharedData/`. Verifies the CLI is callable (auto npm fallback). |
| 3 | `3_apply_token.py` | User machine | Write the bearer token into `~/.codex/.env` + shell/User env so Codex authenticates. Warns if the CLI is not installed yet. |
| M | `install_all.py` | Both | **Master installer** - runs steps 0-1-2-3 in sequence (`--admin`/`--user`/all). Reads `codex.properties`; stops on failure with a resume hint. |
| - | `codex.properties` | Both | **Engineer-editable settings** (model, region, provider, version, os, auth, token_file, ...). Read by all scripts. See section 1b. |
| - | `codex_config.py` | (library) | Shared loader that all scripts import to read `codex.properties`. Do not edit. |

Bundle location: the directory where you cloned/unpacked this bundle (the scripts auto-resolve paths relative to themselves).

---

## 1b. Self-service config: `codex.properties` (edit ONE file)

Instead of remembering flags/prompts, edit **`codex.properties`** (next to the
scripts). Every script reads it automatically. Precedence for each value:

> **CLI flag  >  `codex.properties`  >  interactive prompt  >  built-in default**

- If the file is **missing**, scripts still work (prompt/defaults) and drop a
  commented `codex.properties.template` you can copy.
- To use a custom location: `export CODEX_PROPERTIES=/abs/path/codex.properties`
  (Windows: `set CODEX_PROPERTIES=C:\path\codex.properties`).

### Parameters

| Key | Used by | Values / example | Change? | Notes |
|---|---|---|---|---|
| `os` | 2 | `auto` \| `mac` \| `windows` | rarely | `auto` detects the machine; a wrong forced value is ignored with a warning. |
| `codex_version` | 2 | `latest` \| `0.154.0` | optional | `latest` recommended. Pinning is best-effort on brew; exact pin via npm `@openai/codex@<ver>` / winget `--version`. |
| `install_gui` | 2 | `true` \| `false` | optional | GUI is chat-only on Bedrock; CLI is the functional client. |
| `model` | 2, 3 | `in.openai.gpt-5.6-terra` \| `in.openai.gpt-5.6-luna` | maybe | India geo **inference-profile** id. |
| `model_provider` | 2, 3 | `amazon-bedrock-runtime` | **NO** | Must stay `amazon-bedrock-runtime`. `amazon-bedrock` -> 404. |
| `region` | 2, 3 | `ap-south-1` \| `ap-south-2` | maybe | Mumbai / Hyderabad. |
| `wire_api` | 2, 3 | `responses` | **NO** | OpenAI Responses API surface. |
| `reasoning_effort` | 2, 3 | `none` \| `low` \| `medium` \| `high` \| `xhigh` \| `max` | optional | Default `high`. |
| `base_url` | 2, 3 | blank, or full endpoint URL | rarely | Leave **blank** to let Codex derive it. Only set to force an endpoint. |
| `auth_type` | 1 | `bearer` \| `iamkey` | maybe | `bearer` = Bedrock API key (recommended). |
| `username` | 1 | e.g. `alice` | **YES** | Creates IAM user `codex-bedrock-user-<username>`. |
| `token_file` | 3 | path to `*_BEARER.txt` | **YES** (user) | Preferred way to supply the token. |
| `bearer_token` | 3 | inline token | avoid | Works, but **never commit** the file if set. Prefer `token_file`. |
| `admin_profile` | 0, 1 | e.g. `codex-bedrock-admin` | maybe | AWS CLI profile with admin perms. |
| `account_id` | 1 | 12-digit id | optional | Auto-detected from admin identity if blank. |

### What the admin typically changes vs the end user

- **Admin (steps 0-1):** `admin_profile`, `username`, `auth_type`.
- **End user (steps 2-3):** `token_file` (path to the file the admin handed over).
  Model/region/provider usually stay at the validated defaults.

### Example `codex.properties`

```properties
# ---- Platform / install ----
os = auto
codex_version = latest
install_gui = true

# ---- Model / endpoint (config.toml) ----
model = in.openai.gpt-5.6-terra
model_provider = amazon-bedrock-runtime      # do not change
region = ap-south-1
wire_api = responses                          # do not change
reasoning_effort = high
base_url =                                    # blank = auto

# ---- Auth ----
auth_type = bearer
username = alice
token_file = ./codex-bedrock-user-alice_BEARER.txt
bearer_token =                                # leave blank; use token_file

# ---- AWS (admin) ----
admin_profile = codex-bedrock-admin
account_id =
```

Run the scripts exactly as before; they now pull values from this file and only
prompt for anything still missing:
```bash
python3 1_create_codex_user_and_token.py     # reads username/auth_type/admin_profile
python3 2_install_codex.py                    # reads model/region/provider/gui/version
python3 3_apply_token.py                       # reads token_file (or bearer_token)
```

---

## 1c. One-shot install (master script)

After editing `codex.properties`, run the master installer. With **no flags** it
shows an interactive menu so you pick exactly which steps to run:

```text
 What would you like to do? Select one or more steps.
   0 - Setup admin AWS profile            (admin machine)
   1 - Create Codex user + bearer token   (admin machine)
   2 - Install Codex UI + CLI             (user machine)
   3 - Apply bearer token + Codex config  (user machine)
   Presets: a=all(0,1,2,3)  admin=(0,1)  user=(2,3)  q=quit
 Your choice: 2,3
```

Typical usage by role:
- **On your admin laptop (once):** choose `0` the first time (sets up the admin
  AWS profile), then `1` for each new user (creates their IAM user + bearer token).
  Next time you only need `1` - you don't repeat `0`.
- **On each user's machine:** choose `2,3` (install Codex, then apply the token file
  you handed them).

You can also skip the menu with flags:

```bash

```bash
# macOS - all steps (0,1,2,3) on this machine
python3 install_all.py

# Windows - all steps
python  install_all.py

# Admin machine only (create IAM user + bearer token): steps 0,1
python3 install_all.py --admin

# End-user machine only (install Codex + apply token): steps 2,3
python3 install_all.py --user
```

Useful flags:
| Flag | Effect |
|---|---|
| `--admin` | run only admin steps (0,1) -> produces `*_BEARER.txt` |
| `--user` | run only user steps (2,3) -> installs Codex on this machine |
| `--menu` | force the interactive step-selection menu |
| `--from <n>` | resume starting at step n (0..3) |
| `--skip <n[,n...]>` | skip specific steps (e.g. `--skip 0`) |
| `--properties <path>` | use a specific properties file |
| `--yes` | skip the master confirmation prompt (unattended) |
| `--dry-run` | print the commands without executing (validate first) |

Behaviour:
- Prints the planned settings from `codex.properties` before running.
- **Stops on the first failing step** and prints how to resume (`--from <n>`).
- In an all-in-one run, after step 1 creates the token file it **auto-points
  step 3** at that file (`--token-file ...`), so the hand-off is seamless.
- Tip: run once with `--dry-run` to confirm the sequence, then run for real.

After it finishes, verify in a NEW terminal:
```bash
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
codex exec --skip-git-repo-check "reply with exactly: BEDROCK OK"
```

---

## 2. Installation sequence

### Step 0 - (Admin, once) configure admin AWS credentials
```bash
# macOS
python3 0_setup_admin_credentials.py
# Windows
python  0_setup_admin_credentials.py
```
Creates/uses profile `codex-bedrock-admin` (region ap-south-1) and runs
`aws sts get-caller-identity` to confirm. No AWS resources are created.

### Step 1 - (Admin, per user) create the IAM user + bearer token
```bash
# bearer token (what the end customer uses):
python3 1_create_codex_user_and_token.py --user alice --type bearer

# OR, if you prefer SigV4/SDK creds instead of a bearer token:
python3 1_create_codex_user_and_token.py --user alice --type iamkey
```
- Prints exactly what it will create and asks for `yes` before creating.
- Saves the secret to `./codex-bedrock-user-alice_BEARER.txt` (600 perms) and prints the full path.
- Hand the secret file to the user securely; delete the local copy afterward.
- IAM changes can take ~30s to propagate for the bearer path.

### Step 2 - (User machine) install Codex + write config
```bash
# macOS  (installs Codex CLI via brew cask 'codex' + ChatGPT GUI app)
python3 2_install_codex.py
# Windows (winget 'OpenAI.Codex' = desktop app incl. bundled CLI)
python  2_install_codex.py
```
Writes (resolved to the CURRENT user's home):
- `<home>/.codex/config.toml` - provider `amazon-bedrock-runtime`, model `in.openai.gpt-5.6-terra`, region ap-south-1
- `<home>/.codex/.env` - Bedrock auth env (token filled in step 3)
- `<home>/SharedData/` - drop files here for the Codex CLI to read

The script verifies the `codex` CLI actually runs. If it can't find it, it tries
`npm install -g @openai/codex`, then prints a BLOCKING warning if still missing.
Do NOT continue to step 3 until the CLI is verified.

### Step 3 - (User machine) apply the bearer token
```bash
# macOS
python3 3_apply_token.py --token-file /path/to/codex-bedrock-user-alice_BEARER.txt
# Windows
python  3_apply_token.py --token-file C:\path\to\codex-bedrock-user-alice_BEARER.txt
```
- For an IAM access key instead: run `aws configure` with it (Codex uses the SDK chain).
- **Windows:** fully restart the Codex desktop app after this.
- **macOS:** open a NEW terminal (the token is exported via `~/.zshrc`).

### Step 4 - open a NEW terminal
So the token/env vars load. On macOS this is required; the old shell won't have them.

### Step 5 - verify
```bash
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
codex exec --skip-git-repo-check "reply with exactly: BEDROCK OK"
```
Expected output: `BEDROCK OK`. The `unset` guarantees the bearer token is used
(not a leftover SDK profile). Ignore the harmless "Model metadata not found" warning.

### Step 6 - (Admin) clean up
Securely delete the local `codex-bedrock-user-<name>_BEARER.txt` after hand-off. Never commit it.

---

## 3. KEY CONFIGURATIONS (the settings that make it work)

### 3.1 `~/.codex/config.toml` (CRITICAL - exact values)
```toml
# Codex -> Amazon Bedrock (bedrock-runtime endpoint), India geographic profile.
model = "in.openai.gpt-5.6-terra"          # India geographic INFERENCE PROFILE id
model_provider = "amazon-bedrock-runtime"  # NOT "amazon-bedrock"
model_reasoning_effort = "high"            # none|low|medium|high|xhigh|max

[model_providers.amazon-bedrock-runtime.aws]
region = "ap-south-1"                      # ap-south-2 also valid (Hyderabad)
wire_api = "responses"                     # OpenAI Responses API surface
```

Why the provider name is the make-or-break setting:

| `model_provider` | Endpoint Codex calls | Knows `in.openai.gpt-5.6-terra`? |
|---|---|---|
| `amazon-bedrock` | `bedrock-mantle.ap-south-1.api.aws` | NO -> `404 model does not exist` |
| `amazon-bedrock-runtime` (correct) | `bedrock-runtime.ap-south-1.amazonaws.com/openai/v1/responses` | YES -> works |

`bedrock-runtime` is the endpoint AWS recommends for new apps and the only one
that supports the India geographic cross-Region inference profile (keeps data in
ap-south-1/ap-south-2).

### 3.2 `~/.codex/.env` (auth, written by step 3)
```
AWS_BEARER_TOKEN_BEDROCK=ABSK...      # the Bedrock API key (bearer token)
AWS_REGION=ap-south-1
```
File is chmod 600. On Windows the token is also set at User env scope.

### 3.3 IAM policy for the Codex user (blog-validated, least privilege)
Attached automatically by script 1 (`--type bearer`). Replace `<ACCOUNT>`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "GrantGeoCrisInferenceProfileAccess", "Effect": "Allow",
      "Action": ["bedrock:InvokeModel*"],
      "Resource": [
        "arn:aws:bedrock:ap-south-1:<ACCOUNT>:inference-profile/in.openai.gpt-5.6-terra",
        "arn:aws:bedrock:ap-south-1:<ACCOUNT>:project/default" ] },
    { "Sid": "GrantGeoCrisModelAccess", "Effect": "Allow",
      "Action": ["bedrock:InvokeModel*"],
      "Resource": [
        "arn:aws:bedrock:ap-south-1::foundation-model/openai.gpt-5.6-terra",
        "arn:aws:bedrock:ap-south-2::foundation-model/openai.gpt-5.6-terra" ],
      "Condition": { "StringEquals": {
        "bedrock:InferenceProfileArn":
          "arn:aws:bedrock:ap-south-1:<ACCOUNT>:inference-profile/in.openai.gpt-5.6-terra" } } },
    { "Sid": "AllowBearerTokenAuth", "Effect": "Allow",
      "Action": ["bedrock:CallWithBearerToken"], "Resource": "*" }
  ]
}
```
Key points:
- Bearer-token (Amazon Bedrock API key) auth REQUIRES `bedrock:CallWithBearerToken`
  on `Resource: "*"` (it does not support ARN scoping). SigV4/IAM-key auth does not.
- The FM id is `openai.gpt-5.6-terra` (no prefix); the inference-profile id is
  `in.openai.gpt-5.6-terra`. Both appear in the policy and are different things.

### 3.3b IAM permissions the ADMIN identity needs (to run steps 0-1)

The admin who runs `1_create_codex_user_and_token.py` must be allowed to create
the IAM user, attach its inline policy, and mint the credential. Minimum policy
for the admin identity (scope the `Resource` to the naming prefix as shown):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "AdminManageCodexUsers", "Effect": "Allow",
      "Action": [
        "iam:CreateUser",
        "iam:TagUser",
        "iam:PutUserPolicy",
        "iam:GetUserPolicy",
        "iam:DeleteUserPolicy",
        "iam:CreateServiceSpecificCredential",
        "iam:ListServiceSpecificCredentials",
        "iam:DeleteServiceSpecificCredential",
        "iam:CreateAccessKey",
        "iam:DeleteAccessKey",
        "iam:DeleteUser"
      ],
      "Resource": "arn:aws:iam::<ACCOUNT>:user/codex-bedrock-user-*" },
    { "Sid": "AdminVerifyIdentity", "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"], "Resource": "*" }
  ]
}
```

Notes:
- `CreateServiceSpecificCredential` is what issues the **bearer token** (Bedrock
  API key). The `CreateAccessKey` actions are only needed for the `iamkey` path.
- The `Delete*` actions let the admin clean up the test/user later.
- For production, prefer AWS IAM Identity Center (SSO) for the admin rather than
  a long-lived admin access key.

### 3.4 Model / region reference
| Item | Value |
|---|---|
| Inference profile (model in config) | `in.openai.gpt-5.6-terra` (Terra) / `in.openai.gpt-5.6-luna` (Luna) |
| Foundation model (in IAM ARNs) | `openai.gpt-5.6-terra` |
| Source region | `ap-south-1` (Mumbai) or `ap-south-2` (Hyderabad) |
| Destination regions (auto) | ap-south-1 + ap-south-2 (India only) |
| API surface | OpenAI Responses (`wire_api = "responses"`) |

---

## 4. Troubleshooting (error -> cause -> fix)

| Symptom | Real cause | Fix |
|---|---|---|
| `command not found: codex` | Step 2 skipped or CLI not on PATH | Run/re-run `2_install_codex.py`; open a new terminal |
| `404 The model 'in.openai.gpt-5.6-terra' does not exist` (url `bedrock-mantle...`) | provider `amazon-bedrock` -> wrong (mantle) endpoint | set `model_provider = "amazon-bedrock-runtime"` |
| `403 bedrock-mantle:CreateInference / CallWithBearerToken` | on the mantle endpoint (wrong endpoint) | switch to bedrock-runtime + blog IAM policy |
| `403 not authorized bedrock:InvokeModel` | policy missing profile/FM ARNs or the InferenceProfileArn condition | apply the policy in 3.3; wait ~30s for propagation |
| `AccessDenied ... bedrock:CallWithBearerToken` | bearer path missing this action | ensure the `AllowBearerTokenAuth` statement exists |
| "Model metadata not found" warning | cosmetic fallback metadata | ignore; does not affect results |

---

## 5. Validated limitations (see ../SOLUTION_STATUS.md)

- Use the **Codex CLI** for file analysis. The desktop GUI does NOT expose
  file tools on the Bedrock path, and **MCP tools do NOT work** with Codex on Bedrock.
- On macOS the standalone "Codex" GUI app is discontinued; the desktop GUI is the
  ChatGPT app (installed by step 2). Windows has the dedicated Codex app.
- Bedrock model invocations are logged (S3/CloudWatch) in the India regions for audit.

---

## 6. Security notes

- **Config file is not committed.** `codex.properties` is listed in `.gitignore`
  (it may hold a username or an inline token). Copy it from
  `codex.properties.template` and edit locally: `cp codex.properties.template codex.properties`.
- **Token files are git-ignored.** `*_BEARER.txt` and `*_IAMKEY.txt` are excluded
  by `.gitignore`, but you should still delete them after hand-off.
- Scripts create real IAM resources; step 1 confirms before creating and writes
  secrets to 600-perm files. Delete secret files after hand-off. Never commit them.
- Long-lived IAM users/keys are a Phase 1 convenience. For production prefer AWS
  IAM Identity Center (SSO) with an OIDC credential helper (Codex reads the SDK
  chain), and add LiteLLM per-user governance in Phase 2.
