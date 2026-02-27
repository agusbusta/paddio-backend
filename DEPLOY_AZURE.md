# Desplegar Paddio API en Azure (Container Apps)

Azure Container Apps cobra **por uso** (vCPU/memoria por segundo + requests). Escala a cero cuando no hay tráfico.

## Requisitos

- Cuenta Azure
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) instalado
- Base de datos PostgreSQL (ej. **Azure Database for PostgreSQL**, Neon, Supabase, o la que tengas)

---

## 1. Instalar CLI y extensión

```bash
az login
az upgrade
az extension add --name containerapp --upgrade --allow-preview true
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

---

## 2. Variables de entorno para el deploy

Definí (o exportá) antes de correr el script:

```bash
export RESOURCE_GROUP="paddio-rg"
export LOCATION="eastus"
export ENVIRONMENT="paddio-env"
export API_NAME="paddio-api"
export DATABASE_URL="postgresql://usuario:password@host:5432/Paddio-prod"
export SECRET_KEY="tu-clave-jwt-secreta"
```

---

## 3. Primer deploy

Desde la carpeta del backend:

```bash
cd paddio-backend
chmod +x scripts/deploy-azure.sh
./scripts/deploy-azure.sh
```

El script crea el resource group, el entorno, construye la imagen desde el Dockerfile y despliega. Al final muestra la **URL** del contenedor (ej. `https://paddio-api.xxx.azurecontainerapps.io`).

---

## 3.1 Deploy automático (todo en Azure, sin GitHub)

Para que cada **push a main** despliegue en Azure usando solo servicios Azure (código en **Azure Repos**, pipeline en **Azure Pipelines**), seguí la guía **[AZURE-DEVOPS.md](AZURE-DEVOPS.md)**. Ahí se explica: crear el proyecto en Azure DevOps, subir el código a Azure Repos, configurar la service connection y el pipeline a partir de `azure-pipelines.yml`.

---

## 4. Configurar variables después del primer deploy

Si no pasaste `DATABASE_URL` o `SECRET_KEY` al script, configuralas en el portal o por CLI:

```bash
az containerapp update --name paddio-api --resource-group paddio-rg \
  --set-env-vars "DATABASE_URL=postgresql://..." "SECRET_KEY=tu-clave"
```

En el portal: **Container Apps** → tu app → **Containers** → **Edit and deploy** → **Environment variables**.

---

## 5. Crear PostgreSQL en Azure (Azure Database for PostgreSQL - Flexible Server)

### Opción A: Por consola (portal)

1. En el portal Azure → **Create a resource** → buscar **Azure Database for PostgreSQL**.
2. Elegir **Flexible server** → **Create**.
3. **Basics**:
   - **Resource group:** crear uno nuevo, ej. `paddio-rg`, o usar el mismo que Container Apps.
   - **Server name:** ej. `paddio-db` (debe ser único globalmente; si no está libre, probar `paddio-db-tuNombre`).
   - **Region:** la misma que la app, ej. `East US`.
   - **PostgreSQL version:** 16 (o la que prefieras).
   - **Workload type:** Development (más barato) o Production.
   - **Compute + storage:** en Development suele venir **Burstable B1ms** (1 vCore, bajo costo). Dejá el storage por defecto.
4. **Authentication:**
   - **Admin username:** ej. `paddioadmin` (o `postgres` si lo permiten).
   - **Password:** contraseña segura; guardala para la URL.
5. **Networking:**
   - **Connectivity method:** **Public access (allowed IP addresses)**.
   - **Firewall rules:** agregar **Allow public access from any Azure service** (o añadir la IP de salida de Container Apps si querés restringir). Para probar rápido podés agregar una regla `0.0.0.0 - 255.255.255.255` (cualquier IP) y luego restringir.
6. Crear el servidor y esperar a que esté listo (unos minutos).
7. En el recurso → **Settings** → **Connection strings**. Copiá la **ADO.NET** o armá la URL a mano:
   ```text
   postgresql://USUARIO:CONTRASEÑA@NOMBRE-SERVIDOR.postgres.database.azure.com:5432/postgres
   ```
   La primera base de datos se llama `postgres`. Si querés una base aparte (ej. `Paddio-prod`), en el servidor → **Databases** → **Add database** → nombre `Paddio-prod` y usá esa en la URL en lugar de `postgres`.

### Opción B: Por CLI (Azure)

Mismo resource group y región que la app (ej. `paddio-rg`, `eastus`):

```bash
# Variables (ajustá contraseña y nombre de servidor si hace falta)
RESOURCE_GROUP="paddio-rg"
LOCATION="eastus"
SERVER_NAME="paddio-db"          # debe ser único en Azure (ej. paddio-db-tunombre)
ADMIN_USER="paddioadmin"
ADMIN_PASSWORD="TuPasswordSeguro123!"   # cambialo
DB_NAME="Paddio-prod"

# Crear el servidor (tarda varios minutos)
az postgres flexible-server create \
  --resource-group $RESOURCE_GROUP \
  --name $SERVER_NAME \
  --location $LOCATION \
  --admin-user $ADMIN_USER \
  --admin-password "$ADMIN_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --public-access 0.0.0.0

# Crear la base de datos
az postgres flexible-server db create \
  --resource-group $RESOURCE_GROUP \
  --server-name $SERVER_NAME \
  --database-name $DB_NAME

# Mostrar hostname (para armar la URL)
az postgres flexible-server show --resource-group $RESOURCE_GROUP --name $SERVER_NAME --query "fullyQualifiedDomainName" -o tsv
```

La **URL de conexión** queda:

```text
postgresql://paddioadmin:TuPasswordSeguro123!@paddio-db.postgres.database.azure.com:5432/Paddio-prod?sslmode=require
```

Azure PostgreSQL Flexible Server usa SSL por defecto; el backend ya añade `sslmode=require` si no está en la URL cuando no es localhost.

---

## 6. Frontend (Flutter)

En el `.env` del frontend poné la URL que te dio Container Apps:

```env
API_BASE_URL=https://paddio-api.xxx.azurecontainerapps.io
```

---

## Deploy automático al hacer push a main (CI/CD)

El repo incluye un workflow de **GitHub Actions** que despliega el backend en Azure cada vez que hacés **push a la rama `main`** y cambia algo en `paddio-backend/`.

### Configuración (una sola vez)

1. **Crear un Service Principal en Azure** (con acceso al resource group donde está la app):

   ```bash
   az ad sp create-for-rbac --name "paddio-github-deploy" \
     --role contributor \
     --scopes /subscriptions/<TU_SUBSCRIPTION_ID>/resourceGroups/paddio-backend \
     --sdk-auth
   ```

   Reemplazá `<TU_SUBSCRIPTION_ID>` por tu subscription ID (obtenelo con `az account show --query id -o tsv`).

   El comando devuelve un **JSON**. Copiá todo el bloque (desde `{` hasta `}`).

2. **Añadir el JSON como secret en GitHub**:

   - Repo en GitHub → **Settings** → **Secrets and variables** → **Actions**
   - **New repository secret**
   - Nombre: `AZURE_CREDENTIALS`
   - Valor: pegar el JSON completo del paso 1
   - Save

3. **Subir el workflow** (si no está ya):

   El archivo está en `.github/workflows/deploy-backend-azure.yml`. Hacé commit y push a `main` (la primera vez podés hacer push sin cambios en `paddio-backend/` y el workflow no se ejecutará; al tocar algo en `paddio-backend/` y pushear, sí).

### Comportamiento

- **Trigger:** push a la rama `main` cuando cambian archivos en `paddio-backend/**`
- **Qué hace:** hace login en Azure, construye la imagen desde el Dockerfile en Azure (ACR) y actualiza la Container App `paddio-api` en el resource group `paddio-backend`
- **Variables de entorno** (DATABASE_URL, SECRET_KEY, etc.): no se tocan en el deploy; siguen siendo las que configuraste en Azure (portal o primer deploy manual). El workflow solo despliega código nuevo.

Si usás otro resource group o nombre de app, editá las variables `RESOURCE_GROUP`, `API_NAME`, etc. en el workflow (sección `env` del step "Deploy to Azure Container Apps").

---

## Actualizar (redeploy manual)

Cada vez que cambies el código y quieras desplegar a mano:

```bash
cd paddio-backend
./scripts/deploy-azure.sh
```

---

## Ver logs

```bash
az containerapp logs show --name paddio-api --resource-group paddio-backend --follow
```

O en el portal: **Container Apps** → **paddio-api** → **Log stream** / **Log analytics**.

---

## Costo

- Container Apps: se cobra por consumo. Con poco tráfico suele ser bajo.
- [Precios Container Apps](https://azure.microsoft.com/pricing/details/container-apps/)
