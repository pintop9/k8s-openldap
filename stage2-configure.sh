#!/bin/bash

# STAGE 2: CONFIGURATION
# This script applies custom schema and user configurations to an already running OpenLDAP cluster.

set -e
RELEASE_NAME="my-openldap"
NAMESPACE="ldap"
# Admin credentials (from values.yaml)
ADMIN_PASSWORD="Helmadmin123!"

echo "--- STAGE 2: Starting Configuration ---"

echo "1. Applying OATH (MFA) schema..."
cat oath_schema.ldif | kubectl exec -i -n "$NAMESPACE" "${RELEASE_NAME}-0" -- ldapadd -Y EXTERNAL -H ldapi:///
echo "   Schema applied."

echo "2. Applying custom user and group definitions..."
cat all-users.ldif | kubectl exec -i -n "$NAMESPACE" "${RELEASE_NAME}-0" -- ldapadd -x -c -H ldap://my-openldap.ldap.svc.cluster.local:389 -D "cn=admin,dc=example,dc=org" -w "$ADMIN_PASSWORD"
echo "   Users and groups applied."

echo ""
echo "✅ STAGE 2 Complete: OpenLDAP is fully configured."
echo ""
echo "--- NEXT STEPS ---"
echo "You can now test the authentication with the Python CLI script."
echo "Follow these steps:"
echo ""
echo "1. In a new, separate terminal, start the port-forwarding:"
echo "   kubectl port-forward -n $NAMESPACE service/$RELEASE_NAME 3890:389"
echo ""
echo "2. In your project directory, run the login script:"
echo "   python ldap_cli_login.py"
echo ""
echo "3. When prompted, use one of the custom users (e.g., username 'asmith', password 'password123')."
echo "   This will trigger the first-time MFA enrollment and show a QR code."
echo ""
