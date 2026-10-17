# Hefesto Vault — respaldos unificados, interfaz web y API

Hefesto Vault reúne carpetas de varias cuentas OneDrive en un solo espacio. Permite navegar, subir, descargar, mover y eliminar archivos desde una consola web, File Browser o una API REST con tokens. Authelia protege el acceso humano con contraseña y TOTP. Una réplica programada opcional guarda un espejo con histórico en una tercera cuenta independiente.

Incluye una interfaz responsive con navegación por carpetas, búsqueda, progreso de carga, descarga y operaciones de archivos. Las tarjetas de montaje consultan la API real; el estado de réplica se verifica en los logs del servidor. No muestra métricas de nube inventadas.

**Guías:** [Credenciales y Git](CREDENTIALS.md) · [Réplica y Microsoft](REPLICATION.md) · [API REST](API.md) · [Solución de problemas](TROUBLESHOOTING.md) · [Validación](VALIDATION.md).

## Accesos

| Host de laboratorio | Uso | Autenticación |
|---|---|---|
| `console.storage.test` | Interfaz Hefesto Vault | Contraseña + TOTP |
| `files.storage.test` | Explorador File Browser | Contraseña + TOTP |
| `auth.storage.test` | Identidad/enrolamiento | Authelia |
| `api.storage.test` | Integración con sistemas | Bearer token |

Configurar los cuatro hosts en DNS/hosts; en producción reemplazarlos por tus subdominios reales. El API se publica por el mismo HTTPS de Caddy y valida su token en cada petición. No se ha desplegado públicamente al entregar este ZIP.


Infraestructura para un servidor Linux con Docker Compose v2. Portal de administración de archivos con contraseña y TOTP obligatorio, HTTPS y configuración Rclone cifrada. Se entrega código de infraestructura; no incluye cuentas Microsoft, dominio, SMTP ni secretos precompartidos. No se ha ejecutado Docker en el entorno de generación. Completar las pruebas de aceptación antes de producción.

## Arquitectura y límites

Cliente → Caddy HTTPS → Authelia (`two_factor`) → consola/File Browser → API o FUSE → Rclone union → OneDrive. Los sistemas externos usan la API con Bearer token.

- `net-storage` es interna. File Browser y la API solo pertenecen a esta red y no publica puertos. Authelia y Caddy tienen salida separada; Rclone tiene su propia red de salida para Microsoft. Una única red sin salida impediría OAuth, SMTP y ACME.
- El proxy elimina cabeceras de identidad del cliente y solo copia las autorizadas por Authelia. File Browser utiliza autenticación `proxy`, no tiene TOTP propio. Solo el grupo `storage-admins` puede acceder. Todo el portal, API y enlaces compartidos requieren 2FA.
- FUSE usa `SYS_ADMIN`, `/dev/fuse` y `apparmor:unconfined` exclusivamente en Rclone. Son permisos amplios: desplegar en VM dedicada. Portal sin capacidades, como UID 1000 y sistema raíz de solo lectura.
- Montaje de **directorio padre** con `rshared` hacia Rclone y `rslave` hacia portal. Un volumen Docker ordinario no propaga automáticamente submontajes FUSE. El directorio subyacente es root:root 000; el portal verifica FUSE y termina al perderlo.
- `union` agrega capacidad; **no replica archivos**, no es RAID ni respaldo inmutable. `mfs` requiere cuotas `Free`; los archivos no se dividen entre cuentas. No mantener el mismo nombre/ruta en varias cuentas: lectura `ff` y acciones `mfs` pueden resolver copias diferentes.
- La caché `writes` conserva archivos pendientes localmente. Carga HTTP exitosa no significa persistencia remota terminada. No borrar caché ni matar Rclone durante cargas. Un archivo debe caber en una cuenta y en el disco de caché; 20 GB es un objetivo, no un límite duro durante archivos abiertos.
- El cifrado de `rclone.conf` protege tokens en reposo; no cifra el contenido de los respaldos. Para eso evaluar un remoto `crypt` o respaldos cifrados con Restic/Borg y política 3-2-1. Los archivos `.env` son texto plano del host, no una bóveda cifrada.

## 1. Preparar host

Usar Linux nativo o VM Linux (por ejemplo Ubuntu/Debian) con Docker Engine, Compose v2, Python 3, util-linux, curl y FUSE. Docker Desktop Windows/macOS no es un destino soportado por este diseño de propagación.

```bash
sudo modprobe fuse
cp .env.example .env
# Editar .env antes de continuar.
sudo ./setup.sh prepare
```

`prepare` crea carpetas, permisos, propagación y claves aleatorias sin sobrescribir claves existentes. No requiere contraseñas/TOTP en `.env`. No ejecutar con `bash -x`. Conservar proyecto en disco cifrado y restringir acceso a root y operadores Docker (equivalentes a root).

Laboratorio: `MODE=lab`, `BIND_IP=127.0.0.1`, hosts `files.storage.test`, `auth.storage.test`, `console.storage.test` y `api.storage.test`. Añadir los cuatro a `/etc/hosts` o `C:\Windows\System32\drivers\etc\hosts` apuntando a 127.0.0.1. Para VM remota usar túneles SSH de puertos 80 y 443 o trabajar desde su escritorio. No abrir el laboratorio a Internet.

Producción: `MODE=production`, dominio base propio y cuatro subdominios DNS hacia el servidor; `BIND_IP=0.0.0.0`. Abrir 80/443 TCP para Caddy/ACME. Configurar `SMTP_ADDRESS` (STARTTLS, por ejemplo `smtp://host:587`), usuario, remitente y contraseña mediante un editor seguro en `.env.authelia` (`AUTHELIA_NOTIFIER_SMTP_PASSWORD`). Se exige SMTP en producción. Puertos 80/443 son configurables en Compose, pero el generador los restringe para mantener cookies, URLs y TLS coherentes.

## 2. Autorizar dos cuentas OneDrive

No iniciar todavía el montaje. La plantilla activa queda en `config/rclone/rclone.conf`. Editar cada remoto con el asistente:

```bash
sudo ./scripts/rclone.sh config
```

1. Elegir `e` para editar `onedrive1`, proveedor `onedrive`. Seguir el asistente de Microsoft, tipo de cuenta y unidad. Aceptar guardar.
2. En servidor sin navegador, responder `n` a autorización automática. En tu computador con navegador instalar **la misma versión** de Rclone y ejecutar el comando `rclone authorize "onedrive" ...` que indique el asistente. Iniciar sesión con la primera cuenta y pegar el resultado únicamente en el prompt del servidor. No enviarlo por chat ni guardarlo en Git.
3. Repetir `e` para `onedrive2`, cerrando sesión o usando ventana privada para elegir la segunda cuenta. Seleccionar la unidad correcta para cada una.
4. Mantener el remoto `union-onedrive` de la plantilla con `action_policy=mfs`, `create_policy=mfs` y upstreams `onedrive1:Respaldos onedrive2:Respaldos`.
5. Crear carpetas y verificar cuotas:

```bash
sudo ./scripts/rclone.sh mkdir onedrive1:Respaldos
sudo ./scripts/rclone.sh mkdir onedrive2:Respaldos
sudo ./scripts/rclone.sh about onedrive1:
sudo ./scripts/rclone.sh about onedrive2:
```

Ambas respuestas deben incluir espacio libre. Si Microsoft/SharePoint no entrega cuota, detenerse y elegir una política compatible; no suponer que `mfs` funcionará.

## 3. Cifrar tokens

`prepare` generó `RCLONE_CONFIG_PASS` en `.env.rclone`. Cifrar el archivo completo, sin pegar la contraseña en argumentos ni historial; Compose la carga desde el archivo env privado:

```bash
sudo ./scripts/rclone.sh config encryption set \
  --password-command 'printenv RCLONE_CONFIG_PASS'
sudo ./scripts/rclone.sh config encryption check
sudo ./scripts/rclone.sh --password-command 'printenv RCLONE_CONFIG_PASS' lsd union-onedrive:
```

No usar `rclone obscure` como sustituto del cifrado de configuración. Rclone necesita poder actualizar su archivo cifrado para refrescar OAuth, por eso se monta el directorio de configuración con escritura. No ejecutar editores/asistentes simultáneamente con el montaje. Para futuras ediciones detener portal y Rclone; pasar el mismo `--password-command` al asistente.

## 4. Inicializar administrador

```bash
sudo ./setup.sh render
sudo ./setup.sh admin
sudo ./setup.sh up
# Tras preparar, renderizar, validar e inicializar, también sirve:
# sudo docker compose up -d --build
sudo docker compose ps
```

`admin` solicita una contraseña mediante la CLI oficial de Authelia y luego su hash Argon2id. Pegar únicamente el hash, sin el prefijo `Digest:`. Se guarda el hash en `config/authelia/users_database.yml`; la contraseña no se conserva. File Browser recibe el mismo nombre de usuario y una contraseña aleatoria inutilizada por su modo proxy. `admin` se niega a sobrescribir datos existentes. Si una inicialización falla a medias, revisar el error y completar las operaciones restantes del script; no eliminar bases con datos para reintentarlo.

`runtime/authelia/configuration.yml` se genera como JSON compatible con YAML. No incluye el secreto SMTP: se carga desde `.env.authelia`, junto con las claves de sesión y cifrado. No versionar `runtime`. `config/authelia/configuration.yml.example` muestra el resultado de laboratorio.

## 5. HTTPS y QR de Google Authenticator / Authy

En producción Caddy obtiene certificados públicos automáticamente. En laboratorio usa su CA interna. Tras arrancar, copiar **solo** `data/caddy/caddy/pki/authorities/local/root.crt` e importarlo en el almacén de confianza del navegador/sistema. Nunca copiar `root.key`. No ignorar advertencias TLS como procedimiento habitual.

1. Abrir `https://console.storage.test` (o tu dominio). Redirige a Authelia.
2. Ingresar el usuario de `.env` y la contraseña elegida. Esto **todavía no permite acceder a archivos**.
3. Elegir registrar autenticador/One-Time Password. Authelia enviará verificación de identidad.
4. En producción llega al correo del administrador. En laboratorio el operador puede leer `sudo cat data/authelia/notification.txt` y abrir el enlace/código de verificación. Este archivo contiene enlaces sensibles: no compartirlo ni publicarlo; borrar su contenido al terminar el enrolamiento.
5. Authelia muestra el QR personal. En Google Authenticator: **+ → Escanear código QR**. En Authy añadir una cuenta y escanear. Introducir el código de seis dígitos para confirmar.
6. Solo al completar TOTP se autoriza el portal. Cerrar sesión en Authelia para invalidar la sesión de acceso; salir únicamente de File Browser no cierra la sesión SSO.

El QR se crea con la sesión verificada, nunca se entrega un secreto TOTP universal. Sincronizar hora del servidor y teléfono mediante NTP. La pérdida del teléfono requiere un procedimiento de recuperación administrado: verificar identidad fuera del portal, respaldar SQLite y consultar `authelia storage user totp --help` en la imagen fijada antes de borrar/re-enrolar el dispositivo. No desactivar `two_factor` para recuperar acceso.

## 6. Pruebas de aceptación obligatorias

```bash
# Laboratorio, desde host con resolución de los dominios:
PORTAL_URL=https://files.storage.test \
  CA_CERT=data/caddy/caddy/pki/authorities/local/root.crt \
  ./scripts/smoke.sh
# Producción: misma orden sin CA_CERT y con tu dominio.
```

Además verificar manualmente:

- Incógnito: ni `/`, `/api/resources/`, `/api/raw/...` ni `/share/...` son accesibles sin sesión, incluso enviando `Remote-User: admin` (script incluido).
- Contraseña correcta sin TOTP: archivos bloqueados. TOTP incorrecto: rechazado. TOTP válido: acceso. Usuario fuera de `storage-admins`: denegado.
- Subir un archivo de prueba, esperar la carga remota, encontrarlo en una de las cuentas y descargarlo desde OneDrive; comparar SHA-256 con el original. Probar lectura y borrado de ese archivo desechable.
- Detener Authelia (`docker compose stop authelia`): ninguna ruta del portal debe entregar archivos; puede responder error 5xx. Volver a iniciar Authelia.
- Sin cargas pendientes, detener Rclone: portal deja de servir y no crea archivos en el directorio base. Recuperar con `docker compose up -d rclone-mount`, esperar `healthy`, y `docker compose restart storage-portal`.
- Reiniciar servidor y verificar montaje `fuse.rclone` en ambos contenedores, HTTPS y flujo 2FA. Revisar que `docker compose ps` solo publique Caddy.

`depends_on: service_healthy` solo controla arranque; no es monitor de disponibilidad continua. El guardián del portal detecta desaparición del submontaje; cortes de Internet pueden mantener FUSE montado y devolver errores/datos en caché. Alertar sobre errores de Rclone, espacio local, cuotas, expiración OAuth, contenedores reiniciando y copias pendientes.

## 7. Arranque tras reinicio y operación

La propagación `rshared` no persiste por sí sola. Para producción instalar el proyecto en `/opt/storage-union` (o adaptar todas las rutas de la unidad) y habilitar antes de Docker:

```bash
sudo cp deploy/storage-mount.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable storage-mount.service
sudo systemctl start storage-mount.service
```

La unidad prepara el padre antes de `docker.service`; las políticas de reinicio levantan los contenedores. No desmonta volúmenes al parar. Sin systemd, ejecutar `sudo ./setup.sh prepare` y `sudo ./setup.sh up` después de cada arranque. Verificar siempre la prueba de reinicio; no habilitar actualizaciones automáticas de imágenes.

Para apagar: detener primero `storage-portal`, comprobar en logs que no quedan subidas pendientes, luego `docker compose down`. El margen de parada de 5 minutos no garantiza completar cualquier subida: esperar confirmación remota antes del apagado. No usar `down -v` como rutina.

Respaldar periódicamente `data/authelia` y `data/filebrowser` con los servicios correspondientes detenidos para consistencia SQLite/Bolt; guardar también los `.env` privados y configuraciones y CA de laboratorio en copia cifrada fuera del host. Mantener una copia separada de las claves; perder `AUTHELIA_STORAGE_ENCRYPTION_KEY` impide descifrar datos de Authelia. No rotarla cambiando el archivo sin migración oficial. El cache pendiente necesita preservarse tras fallas. Probar restauración en VM aislada sin dos escritores simultáneos sobre las mismas cuentas.

## 8. Paso a producción y versiones

Se conserva `filebrowser/filebrowser:v2.30.0` por compatibilidad con el requisito y `rclone/rclone:latest` por solicitud. **No se afirma que esas imágenes estén libres de vulnerabilidades.** Antes de exponer a Internet: revisar avisos de seguridad, actualizar a versiones corregidas compatibles, escanear imágenes y fijarlas por digest, incluido Alpine en Dockerfile. Repetir validación y pruebas tras cada cambio. Registrar los digests realmente ejecutados. No usar almacenamiento FUSE de nube para bases de datos activas; subir dumps/archivos cerrados.

Este despliegue administra un espacio común, no aislamiento multitenant. Para más usuarios provisionar el mismo identificador en Authelia y File Browser, definir permisos/scopes explícitos y ampliar las reglas de acceso sin conceder administración global automáticamente.

## Referencias oficiales

- https://rclone.org/union/
- https://rclone.org/onedrive/
- https://rclone.org/commands/rclone_mount/
- https://rclone.org/commands/rclone_config_encryption_set/
- https://www.authelia.com/integration/proxies/caddy/
- https://www.authelia.com/configuration/session/introduction/
- https://www.authelia.com/configuration/second-factor/time-based-one-time-password/
- https://github.com/filebrowser/filebrowser

## 9. Réplica programada (v2)

Consultar **REPLICATION.md** para activar un espejo en una tercera cuenta, con histórico, bloqueo de tareas simultáneas, validación de unidades independientes y cron. Incluye una plantilla app-only opcional para Microsoft 365 empresarial; no modifica el TOTP de Authelia ni promete credenciales eternas.
