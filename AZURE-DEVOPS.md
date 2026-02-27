# Todo en Azure: Repos + Pipelines + Container Apps

Guía para tener el código en **Azure Repos**, el pipeline en **Azure Pipelines** y el deploy en **Azure Container Apps**, sin usar GitHub.

---

## 1. Crear proyecto en Azure DevOps

1. Entrá a [dev.azure.com](https://dev.azure.com) e iniciá sesión.
2. Si no tenés organización, creala. Luego **New project**.
3. Nombre del proyecto (ej. `paddio`), visibilidad **Private**, **Create**.

---

## 2. Crear el repo en Azure Repos y pushear con un nuevo remote

### 2.1 Crear el repositorio en Azure DevOps

1. En el proyecto: **Repos** → **Files**.
2. Arriba a la izquierda hay un dropdown con el nombre del repo (ej. el nombre del proyecto). Clic ahí.
3. **New repository**.
4. **Name:** `paddio-backend`. Dejá el resto por defecto → **Create**.
5. Te queda el repo vacío. Clic en **Clone** (arriba a la derecha) y copiá la **URL** (HTTPS). Se ve así:
   ```text
   https://dev.azure.com/<tu-org>/<tu-proyecto>/_git/paddio-backend
   ```

### 2.2 Agregar el remote y pushear desde tu máquina

En la terminal, desde la carpeta del backend. El remote **azure** está configurado por **SSH**:

```bash
cd /Users/agustinbustamante/Desktop/paddio/paddio-backend

# Remote ya configurado: git@ssh.dev.azure.com:v3/agusbus95/paddio/paddio
git push azure main
```

**SSH:** Si todavía no agregaste tu llave pública en Azure DevOps: **User settings** (avatar) → **SSH Public Keys** → **New Key** → pegá el contenido de `~/.ssh/id_rsa.pub` (o `id_ed25519.pub`). Si no tenés clave, generá una con `ssh-keygen -t ed25519 -C "tu@email"`.

La primera vez que conectes, Git te va a mostrar el **fingerprint** del servidor. Verificá que coincida con el de Azure DevOps:
- **SHA256:** `ohD8VZEXGWo6Ez8GSEJQ9WpafgLFsOfLOtGGQCQo6Og`
- Escribí `yes` para continuar.

A partir de acá el código está en Azure Repos. Para seguir trabajando: `git push azure main` cada vez que quieras desplegar (y el pipeline se disparará solo).

---

## 3. Service connection (conexión a tu Azure)

El pipeline necesita permisos para desplegar en tu suscripción.

1. En el proyecto: **Project settings** (abajo a la izquierda) → **Service connections**.
2. **New service connection** → **Azure Resource Manager** → **Next**.
3. **Service principal (automatic)** → **Next**.
4. **Subscription:** tu suscripción. **Resource group:** `paddio-backend`.
5. **Service connection name:** por ejemplo `paddio-azure-connection` (este nombre va en el YAML del pipeline).
6. **Save**.

Anotá el nombre que usaste; lo vas a poner en `azure-pipelines.yml`.

---

## 4. Nombre del Azure Container Registry (ACR)

El primer deploy que hiciste con `az containerapp up` creó un registro de contenedores. Necesitás su nombre.

En tu máquina (con Azure CLI):

```bash
az acr list --resource-group paddio-backend --query "[].name" -o tsv
```

Copiá el nombre (ej. `paddiobackendacr123`). Ese valor va en `azure-pipelines.yml` en `acrName`.

---

## 5. Ajustar el YAML del pipeline

En el repo (Azure Repos), editá `azure-pipelines.yml`:

- **azureSubscription:** el mismo nombre que la service connection (ej. `paddio-azure-connection`).
- **acrName:** el nombre del ACR del paso anterior (ej. `paddiobackendacr123`).

Guardá y hacé commit (directo en la web o con push desde tu máquina al remote de Azure).

---

## 6. Crear el pipeline en Azure Pipelines

1. **Pipelines** → **Pipelines** → **New pipeline**.
2. **Azure Repos Git** (o **GitHub** si en el futuro volvés a usarlo).
3. Elegí el repo donde está el backend (en Azure Repos).
4. **Existing Azure Pipelines YAML file** → rama `main`, path `/azure-pipelines.yml`.
5. **Continue** → **Run**.

La primera vez puede pedir autorizar el uso de la service connection; aceptá.

El pipeline va a hacer build desde el Dockerfile y deploy a la Container App `paddio-api` en el resource group `paddio-backend`.

---

## 7. Comportamiento a partir de ahora

- **Código:** en Azure Repos (y opcionalmente en GitHub si lo dejás configurado).
- **Pipeline:** corre en Azure Pipelines; se dispara en cada push a `main` (trigger del YAML).
- **Deploy:** actualiza la Container App en Azure; no hace falta GitHub en el medio.

Para desplegar: hacé push a `main` en Azure Repos (o sincronizá desde tu máquina al remote `azure`). El pipeline se ejecuta solo y despliega en Azure.

---

## Resumen de nombres que tenés que configurar

| Dónde | Qué |
|------|-----|
| Service connection (Azure DevOps) | Nombre, ej. `paddio-azure-connection` |
| `azure-pipelines.yml` → **azureSubscription** | Ese mismo nombre |
| `azure-pipelines.yml` → **acrName** | Nombre del ACR (`az acr list -g paddio-backend ...`) |
| Resource group / app | Ya los tenés: `paddio-backend`, `paddio-api` |

Variables de entorno de la app (DATABASE_URL, SECRET_KEY, etc.) no se tocan desde el pipeline; siguen siendo las que configuraste en la Container App en Azure.

---

## Si el pipeline falla al hacer pull de la imagen

La Container App debe poder sacar la imagen del ACR. Si ves un error de tipo "unauthorized" o "pull image", asignale **managed identity** a la app y el rol **AcrPull** sobre el ACR:

```bash
# Managed identity de la app
az containerapp identity assign \
  --name paddio-api \
  --resource-group paddio-backend \
  --system-assigned

# Principal ID que mostró el comando anterior
PRINCIPAL_ID="<pegá el principalId del output>"
ACR_ID=$(az acr show -g paddio-backend -n <TU_ACR_NAME> --query id -o tsv)
az role assignment create --assignee $PRINCIPAL_ID --role AcrPull --scope $ACR_ID

# Decirle a la app que use esa identidad para pull
az containerapp registry set \
  --name paddio-api \
  --resource-group paddio-backend \
  --server <TU_ACR_NAME>.azurecr.io \
  --identity system
```
