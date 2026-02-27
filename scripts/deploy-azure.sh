#!/usr/bin/env bash
# Deploy Paddio API a Azure Container Apps (build desde código con Dockerfile).
# Uso: desde paddio-backend:
#   export RESOURCE_GROUP="paddio-rg"
#   export DATABASE_URL="postgresql://..."
#   ./scripts/deploy-azure.sh

set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-paddio-rg}"
LOCATION="${LOCATION:-eastus}"
ENVIRONMENT="${ENVIRONMENT:-paddio-env}"
API_NAME="${API_NAME:-paddio-api}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BACKEND_DIR"

if ! command -v az &>/dev/null; then
  echo "ERROR: Azure CLI no está instalado. Ver https://learn.microsoft.com/cli/azure/install-azure-cli"
  exit 1
fi

echo "==> Resource group: $RESOURCE_GROUP  Location: $LOCATION  App: $API_NAME"

# Crear resource group si no existe
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none 2>/dev/null || true

# Build y deploy desde código (usa el Dockerfile; puerto 8080 por EXPOSE)
az containerapp up \
  --name "$API_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --environment "$ENVIRONMENT" \
  --source .

# Si hay DATABASE_URL o SECRET_KEY, actualizar env vars del container app
if [ -n "$DATABASE_URL" ] || [ -n "$SECRET_KEY" ]; then
  echo "==> Configurando variables de entorno..."
  ENV_PAIRS=()
  [ -n "$DATABASE_URL" ] && ENV_PAIRS+=("DATABASE_URL=$DATABASE_URL")
  [ -n "$SECRET_KEY" ]  && ENV_PAIRS+=("SECRET_KEY=$SECRET_KEY")
  if [ ${#ENV_PAIRS[@]} -gt 0 ]; then
    az containerapp update --name "$API_NAME" --resource-group "$RESOURCE_GROUP" --set-env-vars "${ENV_PAIRS[@]}"
  fi
fi

echo ""
echo "✅ Deploy listo. URL del servicio:"
FQDN=$(az containerapp show --name "$API_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null)
echo "https://${FQDN}/"
echo ""
echo "Copiá esa URL y usala como API_BASE_URL en el .env del frontend."
echo ""
