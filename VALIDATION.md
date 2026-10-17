# Verificación — Hefesto Vault v3

Completado en el entorno de generación:

- Nueve pruebas HTTP reales locales del gateway API, con montaje sustituido por carpeta temporal exclusivamente en el test: autenticación, rol lector, CRUD, rechazo de traversal/symlinks, límite de carga, origen, montaje ausente y rename sin sobrescritura.
- Seis pruebas de réplica con CLI simulada: drives independientes, destino duplicado, union recursivo, cuenta caída, origen vacío y flags de simulación/histórico/límite de borrados.
- Invariantes estáticas de Compose: red interna, puertos solo en Caddy, UID no privilegiado, propagación FUSE y política two_factor.
- Render de configuraciones de laboratorio sin secretos embebidos, sintaxis Python/Bash/POSIX sh y sintaxis JavaScript.
- ZIP verificado por CRC y lista permitida: no incluye archivos env privados, tokens, bases, cachés ni claves reales.

No ejecutado: Docker/pull/build, validadores nativos Caddy/Authelia, navegador o revisión visual renderizada, montaje FUSE real, autenticación Microsoft, SMTP, HTTPS, QR, sincronización real, carga de rendimiento ni auditoría de seguridad. Docker y credenciales no están disponibles aquí.

La interfaz fue implementada con CSS responsive y controles funcionales, pero su experiencia visual debe revisarse en navegador tras desplegar. Las pruebas locales de API no certifican compatibilidad de rename/atomicidad con todos los remotos OneDrive ni rendimiento en producción. Seguir README y TROUBLESHOOTING.md antes de exposición pública; revisar imágenes y fijar versiones por digest. El paquete no se presenta como producción auditada.
