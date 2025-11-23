# OpenLDAP on Kubernetes (Minikube) Project - Automated Deployment

This document outlines the streamlined and automated process for deploying a fully configured OpenLDAP service on Minikube, complete with custom users and a first-login MFA enrollment flow.

## Project Overview

The goal is to deploy OpenLDAP on Kubernetes with a robust, configuration-driven, and automated setup. This includes adding a custom OATH schema for MFA, pre-loading users, and using an intelligent script for first-time MFA enrollment.

## Prerequisites

- `minikube`
- `kubectl`
- `helm`
- `python` and `pip`

## Project Files

*   **`values.yaml`**: Your main Helm values file, which embeds the OATH schema, and user/group definitions.
*   **`oath_schema.ldif`**: The custom OATH schema definition.
*   **`all-users.ldif`**: Contains all custom OUs, groups, and user definitions.
*   **`ldap_cli_login.py`**: The Python script for authentication and MFA enrollment.
*   **`generate_qr.py`**: The Python script for MFA QR code generation.
*   **`requirements.txt`**: Python dependencies for the scripts.
*   **`deploy.sh`**: Shell script for Stage 1: Initial Helm deployment.
*   **`stage2-configure.sh`**: Shell script for Stage 2: Applying custom configurations.
*   **`README.md`**: This guide.

## Required Python Libraries

All necessary Python libraries are listed in `requirements.txt`. Install them using:
```bash
pip install -r requirements.txt
```

---

## Automated Deployment and Configuration

The entire deployment and configuration process is now automated using two sequential shell scripts.

### Step 1: Deploy OpenLDAP (Run `deploy.sh`)

This script handles the cleanup and the initial Helm installation of the OpenLDAP server.

1.  **Ensure you are in your project directory.**
2.  **Make the script executable:**
    ```bash
    chmod +x deploy.sh
    ```
3.  **Run the deployment script:**
    ```bash
    ./deploy.sh
    ```
    *   This script will clean up any previous installations, install the OpenLDAP Helm chart, and print instructions to monitor the pods.
    *   **Crucially, wait for all OpenLDAP pods (`my-openldap-0`, `-1`, `-2`) to be in the `Running` and `1/1` READY state before proceeding to Step 2.** You can monitor them using `kubectl get pods -n ldap --watch`.

### Step 2: Configure OpenLDAP (Run `stage2-configure.sh`)

Once the OpenLDAP pods are fully up and ready, run this script to apply the OATH schema and create your custom users.

1.  **Make the script executable:**
    ```bash
    chmod +x stage2-configure.sh
    ```
2.  **Run the configuration script:**
    ```bash
    ./stage2-configure.sh
    ```
    *   This script will apply the custom OATH schema and create the `ou=users`, `ou=groups`, `cn=users` group, and the three custom users (`asmith`, `bjohnson`, `cbrown`) with `password123` as their initial password.

---

## Authentication and MFA Enrollment

After both deployment and configuration scripts have run successfully, you can test the authentication flow.

1.  **Start `kubectl port-forward` (in a NEW, separate terminal and leave it running):**
    ```bash
    kubectl port-forward -n ldap service/my-openldap 3890:389
    ```
    *The `ldap_cli_login.py` script is pre-configured to connect to `localhost:3890`.*

2.  **Run the Python Login Script:**
    ```bash
    python ldap_cli_login.py
    ```

3.  **When prompted:**
    *   **Username:** `asmith` (or `bjohnson`, `cbrown`)
    *   **Password:** `password123`

#### First-Time Login Flow:

-   The script will detect that MFA is not yet configured for this user.
-   It will automatically generate a new MFA secret, save it to the user's LDAP profile, and display a **QR Code** in the terminal.
-   Scan this QR code with your OTP app.
-   The script will wait for you to press 'y' to confirm.
-   The login process for this first time is now complete.

#### Subsequent Logins:

-   Enter the username and password.
-   The script will detect that MFA is configured.
-   It will now prompt you for the 6-digit "OTP Code".
-   Enter the code from your app to complete the authentication.
