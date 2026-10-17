# API REST de Hefesto Vault

API HTTPS para operar sobre el mismo FUSE que la interfaz. Host configurado en `API_HOST`; ejemplo `https://api.storage.test`. Docker solo publica Caddy en 80/443. `storage-api:8081` queda en red interna. Cada petición requiere `Authorization: Bearer <token>`; no hay endpoints públicos ni tokens en URLs.

La API de sistemas no usa TOTP interactivo: sus tokens son credenciales de servicio independientes. La consola web en `DASHBOARD_HOST` sí exige usuario + TOTP; Caddy añade internamente el token admin después de autorizar al grupo `storage-admins`. El navegador nunca recibe ese token. No añadir otros grupos al dashboard sin implementar permisos equivalentes.

## Credenciales y rotación

`setup.sh prepare` genera dos tokens aleatorios distintos en `.env.api`, permisos 0600:

- `STORAGE_API_READ_TOKEN`: listar y descargar.
- `STORAGE_API_ADMIN_TOKEN`: lectura y todas las mutaciones.

No se almacenan en base de datos. Cargar el token apropiado en el gestor de secretos/env del sistema consumidor. Estos tokens son compartidos por perfil, no por usuario: para revocación/auditoría por cliente será necesario extender el registro de identidades. Rotar sustituyendo el valor por uno nuevo de al menos 48 caracteres y recrear API y proxy con `docker compose up -d --force-recreate storage-api auth-proxy`. El token anterior deja de funcionar. Nunca ejecutar `docker compose config` sin `--quiet` en logs públicos porque puede expandir secretos.

## Operaciones

Todas las rutas `path`, `source` y `destination` son relativas a la raíz; no empiezan por `/`. Se rechazan `..`, `.`, enlaces simbólicos en la ruta, barras invertidas y componentes vacíos. La raíz no se puede borrar ni renombrar.

| Método | Endpoint | Función |
|---|---|---|
| GET | `/v1/health` | Montaje y límite de carga, autenticado |
| GET | `/v1/files?path=carpeta&offset=0&limit=200` | Listar directorio, máximo 1.000 por página |
| GET | `/v1/content?path=carpeta/archivo.zip` | Descargar archivo como attachment |
| PUT | `/v1/content?path=carpeta/archivo.zip` | Crear/reemplazar archivo con cuerpo binario |
| POST | `/v1/directories` | Crear carpeta: JSON `{"path":"carpeta"}` |
| PATCH | `/v1/entries` | Mover/renombrar: JSON `{"source":"a","destination":"b"}` |
| DELETE | `/v1/entries?path=carpeta/archivo.zip` | Eliminar archivo o carpeta vacía |

Las carpetas padre deben existir. PUT reemplaza el archivo al completarse la recepción mediante un rename; PATCH nunca sobrescribe destino. No se ofrece borrado recursivo masivo. JSON máximo 64 KiB; límite binario 2 GiB por defecto, ajustable mediante `API_MAX_UPLOAD_BYTES`. Se exige Content-Length y no se admiten cargas chunked. Hasta 16 conexiones de trabajo simultáneas; timeout de inactividad 30 segundos. Los directorios de más de 50.000 entradas se rechazan para limitar memoria. Dividir árboles grandes en subcarpetas.

Respuesta PUT indica `remote_durable:false`: la recepción en FUSE/VFS no certifica carga terminada en Microsoft. No usar esta API para escrituras transaccionales de bases de datos. Cambios de directorio entre upstreams o backend sin soporte de rename seguro pueden devolver error; no hay fallback que sobrescriba datos silenciosamente.

## Ejemplos con curl

Configurar DNS/hosts y confianza TLS primero. En laboratorio añadir `--cacert /ruta/root.crt` a curl; no desactivar la verificación TLS.

```bash
BASE=https://api.storage.test
read -rsp 'Token API: ' API_TOKEN; echo
# El token vive solo en esta shell. No pegarlo directamente en el historial.
curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" "$BASE/v1/health"

curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" \
  -H 'Content-Type: application/json' -X POST \
  --data '{"path":"integraciones"}' "$BASE/v1/directories"

curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" \
  --upload-file ./backup.zip "$BASE/v1/content?path=integraciones%2Fbackup.zip"

curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" \
  "$BASE/v1/files?path=integraciones"

curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" \
  "$BASE/v1/content?path=integraciones%2Fbackup.zip" --output copia.zip

curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" \
  -H 'Content-Type: application/json' -X PATCH \
  --data '{"source":"integraciones/backup.zip","destination":"integraciones/backup-final.zip"}' \
  "$BASE/v1/entries"

# Operación destructiva, solo sobre el archivo de prueba:
curl --fail-with-body -H "Authorization: Bearer $API_TOKEN" -X DELETE \
  "$BASE/v1/entries?path=integraciones%2Fbackup-final.zip"
unset API_TOKEN
```

En hosts compartidos, los argumentos de curl pueden verse en la lista de procesos: usar un SDK que lea el token de entorno o archivo de configuración privado de curl. No activar trazas de cabeceras. Consultar `api/openapi.json` para importar la especificación OpenAPI 3.1.

Errores: 400 ruta/cuerpo inválido, 401 token incorrecto, 403 permisos/origen, 404 inexistente, 409 conflicto/carpeta no vacía, 411 falta Content-Length, 413 tamaño, 415 tipo JSON, 501 rename seguro no soportado, 503 almacenamiento no disponible.

No hay CORS abierto. API destinada a backend-backend; no incrustar tokens admin en frontends externos. Preferir VPN/firewall allowlist cuando sea posible. Este gateway implementado con biblioteca estándar requiere revisión de seguridad y pruebas de carga en el host real antes de exposición pública. Las pruebas locales no sustituyen una auditoría.
