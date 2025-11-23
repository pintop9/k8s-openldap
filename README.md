# OpenLDAP on Kubernetes (Minikube) Project - Streamlined

This document outlines the streamlined process for deploying a fully configured OpenLDAP service on Minikube, complete with custom users and a first-login MFA enrollment flow.

## Project Overview

The goal is to deploy OpenLDAP on Kubernetes with a configuration-driven setup. This includes adding a custom OATH schema for MFA, pre-loading users, and using an intelligent script for first-time MFA enrollment.

## Prerequisites

- `minikube`
- `kubectl`
- `helm`
- `python` and `pip`

## Required Python Libraries

All necessary Python libraries are listed in `requirements.txt`. Install them using:
```bash
pip install -r requirements.txt
```

---

## Deployment and Configuration

The entire deployment is handled by a single `helm install` command that references our custom configuration files. This process is idempotent and ensures a consistent setup.

### Included Configuration Files:

1.  **`oath_schema.ldif`**: Extends the OpenLDAP schema to support Time-based One-Time Passwords (TOTP/MFA).
2.  **`setup.ldif`**: A setup script that runs after the schema is loaded. It deletes the default chart users and creates three new custom users (`asmith`, `bjohnson`, `cbrown`) ready for MFA enrollment.

### Deployment Command

To deploy or upgrade your OpenLDAP instance with this configuration, run the following `helm` command from the root of the project directory.

This command installs the chart and uses the `--set-file` flag to automatically load our custom schema and setup files into the OpenLDAP configuration.

```bash
helm install my-openldap helm-openldap/openldap-stack-ha \
  --namespace ldap \
  --create-namespace \
  --set-file customSchemaFiles.oath\.ldif=./oath_schema.ldif \
  --set-file customLdifFiles.setup\.ldif=./setup.ldif
```
*Note: If you are upgrading an existing release, use `helm upgrade` instead of `helm install`.*

---

## Authentication and MFA Enrollment

The `ldap_cli_login.py` script now handles both standard authentication and first-time MFA enrollment.

### Connecting to the LDAP Service

The Python script runs on your local machine and needs to connect to the LDAP service running inside Minikube. Use `kubectl port-forward` to make this connection possible.

**In a separate, dedicated terminal, run and leave this command running:**
```bash
kubectl port-forward -n ldap service/my-openldap 3890:389
```
The script is pre-configured to connect to `localhost:3890`.

### Running the Login Script

Execute the script to start the login process:
```bash
python ldap_cli_login.py
```

#### First-Time Login Flow:

1.  Enter the username (e.g., `asmith`) and password (`password123`).
2.  The script will detect that MFA is not yet configured for this user.
3.  It will automatically generate a new MFA secret, save it to the user's LDAP profile, and display a **QR Code** in the terminal.
4.  Scan this QR code with your Google Authenticator app.
5.  The login process for this first time is now complete.

#### Subsequent Logins:

1.  Enter the username and password.
2.  The script will detect that MFA is configured.
3.  It will now prompt you for the 6-digit "Google Authenticator Code".
4.  Enter the code from your app to complete the authentication.