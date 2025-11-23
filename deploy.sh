#!/bin/bash

# STAGE 1: DEPLOYMENT
# This script cleans up any previous release and installs the OpenLDAP chart.

set -e
RELEASE_NAME="my-openldap"
NAMESPACE="ldap"
CHART_NAME="helm-openldap/openldap-stack-ha"
VALUES_FILE="values.yaml"

echo "--- STAGE 1: Starting Clean Deployment ---"

echo "1. Cleaning up previous installations (if any)..."
helm uninstall "$RELEASE_NAME" -n "$NAMESPACE" > /dev/null 2>&1 || true
if kubectl get ns "$NAMESPACE" > /dev/null 2>&1; then
  echo "Waiting for namespace '$NAMESPACE' to be fully terminated..."
  kubectl delete namespace "$NAMESPACE"
  while kubectl get ns "$NAMESPACE" > /dev/null 2>&1;
  do
    sleep 1
  done
fi
echo "Cleanup complete."

echo "2. Installing OpenLDAP chart using '$VALUES_FILE'..."
helm install "$RELEASE_NAME" "$CHART_NAME" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  -f "$VALUES_FILE"

echo ""
echo "✅ STAGE 1 Complete: Deployment has been initiated."
echo ""
echo "--- NEXT STEPS ---"
echo "Please wait for the pods to be ready. You can monitor them with:"
echo "   kubectl get pods -n $NAMESPACE --watch"

echo ""
echo "Once all pods ('my-openldap-0', '-1', '-2') are in the 'Running' and '1/1' READY state, run the second script:"
echo "   ./stage2-configure.sh"
echo ""