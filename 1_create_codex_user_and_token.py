#!/usr/bin/env python3
r"""
1_create_codex_user_and_token.py   (cross-platform: macOS + Windows)
=============================================================================
STEP 1 - ADMIN runs this (with admin AWS credentials configured).

Creates a LOW-PRIVILEGE IAM user for one Codex end user, attaches a
least-privilege Bedrock-invoke policy (India model/inference-profile ARNs),
and issues a credential:
    - bearer  : a Bedrock API key (AWS_BEARER_TOKEN_BEDROCK) - includes the
                required bedrock:CallWithBearerToken permission.
    - iamkey  : an IAM access key (SigV4 / AWS SDK credential chain).

The secret is saved to a file (600 perms); the FILE PATH is printed so you can
hand it to the user securely and then run step 3 on their machine.

SAFETY: prints exactly what it will create and asks for "yes" before creating.

USAGE
  python3 1_create_codex_user_and_token.py                       (prompts)
  python3 1_create_codex_user_and_token.py --user alice --type bearer
  Options: --admin-profile <name>  --user <name>  --type bearer|iamkey  --out-dir <dir>
=============================================================================
"""
import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

try:
    import codex_config  # shared codex.properties loader (optional)
except Exception:
    codex_config = None

REGIONS  = ["ap-south-1", "ap-south-2"]          # India geo profile (source, dest)
MODEL_ID = "in.openai.gpt-5.6-terra"    # India geographic inference profile id
FM_ID    = "openai.gpt-5.6-terra"       # underlying foundation-model id


def build_policy_doc(account_id, cred_type):
    """Blog-validated policy for Codex on the bedrock-runtime endpoint using the
    India geographic inference profile (data stays in India).

    Ref: AWS blog "Introducing OpenAI models on Amazon Bedrock for in-country
    inferencing in India". bedrock:InvokeModel* scoped to:
      - the India geo inference-profile + project/default   (source region)
      - the foundation model in ap-south-1 AND ap-south-2    (dest regions),
        gated by the bedrock:InferenceProfileArn condition.
    Bearer-token auth additionally needs bedrock:CallWithBearerToken on "*".
    """
    src = REGIONS[0]  # ap-south-1 (source region)
    profile_arn = f"arn:aws:bedrock:{src}:{account_id}:inference-profile/{MODEL_ID}"
    fm_arns = [f"arn:aws:bedrock:{r}::foundation-model/{FM_ID}" for r in REGIONS]
    statements = [
        {
            "Sid": "GrantGeoCrisInferenceProfileAccess",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel*"],
            "Resource": [
                profile_arn,
                f"arn:aws:bedrock:{src}:{account_id}:project/default",
            ],
        },
        {
            "Sid": "GrantGeoCrisModelAccess",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel*"],
            "Resource": fm_arns,
            "Condition": {
                "StringEquals": {"bedrock:InferenceProfileArn": profile_arn}
            },
        },
    ]
    # Bearer path REQUIRES bedrock:CallWithBearerToken on Resource:"*".
    # The OpenAI Responses/Chat Completions APIs use this to authenticate with
    # an Amazon Bedrock API key. (SigV4/IAM-key path also benefits; harmless.)
    if cred_type == "bearer":
        statements.append({
            "Sid": "AllowBearerTokenAuth",
            "Effect": "Allow",
            "Action": ["bedrock:CallWithBearerToken"],
            "Resource": "*",
        })
    return {"Version": "2012-10-17", "Statement": statements}


def aws_json(args, profile):
    cmd = ["aws"] + args + (["--profile", profile] if profile else []) + ["--output", "json"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"AWS call failed: {' '.join(args)}\n{p.stderr.strip()}")
    return json.loads(p.stdout) if p.stdout.strip() else {}


def aws_ok(args, profile):
    cmd = ["aws"] + args + (["--profile", profile] if profile else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"AWS call failed: {' '.join(args)}\n{p.stderr.strip()}")
    return p.stdout


def write_secret(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)   # 600
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-profile", default="", help="AWS CLI profile with admin perms (default: default chain)")
    ap.add_argument("--user")
    ap.add_argument("--type", choices=["bearer", "iamkey"])
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--properties", default="", help="path to codex.properties (optional)")
    args = ap.parse_args()

    print("=" * 70)
    print(" STEP 1 - Create Codex end-user IAM user + credential  (ADMIN)")
    print("=" * 70)

    # Resolve settings: CLI flag > codex.properties > prompt > default
    cli = {"admin_profile": args.admin_profile, "username": args.user, "auth_type": args.type}
    if codex_config:
        codex_config.ensure_template()
        cfg = codex_config.Config(cli_overrides=cli,
                                  path=(Path(args.properties) if args.properties else None))
        profile = cfg.get("admin_profile", default="")
        user_short = cfg.get("username", prompt=True,
                             prompt_text="End-user short name (e.g. alice)")
        cred_type = cfg.get("auth_type", default="bearer", prompt=True,
                            prompt_text="Credential type",
                            choices=["bearer", "iamkey"])
        out_dir_val = args.out_dir or cfg.get("out_dir", default=".")
    else:
        profile = args.admin_profile
        user_short = args.user or input("End-user short name (e.g. alice): ").strip()
        cred_type = args.type or (input("Credential type - [bearer] Bedrock API key or "
                                        "[iamkey] IAM access key (default bearer): ").strip() or "bearer")
        out_dir_val = args.out_dir or "."

    if not user_short:
        print("ERROR: user name required."); sys.exit(1)
    iam_user = f"codex-bedrock-user-{user_short}"
    if cred_type not in ("bearer", "iamkey"):
        print("ERROR: type must be 'bearer' or 'iamkey'."); sys.exit(1)

    ident = aws_json(["sts", "get-caller-identity"], profile)
    account_id = ident.get("Account")
    print(f"\nAdmin identity: {ident.get('Arn')}  (account {account_id})")

    policy_doc = build_policy_doc(account_id, cred_type)

    print("\nTHIS WILL CREATE:")
    print(f"  - IAM user      : {iam_user}")
    print(f"  - Inline policy : bedrock:InvokeModel* on India geo profile "
          f"{MODEL_ID} (bedrock-runtime endpoint; ap-south-1 + ap-south-2)"
          + (" + bedrock:CallWithBearerToken (bearer)" if cred_type == "bearer" else ""))
    print(f"  - Credential    : {'Bedrock API key (bearer token)' if cred_type=='bearer' else 'IAM access key (SigV4)'}")
    print(f"  - Admin profile : {profile or '(default credential chain)'}  account {account_id}")
    if input('\nType "yes" to create: ').strip().lower() != "yes":
        print("Aborted. Nothing created."); sys.exit(0)

    print(f"\nCreating IAM user {iam_user} ...")
    try:
        aws_ok(["iam", "create-user", "--user-name", iam_user,
                "--tags", "Key=purpose,Value=codex-bedrock", "Key=managed-by,Value=provisioning-script"], profile)
    except RuntimeError as e:
        if "EntityAlreadyExists" in str(e):
            print("  (user already exists - continuing)")
        else:
            raise
    print("Attaching least-privilege policy ...")
    aws_ok(["iam", "put-user-policy", "--user-name", iam_user,
            "--policy-name", "bedrock-invoke-india",
            "--policy-document", json.dumps(policy_doc)], profile)

    out_dir = Path(out_dir_val); out_dir.mkdir(parents=True, exist_ok=True)

    if cred_type == "bearer":
        print("Creating Bedrock API key (service-specific credential) ...")
        resp = aws_json(["iam", "create-service-specific-credential",
                         "--user-name", iam_user, "--service-name", "bedrock.amazonaws.com"], profile)
        c = resp.get("ServiceSpecificCredential", {})
        token = c.get("ServiceCredentialSecret") or c.get("ServicePassword") or c.get("ServiceApiKeyValue") or ""
        cid = c.get("ServiceSpecificCredentialId", "")
        if not token:
            print("ERROR: no secret returned. Fields:", sorted(c.keys()))
            print("Your CLI may be too old for bedrock service-specific credentials. "
                  "Update AWS CLI v2 or create the key in the Bedrock console -> API keys.")
            sys.exit(1)
        secret_path = out_dir / f"{iam_user}_BEARER.txt"
        write_secret(secret_path, token + "\n")
        print("\n" + "=" * 70)
        print(" BEARER TOKEN CREATED")
        print("=" * 70)
        print(f"  IAM user   : {iam_user}")
        print(f"  Cred id    : {cid}")
        print(f"  Token head : {token[:8]}...   len {len(token)}")
        print(f"  SAVED TO   : {secret_path.resolve()}   (permissions 600)")
        print("\n  NEXT STEP (on the USER'S machine, after step 2 installs Codex):")
        print(f"    python3 3_apply_token.py --token-file \"{secret_path.resolve()}\"")
        print("\n  NOTE: IAM changes can take ~30s to propagate for the bearer path.")
    else:
        print("Creating IAM access key ...")
        resp = aws_json(["iam", "create-access-key", "--user-name", iam_user], profile)
        ak = resp.get("AccessKey", {})
        akid, secret = ak.get("AccessKeyId", ""), ak.get("SecretAccessKey", "")
        secret_path = out_dir / f"{iam_user}_IAMKEY.txt"
        write_secret(secret_path, f"AWS_ACCESS_KEY_ID={akid}\nAWS_SECRET_ACCESS_KEY={secret}\nAWS_REGION={REGIONS[0]}\n")
        print("\n" + "=" * 70)
        print(" IAM ACCESS KEY CREATED")
        print("=" * 70)
        print(f"  IAM user      : {iam_user}")
        print(f"  Access key id : {akid}")
        print(f"  SAVED TO      : {secret_path.resolve()}   (permissions 600)")
        print("\n  NEXT STEP (on the USER'S machine): configure AWS creds, e.g.")
        print(f"    aws configure   (paste the key id + secret; region {REGIONS[0]})")
        print("  Codex then uses the AWS SDK credential chain (no bearer token needed).")

    print("\nDelete the local secret file after secure hand-off.")


if __name__ == "__main__":
    main()
