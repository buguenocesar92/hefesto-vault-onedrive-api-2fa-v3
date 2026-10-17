# Solución de problemas

Antes de cambiar credenciales o borrar datos, revisar `docker compose ps`, `docker compose logs --tail=100 <servicio>` y `sudo ./setup.sh validate`. No pegar tokens, env ni configuraciones expandidas en tickets.

| Síntoma | Comprobación y solución |
|---|---|
| Falta Docker o Compose | Instalar Docker Engine y Compose v2 en el host Linux. Verificar `docker info` y `docker compose version`. |
| `/dev/fuse` inexistente | `sudo modprobe fuse`; comprobar `ls -l /dev/fuse`. Usar VM Linux nativa si Docker Desktop no permite propagación. |
| Montaje vacío / portal bloqueado | `findmnt -o TARGET,FSTYPE,PROPAGATION`; ejecutar `sudo ./setup.sh prepare` para restaurar rshared y luego `up`. No cambiar permisos de la carpeta base para forzar acceso. |
| `Transport endpoint is not connected` | Detener portal/API, esperar o investigar cargas pendientes, detener Rclone; un operador debe desmontar únicamente el submontaje huérfano tras comprobarlo. Nunca borrar la carpeta montada. Volver a preparar y levantar. |
| Config de Rclone no descifra | Comprobar que `.env.rclone` conserva la clave original. Si se migró, revisar la importación desde `secrets/rclone_password`. No generar una contraseña nueva sobre config existente. |
| `invalid_grant`, MFA o consentimiento Microsoft | Reautorizar el remoto delegado con `rclone config reconnect` durante mantenimiento. Revisar políticas del tenant. Para app-only verificar permiso Application, consentimiento, drive ID y secreto vigente. |
| `mfs` no encuentra destino | Revisar `rclone about` de cada fuente y cuota libre. El archivo debe caber completo en una cuenta; no se reparte en fragmentos. |
| Redirección infinita / cookies | Usar HTTPS y hosts distintos bajo BASE_DOMAIN. Borrar cookies antiguas tras cambio de dominio. Validar DNS, configuración generada y reloj. No acceder directamente a IP/puerto del backend. |
| Certificado no confiable en laboratorio | Importar el `root.crt` público de la CA de Caddy en el cliente. No distribuir claves privadas. En producción revisar DNS y conectividad ACME 80/443. |
| Falta correo/QR | En lab leer `data/authelia/notification.txt`. En producción comprobar SMTP y `.env.authelia`. Completar enlace de identidad antes de registrar el autenticador. |
| TOTP siempre inválido | Sincronizar NTP en servidor/teléfono y comprobar que se usa la cuenta correcta de Authelia. No confundirlo con MFA de Microsoft. |
| API 401 / 403 | Usar Bearer y token vigente; token de lectura no muta. Tras rotar recrear API y Caddy. No enviar token por query string. |
| API 411 / 413 | Enviar Content-Length; comprobar `API_MAX_UPLOAD_BYTES`. No enviar transferencia chunked. |
| API 409 / 501 al mover | Destino ya existe, carpeta no vacía o filesystem sin rename seguro. Elegir ruta libre; no sobrescribir silenciosamente. Probar la operación en el backend destino. |
| API 503 / consola sin conexión | Revisar FUSE, servicios y sesión Authelia. La API falla cerrada cuando falta el montaje. |
| API no disponible en contenedor Caddy recién iniciado | Confirmar que storage-api se construyó y está escuchando; revisar sus logs. `depends_on` no es una garantía de disponibilidad continua. |
| Réplica se niega a ejecutar | Revisar IDs distintos, config cifrado, fuentes accesibles y origen no vacío. El destino no puede formar parte de union. |
| `max-delete` bloquea réplica | Leer dry-run y evaluar borrados previstos. No quitar el límite por defecto sin entender el motivo. Las ejecuciones fallidas pueden dejar cambios parciales. |
| Archivo visible pero aún no llegó a OneDrive | Esperar drenaje de la caché VFS y comprobar logs/archivo remoto. No borrar la caché ni apagar con subidas pendientes. |
| UI no carga tras cambio de dominio | Ejecutar `render`, recrear Caddy y comprobar los cuatro hosts. `ui/config.json` se genera sin secretos. |
| Env faltante | Ejecutar `sudo ./setup.sh prepare` antes de Compose. No copiar ejemplos con valores GENERAR como credenciales reales. |

## Validación en el servidor

1. `sudo ./setup.sh validate` y `sudo ./setup.sh up`.
2. Revisar HTTPS, contraseña y enrolamiento TOTP completo en consola y File Browser.
3. Ejecutar `scripts/smoke.sh` contra ambos hosts web. En API probar sin token (401), lector (GET permitido, PUT 403) y admin con archivo desechable.
4. Crear carpeta, subir, descargar y comparar SHA-256; renombrar, borrar archivo y carpeta vacía.
5. Ejecutar dry-run, réplica y check; recuperar una versión anterior desde history.
6. Probar apagado/reinicio sin cargas pendientes y confirmar propagación FUSE.
7. Probar desconexión temporal de una cuenta y falta de cuota: deben generar errores visibles, nunca un éxito de respaldo falso.

## Recuperación

No ejecutar `rm -rf data`, `down -v` ni regenerar claves como método de reparación. Respaldar bases con servicios detenidos, restaurarlas junto con sus claves originales y validar en VM aislada. La copia espejo puede contener solo los datos de la última ejecución correcta; no es una instantánea ni un respaldo inmutable. No conectar dos instancias escritoras al mismo union durante una restauración.
