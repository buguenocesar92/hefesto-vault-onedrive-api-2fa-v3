# Credenciales fuera de la base de datos y de Git

Los archivos reales son privados; el ZIP solo incluye `.env*.example`. `sudo ./setup.sh prepare` crea las claves aleatorias, sin imprimirlas y sin sobrescribir valores existentes.

| Archivo | Contenido |
|---|---|
| `.env` | Dominios, puertos y opciones generales; también ignorado |
| `.env.authelia` | Claves de sesión/cifrado/JWT y contraseña SMTP |
| `.env.rclone` | Clave del config cifrado y, opcionalmente, client secrets Microsoft app-only |
| `.env.replica` | Clave independiente y credenciales app-only de la réplica |
| `.env.api` | Tokens externos de lectura y administración |

Docker Compose inyecta cada archivo únicamente a sus servicios. Los client secrets app-only se configuran con variables `RCLONE_CONFIG_<REMOTO>_CLIENT_SECRET` (nombre del remoto en mayúsculas). Completar Client ID, tenant y habilitar `client_credentials` según el ejemplo. Para la réplica conservar `drive_id` y la definición de union en el archivo cifrado: el validador inspecciona esa topología. Credenciales no deben quedar también duplicadas en `rclone.conf`.

## Dos excepciones necesarias

1. OAuth delegado de cuentas personales: los access/refresh tokens rotan y Rclone los persiste en **rclone.conf cifrado**, fuera de la base de datos y de Git. No se fuerzan tokens rotativos a una variable estática, porque puede impedir conservar la renovación. Usar app-only autorizado cuando corresponda si se desea client secret estático en env.
2. Authelia: el enrolamiento TOTP individual necesita persistencia y se guarda cifrado en SQLite. La clave `AUTHELIA_STORAGE_ENCRYPTION_KEY` queda **fuera de SQLite**, en `.env.authelia`. La contraseña humana se guarda únicamente como hash Argon2id en `users_database.yml`, también ignorado. Trasladar todo el enrolamiento TOTP a env no es una función nativa de esta implementación y no se afirma que lo haga.

Esto evita guardar contraseñas de servicios/tokens API en BD; no significa que la base no tenga ningún material sensible cifrado. Guardar env en disco cifrado y copias de seguridad cifradas. Root y operadores Docker pueden leer entornos de contenedores: `.env` no es un gestor de secretos.

## Evitar versionado

`.gitignore` excluye `.env`, `.env.*` reales, `secrets`, configs OAuth activos, usuarios, bases, cachés y runtime; permite solo plantillas `.example`. Antes de cada commit ejecutar `./scripts/check-secrets.sh`. No compartir `docker inspect`, config expandida ni trazas de shell. Si ya se subió un secreto a Git: revocarlo/rotarlo, retirarlo del índice y sanear el historial; añadir `.gitignore` no lo elimina de commits anteriores.

No ejecutar `source .env.*`; estos archivos pertenecen al parser de Compose. Para contraseñas SMTP con `$` o `#`, usar comillas simples conforme a dotenv. Las claves autogeneradas son valores seguros sin interpolación. Editar mediante `sudoedit` o un editor privado, nunca pegar claves en un comando que quede en historial.

## Migración desde el ZIP anterior

Detener el stack en una ventana sin cargas pendientes; respaldar configs, claves y bases. Conservar las carpetas de datos. Al ejecutar `prepare`, `scripts/init-env.py` importa las antiguas claves de `secrets/*` si existen y aún no hay archivo env, para no perder capacidad de descifrar. No borra las claves anteriores. Verificar funcionamiento y recuperación antes de retirarlas. No regenerar `AUTHELIA_STORAGE_ENCRYPTION_KEY` sobre una base existente. Añadir los nuevos dominios de consola/API a `.env` siguiendo `.env.example`.
