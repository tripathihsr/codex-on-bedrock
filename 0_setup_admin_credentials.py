#!/usr/bin/env python3
r"""
1_setup_admin_credentials.py  (cross-platform: macOS + Windows)
=============================================================================
STEP 1 of the Codex+Bedrock provisioning bundle.

PURPOSE
  Configure the ADMIN's AWS credentials on this machine's CLI. The admin
  ALREADY HAS these credentials (an IAM user/role that can create IAM users,
  policies, access keys, and/or Bedrock API keys). This script just stores
  them into the AWS CLI config (a named profile) so scripts 2 and 3 can use
  them, and verifies the identity.

  It does NOT create any AWS resources. It only runs `aws configure` for a
  profile and calls `aws sts get-caller-identity` to confirm.

PREREQUISITES
  - AWS CLI v2 installed  (https://aws.amazon.com/cli/)
  - The admin's Access Key ID + Secret Access Key (or use SSO separately)

USAGE
  python3 1_setup_admin_credentials.py           (macOS)
  python  1_setup_admin_credentials.py           (Windows)
=============================================================================
"""
import getpass
import shutil
import subprocess
import sys

DEFAULT_PROFILE = "codex-bedrock-admin"
DEFAULT_REGION  = "ap-south-1"   # India


def have_aws_cli() -> bool:
    return shutil.which("aws") is not None


def run(cmd, check=False, capture=True):
    proc = subprocess.run(cmd, capture_output=capture, text=True)
    if capture and proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0 and capture and proc.stderr.strip():
        print("  [stderr]", proc.stderr.strip())
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return proc.returncode, (proc.stdout if capture else "")


def aws_configure_set(profile, key, value):
    run(["aws", "configure", "set", key, value, "--profile", profile])


def main():
    print("=" * 70)
    print(" STEP 1  -  Configure ADMIN AWS credentials (no resources created)")
    print("=" * 70)

    if not have_aws_cli():
        print("\nERROR: AWS CLI not found. Install AWS CLI v2 first:")
        print("  macOS:   brew install awscli     (or the AWS pkg installer)")
        print("  Windows: winget install Amazon.AWSCLI")
        sys.exit(1)

    print("\nThis stores the admin credentials you ALREADY HAVE into a named AWS "
          "CLI profile so the provisioning scripts can use them.\n")

    profile = input(f"AWS profile name to create/use [{DEFAULT_PROFILE}]: ").strip() or DEFAULT_PROFILE
    region  = input(f"AWS region [{DEFAULT_REGION}]: ").strip() or DEFAULT_REGION

    print("\nAuth method:")
    print("  1) Access key + secret (paste them)")
    print("  2) I use AWS SSO / already have a profile -> just verify")
    method = input("Choose [1/2] (default 1): ").strip() or "1"

    if method == "1":
        access_key = input("AWS Access Key ID: ").strip()
        secret_key = getpass.getpass("AWS Secret Access Key (hidden): ").strip()
        session    = getpass.getpass("AWS Session Token (optional, hidden; Enter to skip): ").strip()
        if not access_key or not secret_key:
            print("ERROR: access key and secret are required."); sys.exit(1)
        aws_configure_set(profile, "aws_access_key_id", access_key)
        aws_configure_set(profile, "aws_secret_access_key", secret_key)
        if session:
            aws_configure_set(profile, "aws_session_token", session)
        aws_configure_set(profile, "region", region)
        aws_configure_set(profile, "output", "json")
        print(f"\nStored credentials in profile '{profile}'.")
    else:
        print(f"\nUsing existing profile '{profile}'. If it does not exist, run "
              f"'aws configure sso' or 'aws configure --profile {profile}' first.")
        aws_configure_set(profile, "region", region)

    print("\nVerifying identity...")
    rc, out = run(["aws", "sts", "get-caller-identity", "--profile", profile])
    if rc != 0:
        print("\nVerification FAILED. Check the credentials / profile and retry.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" DONE. Admin profile is ready.")
    print("=" * 70)
    print(f"""
Profile : {profile}
Region  : {region}

NEXT STEP:
  Run script 2 to provision a Bedrock end-user, passing this profile:
    python3 2_provision_bedrock_user.py --admin-profile {profile}   (macOS)
    python  2_provision_bedrock_user.py --admin-profile {profile}   (Windows)

NOTE: The admin identity must have permission to create IAM users/policies/keys
(for the IAM-user option) and/or Bedrock API keys (bearer-token option).
For production, prefer AWS IAM Identity Center (SSO) over long-lived keys.
""")


if __name__ == "__main__":
    main()
