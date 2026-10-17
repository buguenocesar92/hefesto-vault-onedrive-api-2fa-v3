# Réplica independiente y autenticación Microsoft

## Qué cambia

Este paquete v2 añade un servicio `rclone-replica` sin FUSE y sin puertos, activado solo con perfil `backup`. Usa configuración y contraseña separadas del montaje. El destino fijo es `onedrive_backup:StorageMirror/current`; los archivos reemplazados o eliminados se conservan en `onedrive_backup:StorageMirror/history/<fecha-UTC>`.

Se mantiene `union-onedrive` con dos cuentas fuente. La tercera unidad de respaldo debe ser independiente, con capacidad para **todo el union más el histórico**. El script verifica IDs distintos; no puede certificar independencia administrativa, contractual o del proveedor. Si solo tienes dos cuentas, usa una como principal y otra espejo, renunciando a sumar ambas capacidades; esta variante requiere adaptar la plantilla y su validador.

`/mnt/respaldo-espejo/` sería una ruta local, no una cuenta OneDrive por sí misma. Aquí se usa el remoto directamente para evitar otro montaje.

## Configuración y primera ejecución

En instalación nueva seguir primero README. Si actualizas una instalación existente, fusionar estos archivos conservando `.env`, claves, bases y config activa; ejecutar `prepare` para generar únicamente la nueva clave que falte.

```bash
sudo ./setup.sh prepare
sudo cp config/replica/rclone.conf.example config/replica/rclone.conf
sudo chmod 700 config/replica
sudo chmod 600 config/replica/rclone.conf
sudo docker compose --profile backup run --rm --no-deps \
  --entrypoint rclone rclone-replica config
```

Autorizar independientemente `onedrive1`, `onedrive2` (las mismas unidades fuente que usa el portal) y `onedrive_backup` (tercera unidad). No copiar el archivo cifrado del montaje como configuración de réplica: se desean sesiones y escrituras de configuración separadas. Dejar `union-onedrive` exactamente como la plantilla. No editar esta configuración mientras cron trabaja.

```bash
sudo docker compose --profile backup run --rm --no-deps \
  --entrypoint rclone rclone-replica config encryption set
sudo ./scripts/replicate.sh --dry-run
sudo ./scripts/replicate.sh --apply
sudo ./scripts/replicate.sh --check
```

El servicio ya entrega `RCLONE_PASSWORD_COMMAND`, que lee `RCLONE_CONFIG_PASS` en `.env.replica`. No pasar claves en argumentos. El comando `--check` compara descargando el contenido; puede ser costoso en tiempo y tráfico. Solo registra una réplica como completada si `sync` finaliza con éxito. Un `--dry-run` nunca actualiza `last-success`.

Por defecto `MIRROR_MAX_DELETE=0` bloquea borrados del espejo. Para reflejar eliminaciones legítimas, revisar primero el dry-run y configurar un límite pequeño en `.env`, por ejemplo `MIRROR_MAX_DELETE=20`. Al superar el límite, la ejecución falla y **no es transaccional**: puede haber cambios parciales. Nunca utilizar `--ignore-errors` ni deshabilitar la protección para silenciar fallos.

El espejo con histórico reduce riesgo de propagar borrados, pero no ofrece inmutabilidad: quien tenga credenciales de respaldo puede borrar también el histórico. No hay limpieza automática del histórico; controlar cuotas y definir retención después de comprobar restauraciones. Es necesaria otra copia fuera de estas credenciales para protección ante compromiso del servidor.

## Programación

Después de validar manualmente los tres comandos, adaptar la ruta en `deploy/replica.cron.example` e instalar:

```bash
sudo install -m 644 deploy/replica.cron.example /etc/cron.d/storage-replica
```

La tarea se ejecuta diariamente a las 03:15, según zona horaria del host. `flock` impide solapamientos; logs en `data/replica/`. Monitorizar errores y antigüedad de `data/replica/last-success` (alarma si supera 26 horas con esta frecuencia). Los logs no tienen rotación automática: incluirlos en logrotate y aplicar retención. Cron requiere un MTA para alertas de correo; no se presume configurado. No se instala cron ni se toca OneDrive al generar este paquete.

En el preflight, cada cuenta debe responder y el union no puede estar vacío. No es una instantánea consistente: ejecutar durante una ventana sin escrituras y después de que la caché VFS termine las cargas. Un error transitorio o un archivo cambiado mientras se replica obliga a revisar y repetir. No se activa `--fast-list` por defecto; el proveedor y la profundidad del árbol condicionan su rendimiento.

Prueba de restauración: crear un archivo desechable, replicar y comprobar; modificarlo y repetir; verificar el original en history. Restaurar siempre a una carpeta temporal, comparar contenido, y solo después reponerlo al origen. Probar igualmente cuenta inaccesible, destino sin cuota y fallo de autenticación; ninguna de estas condiciones debe quedar registrada como éxito.

## Microsoft: token, TOTP y app-only son cosas diferentes

La sesión/TOTP del portal pertenece a Authelia y no cambia. Los tokens OAuth pertenecen a la conexión con Microsoft. Los refresh tokens tienen duraciones predeterminadas y se renuevan al usarse; pueden revocarse. No hay una regla universal que obligue a todo Rclone a pedir MFA exactamente cada 90 días. Las políticas de la organización pueden exigir nueva autenticación.

Para cuentas personales se mantiene OAuth delegado. Un client ID propio no convierte por sí solo esa conexión en autenticación de aplicación.

Para Microsoft 365 Business/SharePoint, con aprobación del administrador:

1. Registrar una aplicación en el tenant correspondiente y crear una credencial con vencimiento y responsable de rotación.
2. Conceder permisos Microsoft Graph de tipo **Application**, con consentimiento administrativo. Para lectura de fuentes preferir acceso de solo lectura; para escritura autorizar únicamente lo necesario. `Files.ReadWrite.All` es amplio: revisar permisos Selected y asignación explícita al recurso cuando sean compatibles, en lugar de conceder todo el tenant por defecto.
3. Configurar usando `config/rclone/app-only.conf.example`: `client_credentials = true`, `tenant = ...`, Client ID, secreto y `drive_id` explícito. El campo de Rclone es `tenant`, no `tenant_id`. En el asistente seleccionar drive ID/SharePoint para este flujo.
4. Cifrar el archivo, comprobar acceso de lectura y hacer una prueba controlada de escritura si corresponde. `rclone about` puede verificar cuota cuando el backend la ofrece, pero una respuesta sin navegador **no prueba** que el flujo sea app-only: un token delegado almacenado también funciona así.

App-only obtiene tokens de acceso nuevos con la credencial de aplicación; no elimina la expiración/revocación del secreto ni la necesidad de monitoreo. Documentar vencimiento y alertar con anticipación (por ejemplo 30 y 7 días), rotar con periodo de superposición y volver a verificar. No modificar ni eludir políticas de seguridad del tenant. La plantilla no realiza cambios en Azure ni asigna permisos automáticamente.

## Fuentes oficiales

- Rclone OneDrive y opciones client credentials: https://rclone.org/onedrive/
- Comportamiento de sync: https://rclone.org/commands/rclone_sync/
- Histórico y límites: https://rclone.org/docs/#backup-dir-dir
- Refresh tokens: https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens
- App-only: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow
