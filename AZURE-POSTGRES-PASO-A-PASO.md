# Paso a paso: crear PostgreSQL en Azure para Paddio

Seguí estos pasos en orden. Todo se hace en el portal de Azure (portal.azure.com).

---

## Parte 1: Crear el servidor PostgreSQL

### Paso 1 – Ir a crear el recurso correcto

1. Entrá a **https://portal.azure.com** e iniciá sesión.
2. Arriba a la izquierda, click en **“Create a resource”** (Crear un recurso).
3. En el buscador de la parte superior escribí: **PostgreSQL**.
4. En los resultados, elegí **“Azure Database for PostgreSQL”** (no “SQL databases”, no “Azure SQL”).
5. En la pantalla que aparece, elegí la opción **“Flexible server”** y click en **“Create”** (Crear).

---

### Paso 2 – Pestaña “Basics” (Conceptos básicos)

1. **Subscription:** dejá la que tengas (ej. “Azure subscription 1”).
2. **Resource group:**  
   - Click en “Create new”.  
   - Nombre: **paddio-rg** (o paddio-backend si preferís).  
   - Click OK.
3. **Server name:** escribí **paddio-db** (si dice que no está disponible, probá **paddio-db-tunombre**).
4. **Region:** **no uses East US**. Elegí una de estas:
   - **East US 2**
   - **West US 2**
   - **West Europe**
5. **PostgreSQL version:** dejá **16** (o la que venga por defecto).
6. **Workload type:** elegí **“Development”** (es la más barata).
7. **Compute + storage:** click en **“Configure server”**:
   - Dejá **Burstable**.
   - En **Compute size** elegí la más chica (ej. **B1ms**).
   - **Storage:** dejá el valor por defecto (ej. 32 GB).
   - OK.
8. **Administrator account:**
   - **Username:** ej. **paddioadmin** (no uses “postgres” si no lo permite).
   - **Password** y **Confirm password:** una contraseña segura (anotala, la vas a usar en la URL).
9. Click en **“Next: Networking >”** (abajo a la derecha).

---

### Paso 3 – Pestaña “Networking” (Red)

1. **Connectivity method:** elegí **“Public access (allowed IP addresses)”**.
2. **Firewall rules:**
   - Click **“Add current client IP address”** (para que puedas probar desde tu compu).
   - Para que la app en Azure pueda conectarse, agregá una regla más:
     - **Rule name:** AllowAzure  
     - **Start IP:** 0.0.0.0  
     - **End IP:** 255.255.255.255  
     (Así acepta desde cualquier IP; después podés restringir si querés.)
3. Click **“Next: Review + create”**.

---

### Paso 4 – Crear el recurso

1. Revisá que **Region** no sea East US (que te daba error).
2. Click en **“Create”**.
3. Esperá unos minutos hasta que diga que el deployment terminó.

---

## Parte 2: Crear la base de datos “Paddio-prod”

1. En el portal, buscá **“Resource groups”** (Grupos de recursos) y entrá.
2. Abrí el grupo **paddio-rg** (o el que hayas creado).
3. Click en el recurso que se llama **paddio-db** (tipo “Azure Database for PostgreSQL flexible server”).
4. En el menú izquierdo, en **“Settings”**, click en **“Databases”**.
5. Click en **“+ Add”** (Agregar).
6. **Database name:** **Paddio-prod**.
7. Click **OK**.

---

## Parte 3: Anotar la URL de conexión

1. Seguí en el recurso **paddio-db** (el servidor).
2. En el menú izquierdo, en **“Settings”**, click en **“Connection strings”** (o en **“Overview”** podés ver el host).
3. Anotá:
   - **Server name / host:** algo como `paddio-db.postgres.database.azure.com`
   - **Usuario:** el que pusiste (ej. paddioadmin)
   - **Contraseña:** la que definiste
   - **Base de datos:** Paddio-prod

La URL completa queda así (reemplazá con tus datos):

```
postgresql://paddioadmin:TU_CONTRASEÑA@paddio-db.postgres.database.azure.com:5432/Paddio-prod?sslmode=require
```

---

## Parte 4: Usar esa URL en el deploy de la API

En la terminal, desde la carpeta del backend:

```bash
cd /Users/agustinbustamante/Desktop/paddio/paddio-backend

export RESOURCE_GROUP="paddio-rg"
export LOCATION="eastus2"
export DATABASE_URL='postgresql://paddioadmin:TU_CONTRASEÑA@paddio-db.postgres.database.azure.com:5432/Paddio-prod?sslmode=require'
export SECRET_KEY='una-clave-jwt-secreta'

chmod +x scripts/deploy-azure.sh
./scripts/deploy-azure.sh
```

- Si creaste el resource group con otro nombre, usá ese en `RESOURCE_GROUP`.
- Si elegiste otra región (ej. West US 2), poné esa en `LOCATION` (ej. `westus2`).
- Reemplazá `TU_CONTRASEÑA` por la contraseña del usuario de PostgreSQL.

Cuando el script termine, te va a mostrar la **URL de la API** (ej. `https://paddio-api.xxx.azurecontainerapps.io`). Esa URL va en el **.env** del frontend como **API_BASE_URL**.

---

## Resumen rápido

| Qué hacer | Dónde |
|-----------|--------|
| Crear recurso | Create a resource → buscar “PostgreSQL” → **Azure Database for PostgreSQL** → **Flexible server** |
| Region | No East US; usar East US 2, West US 2 o West Europe |
| Crear base de datos | En el servidor → Databases → Add → nombre **Paddio-prod** |
| URL de conexión | postgresql://usuario:contraseña@host:5432/Paddio-prod?sslmode=require |
| Deploy API | `./scripts/deploy-azure.sh` con `DATABASE_URL` y `SECRET_KEY` exportados |
