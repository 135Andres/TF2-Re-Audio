# TF2 Re-Audio — Plan (v5, 2026-10-15)

> Documento de referencia para evaluación externa. Sustituye a v4 (2026-10-13). Las tareas detalladas y la propiedad de archivos están en `TASKS.md`; la auditoría de UX en `AUDITORIA_UX.md`; el estado del trabajo no commiteado en `docs/local-ui-review.md` y el protocolo de prueba humana en `docs/milestone-wave2.md`.

## 1. Resumen para el evaluador

**Qué es:** app local para que un grupo de amigos de TF2 reemplace voces del juego por grabaciones propias. Cada PC instala las tomas en `tf/custom/tf2reaudio/sound/vo/` como WAV con extensión `.mp3`. La UI es un sitio local (`http://127.0.0.1:8440`) abierto en el navegador; no hay backend central. La colaboración (grupo/sync/túnel) es opcional y posterior.

**Estado a 2026-10-15:**

| Ola | Estado | Evidencia |
|---|---|---|
| **0 · Fundaciones** | **Hecha y en `master` (`ccb7a94`)** — T0–T10 + T7 aislado | `python -m unittest` 173 passed / 7 skipped (2026-10-13, Linux, Chromium opcional). CLI `doctor`/`import-wav`/`apply` funcionan contra fixtures. |
| **1 · Uso local (web)** | **Candidato privado en disco, consolidación en curso** — T14–T17 + T19 candidato | Suite Linux con Chromium: 179 pruebas, OK, 2 omitidas. CSP de T14 integrado y comprobado en navegador; ZIP reproducible y arranque extraído verificados. Catálogo y audio original del VPK real comprobados en Linux. Sin validación de micrófono físico, reemplazos dentro del juego ni Windows. |
| **2 · Hito humano** | **Bloqueante y pendiente** | Requiere Windows 10/11 nativo + TF2 real en Casual mid-game (`snd_restart`). Sin esto no se autoriza Ola 3. Protocolo en `docs/milestone-wave2.md`. |
| **3 · Colaboración** | **No iniciada** | Falta `group.py` (T11), `sync.py` (T12), `test_integration_sync.py` (T13), integración de `tunnel.py` y `web/group.js` (T18). |
| **4 · Usuarios + a11y** | **No iniciada** | 5 personas nuevas, teclado/zoom 200%/lector — criterio: 4/5 completan MEDIC! sin ayuda. |
| **5 · Release final** | **No iniciada** | T19 se regenera tras Ola 4; T20 solo si la prueba lo pide. |

**Preguntas para el evaluador:** ¿Es razonable el orden vertical (validar local antes de red)? ¿Falta algún riesgo de seguridad/integridad en el modelo de datos y sync? ¿El criterio de aceptación de cada ola es verificable? ¿Qué recortarías para llegar a un release local sin colaboración?

## 2. Objetivo y no-objetivos

**Objetivo:** una persona nueva graba una voz (p. ej. `soldier/medic`), la escucha, la instala en TF2 y la recupera si se arrepiente — sin cuenta, sin red y sin ayuda verbal. Luego, opcionalmente, un grupo comparte esas tomas con conflictos sin pérdida.

**No-objetivos v1:** editor multipista, voces con IA, link fijo del host (requiere dominio), actualización automática, app nativa de escritorio, i18n más allá de `web/strings.js` (UI solo en inglés por decisión vigente).

## 3. Hechos, hipótesis y pendientes de verificar

| Hecho | Origen | Confianza |
|---|---|---|
| Voces son `.mp3` (44.1 kHz mono) en `tf2_sound_vo_english_dir.vpk`, 12 728 entradas | Índice VPK leído en esta máquina | Verificado |
| `tf/custom/<mod>/sound/vo/` suena en Casual; WAV renombrado a `.mp3` funciona | Prueba del usuario (Scout) | Verificado |
| RCON + `snd_restart` funcionan en el menú; `127.0.0.1` es suficiente | Prueba del usuario | Verificado |
| TF2 solo monta carpetas nuevas de `tf/custom/` al arrancar; archivos dentro de carpeta ya montada sí se detectan | Motor Source | Verificado localmente |
| Lanzadores abren con doble clic y descargan Python embeddable verificado en Windows | Código T6 | Probado solo en Linux; Windows documentado en `docs/launchers.md` |
| `snd_restart` en mitad de Casual: duración del tirón, si corta el audio | — | **No verificado — bloquea Ola 2** |
| `rcon.send()` real necesita eco vacío para detectar fin de respuesta | Sospecha `TASKS.md:208` | **No verificado** |
| Micrófono en Windows, otros navegadores, lectores | — | **No verificado** |
| Túnel Cloudflare Quick Tunnel para host | Docs CF — URL variable, sin SLA | Probado aislado, no integrado |

`phase0_test.py` fue un prototipo con ffmpeg/lame y dos bugs reproducidos (VPK truncado colgaba, RCON fallaba con cabecera fragmentada). Ya reemplazado por T2/T3 robustos.

## 4. Decisiones vigentes

| Tema | Decisión | Implicación |
|---|---|---|
| Idioma UI | Solo inglés | Textos centralizados en `web/strings.js` para añadir es después sin reescribir. |
| Distribución | ZIP con `TF2ReAudio.cmd` + `tf2reaudio.sh` | En Windows descarga Python embeddable oficial (SHA-256 fijado) si falta ≥3.10. Sin admin/winget. |
| Visibilidad (decisión del usuario, 2026-10-15) | Mantener el proyecto privado por ahora | Solo candidatos locales para revisión; no publicar repositorio, ZIP ni releases. Elección de licencia aplazada. |
| Prioridad de validación (decisión del usuario, 2026-10-15) | Hacer funcional y comprobar primero el recorrido local en Linux | Windows sigue sin probar y se pospone hasta estabilizar Linux; no impide corregir ni validar el uso local. El hito completo sigue pendiente antes de colaboración. |
| Código | Paquete Python `tf2reaudio/`, solo stdlib | `__version__ = "0.1.0"`, `PROTOCOL_VERSION = 1`. Persistencia siempre vía `util.atomic_write`. |
| Descarga futura | GitHub Releases + `GET /download` del host, pendiente de autorización futura | Por ahora se prepara el ZIP local; no se publica ni se habilita descarga pública. |
| Aplicar al juego | Manual por defecto (`Apply N changes to TF2` → `snd_restart`) | Auto solo si el hito humano mide tirón aceptable. |
| Cuentas | Sin contraseñas; token de dispositivo 32 bytes, en red solo SHA-256 | Si se pierde acceso, un admin re-invita. |
| Primer uso | Sin cuenta y sin red (`Start solo`) | Grupos opcionales. |
| Conflictos | Nunca se pierde una toma por sincronizar | Conflictos se conservan ambos y se resuelven explícitamente. Lamport, no reloj de pared. |
| Privacidad `doctor` | Nunca imprime tokens ni contraseña RCON | Reporte copiable con `--copy`. |

## 5. Arquitectura

```
PC de cada miembro (todas iguales)
┌──────────────────────────────────────────────────────────┐
│ navegador ─► 127.0.0.1:8440  (UI + API local)            │
│                 │                                        │
│   tf2reaudio (paquete Python)                            │
│    ├─ steam    → encuentra TF2 (auto + manual)            │
│    ├─ vpk      → lista/lee originales                   │
│    ├─ catalog  → comandos → archivos                    │
│    ├─ store    → tomas, historial, conflictos (atómico)  │
│    ├─ game     → instala en tf/custom, RCON snd_restart  │
│    ├─ group    → identidad, miembros, invitaciones       │
│    ├─ sync     → cliente/servidor de sincronización      │
│    └─ tunnel   → cloudflared (solo si eres host)         │
└──────────────────────────────────────────────────────────┘
        ▲ sync HTTPS (solo API, nunca la UI)
        ▼
Host del día = cualquier miembro con "Host for the group" activado
```

- UI siempre local. Micrófono: `getUserMedia` con mensajes específicos para `NotAllowedError`/`NotFoundError`/`NotReadableError`/`OverconstrainedError` y `track.stop()` inmediato.
- Instancia única: segunda ejecución solo abre el navegador si `/api/ping` responde; puerto guardado en `data_dir()/instance.json`.
- Datos fuera del programa: `%APPDATA%\TF2ReAudio` (Windows) / `~/.local/share/tf2reaudio` (Linux). Sobreviven a mover/actualizar la carpeta.
- Prioridad baja: `os.nice(10)` / `BELOW_NORMAL_PRIORITY_CLASS`.
- Sync: poll 15 s con ETag → 304 si no hay cambios; blobs por hash, reanudable.
- `tf/custom` solo toca archivos cuyo hash cambió; `atomic_write` + `os.replace`.

## 6. Modelo de datos (`store`)

- **Take** inmutable: `take_id` (uuid4), `sha256`, `line` (p. ej. `soldier/medic`), `author_member_id`, `device_id`, `created_at` (solo display). Audio en `blobs/<sha256>.wav`.
- **Línea**: log de eventos `set_active(take_id | ORIGINAL)` con `event_id`, `parent_event_id`, Lamport `max(local,visto)+1`, `device_id`. Ganador `max(lamport, device_id)`. Conflicto = dos eventos con mismo `parent` sin `resolve` posterior; ambas tomas quedan audibles.
- **Variantes**: por defecto una take cubre todas (`medic01..03`); opcional `soldier/medic#02` con línea propia.
- **Override local**: `Use original on my PC only` no se sincroniza.
- **Estados por línea**: `saved_locally` · `pending_share` · `pending_apply` · `applied_requested`. Nunca "heard in game".
- **Retención**: activas y en conflicto nunca se podan; inactivas >5 por línea se podan (las más viejas).
- **Persistencia**: `collection.json` vía `atomic_write` + rotación `collection.json.bak`; lock de escritura por proceso; recuperación desde `.bak` si corrupción.
- **Sync**: unión de takes (grow-only set) + unión de eventos; idempotente y conmutativa.

## 7. Grupo y seguridad

- `group_id` (uuid) estable; cambiar host/link no crea otra colección; `Update link` solo cambia dirección.
- Roles `admin`/`member`; hostear no da permisos.
- Invitaciones: código `TF2-ABCD-EFGH` de un solo uso, TTL 24 h; se replican hasheadas; canje = evento Lamport. Riesgo aceptado: dos hosts desconectados canjeando el mismo código aceptan dos miembros distintos hasta sincronizar.
- API host: todo con Bearer token salvo `POST /api/redeem-invite` y `GET /download`. Rate limit 5/min/IP (`CF-Connecting-IP` tras Cloudflare). `protocol_version` mismatch → `426 Update the app`.
- Validación en ambos extremos (host y cliente): `line` existe en catálogo, ruta en índice VPK de voces, WAV = RIFF PCM 16-bit mono 44.1 kHz ≤10 s ≤1 MB, SHA-256 coincide.
- UI local: solo `127.0.0.1`, valida `Host` (`127.0.0.1:<port>` / `localhost:<port>`) + `X-TF2RA: 1` en POST contra CSRF/DNS rebinding; `X-Frame-Options: DENY`.
- RCON: `+ip 127.0.0.1`, contraseña aleatoria por PC en `data_dir()/settings.json`.
- Túnel: `cloudflared tunnel --url http://127.0.0.1:<port> --no-autoupdate`, binario por SO/arch con versión y SHA-256 fijados, `CREATE_NO_WINDOW` en Windows.
- Desinstalación en 3 niveles: Disable (mueve carpeta a `data_dir()/disabled_mod`), Delete collection (borra datos), Uninstall (guía para quitar Launch Options sin tocar otras).
- `doctor` sin secretos.

## 8. Experiencia (resumen; detalle en `TASKS.md` T14–T18)

1. **Primer inicio:** Start solo / Join friends, abre navegador.
2. **Setup:** TF2 detectado + Choose another folder; distingue `not_found`/`wrong_folder`/`vpk_unreadable`/`not_writable`; retira `tf2reaudio_test`; "Restart TF2 once" si carpeta nueva.
3. **Conexión TF2 (opcional):** Copy launch options (con aviso de conservar opciones), Check connection, fallback "Apply when you restart TF2".
4. **Dashboard:** 9 clases con SVG local, Suggested voice, progreso por comandos lógicos.
5. **Clase:** Start with MEDIC! / Continue, Pending only, Next line, pestañas (Voice menu / Pain & death / Domination / All), buscador, Details con variantes.
6. **Grabadora:** elegir micrófono + medidor `AnalyserNode`; Start/Stop (no hold), contador vs 10 s; preview; Retake/Discard/Save; variantes afectadas visibles; trim silencio desactivable; avisos `silent`/`clipping` no bloquean; `track.stop()` al cerrar/Escape.
7. **Cabecera:** TF2 (Connected/Not running/Not configured/Auth failed) y grupo (Synced X ago / Host offline – N saved here / Solo) + Apply N changes.
8. **Restaurar:** Play original (solo preview), Use original on my PC (override local), Restore original for collection (evento con Undo); History audible; conflictos visibles.
9. **Ajustes:** carpeta TF2, puerto RCON, test mod, export/import ZIP, disable/enable, desinstalación guiada.
10. **A11y objetivo:** WCAG 2.2 AA — teclado completo, foco visible, 200% zoom sin scroll horizontal, `aria-live`, botones con texto, contraste 4.5:1, hit target ≥44×44.

## 9. Orden de trabajo pendiente

| Ola | Entrega | Archivos dueños | Criterio de aceptación (bloqueante) |
|---|---|---|---|
| **1 — local (cierre)** | Consolidar T14–T17+T19 en `master`, ZIP candidato | `server.py`, `web/*`, `tools/build_zip.py`, `__main__.py` | `python -m unittest` verde; `doctor`/`import-wav` sin web funcionan; ZIP `dist/TF2ReAudio-0.1.0.zip` reproducible y sin secretos |
| **2 — hito humano** | Validar con TF2 real | `game.py`, `rcon.py`, `steam.py`, ZIP | Linux + Windows: voz importada suena tras restart; `apply` mid-Casual mide tirón; `doctor` RCON conectado; error `os.replace` en Windows documentado |
| **3 — colaboración** | `group`→`sync`→integración→túnel→UI grupo | `group.py`, `sync.py`, `server.py` (endpoints grupo), `web/group.js` | Dos dispositivos intercambian tomas offline, sobreviven desconexión, conflicto conserva ambas, ganador determinista, expulsión 401, blob interrumpido reanuda, cambio de host conserva `group_id` |
| **4 — usuarios + a11y** | 5 personas nuevas | `web/*` | 4/5 completan MEDIC! sin ayuda; ninguna acción esencial inaccesible con teclado/zoom/lector |
| **5 — release** | T19 final + T20 si aplica | `tools/build_zip.py`, `docs/README.md` | ZIP final validado y conservado privado; publicación aplazada por decisión del usuario; comodidad solo si Ola 4 la exige |

T7 no bloquea Olas 1–2. T14 entrega 2 (endpoints de grupo) solo después de T12.

## 10. Riesgos abiertos que el evaluador debe ponderar

- **Aceptación humana ausente:** la suite usa TF2/RCON/micrófono falsos; nada prueba `snd_restart` en partida ni Windows nativo.
- **RCON real:** si el cliente TF2 no hace eco del paquete vacío, `rcon.py` necesita fallback a "leer solo primer paquete".
- **`os.replace` en Windows:** puede fallar con `Access is denied` si TF2 tiene el archivo abierto; mitigado cerrando TF2, pero no medido.
- **Integridad de sync:** T12 debe revalidar todo lo recibido (catálogo, WAV, hash); la red no confía en el cliente.
- **Atomicidad:** `store`/`server` dependen de `atomic_write` + `.bak`; pruebas de corte de corriente/disco lleno son obligatorias antes de sync.

## 11. Cómo evaluar este plan

Un buen dictamen responde: (a) si el modelo Lamport+conflictos es suficiente para un grupo de amigos sin servidor permanente, (b) si el alcance de Ola 3 es mínimo viable o sobra, (c) si los criterios de aceptación son falsables, (d) qué recortar para un release solo-local en 1–2 semanas, y (e) qué pruebas adicionales exigir antes de tocar red.

## 12. Mapa de documentos

- `TASKS.md` — contratos por tarea (interfaces, archivos dueños, pruebas).
- `AUDITORIA_UX.md` — hallazgos y recomendaciones (P0–P2).
- `docs/local-ui-review.md` — informe del trabajo no commiteado (qué se hizo, qué no se probó).
- `docs/milestone-wave2.md` — protocolo del hito humano (Linux + Windows).
- `docs/launchers.md` — prueba manual de lanzadores en Windows.
- `docs/README.md` — instrucciones para el usuario del ZIP candidato.

## 13. Consideraciones añadidas en revisión 2026-10-15

Esta sección no cambia decisiones vigentes; añade huecos detectados en la revisión para que el evaluador y las olas futuras los cierren explícitamente.

### 13.1 Legal, licencia y cumplimiento con Valve
| Hueco | Por qué importa | Qué añadir al plan |
|---|---|---|
| Sin `LICENSE` en el repo | La licencia para una distribución pública sigue pendiente | El usuario decidió mantener el proyecto privado. No elegir licencia ni publicar; retomar esta decisión si autoriza una distribución pública |
| ToS de Steam / VAC | No se ha verificado una garantía de compatibilidad ni aprobación de Valve | Describir el comportamiento verificable: reemplaza audio local bajo `tf/custom` sin modificar binarios. No prometer seguridad frente a VAC ni aprobación de Valve |
| Uso de `vo_index.txt` y referencia externa | El plan cita `robbilookatme/tf2-voice-pack-reference` sin licencia; riesgo de copiar datos no licenciados | Mantener regla ya escrita en T5 (solo verificación manual) y auditar que ningún fixture/strings copie transcripciones |

### 13.2 Compatibilidad y matriz de soporte
El plan exige Windows y Linux pero no fija matriz. Fijarla hace falsables los criterios de Ola 2 y 4.

| Eje | Soportado v1 | No soportado / fuera de alcance | Prueba asociada |
|---|---|---|---|
| OS | Windows 10/11 x64 nativo, Ubuntu/Fedora/Debian x64 recientes | Windows 7/8, macOS, ARM sin Rosetta, Steam Deck/Proton sin validar | `docs/milestone-wave2.md` + `docs/launchers.md` |
| Steam | Instalación nativa (no Snap/Flatpak salvo ruta ya listada) | Múltiples bibliotecas en unidades con symlinks se prueban, Proton no garantizado | T1 `check_install` |
| Navegador | Chromium/Chrome y Firefox recientes, `getUserMedia` + `AudioContext` | Safari, WebView embebido, modo incógnito con micrófono bloqueado por policy | T16 + `test_web.py` |
| TF2 | Cliente nativo Steam con `+ip 127.0.0.1` | Servidores comunitarios con `sv_pure`, TF2 en modo `-insecure` no probado | Hito Ola 2 |
| Antivirus/firewall | Windows Defender; SmartScreen avisará por ZIP sin firma (documentar) | No se firma código en v1 | T19 README troubleshooting |

Añadir a T19 una sección de troubleshooting: SmartScreen, firewall solicitando permiso para `127.0.0.1:8440` y para `cloudflared`, y antivirus marcando `runtime/python.exe`.

### 13.3 Seguridad ampliada (además de lo ya cubierto en §7)
Lo ya previsto (Host check, `X-TF2RA`, `X-Frame-Options`, validación WAV/hash/catálogo, rate limit, `426`) es correcto. Faltaba explicitar:

- **CSP y cabeceras web local:** servir con `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` en API. Previene XSS si algún día un `label` curado contiene HTML y MIME-sniffing de WAV/MP3.
  - **Avance 2026-10-15:** integrado T14 (`55fb725`) en el checkout principal. La política añade `media-src 'self' blob:` para preescuchas locales. Cabeceras comprobadas en respuestas de la API, errores JSON, archivos y audio; Chromium verifica que un script inline se bloquea y que el audio blob se reproduce. El test falla al desactivar la política. El servidor local se reinició y su `/api/ping` entrega las nuevas cabeceras. Los errores del parser HTTP base se revisan por separado.
- **ZIP import/export:** validar tamaño descomprimido (zip-bomb), límite de entradas, y que ningún path escape de `collection/` (`..`/`/`). Ya hay `MAX_BYTES` para WAV; extender la misma validación al ZIP.
- **Path traversal en `sync_files`:** ya mitigado por `catalog.is_vo_path`, pero documentar como invariante de seguridad y añadir test de fuzz con `../` y `sound/vo/../../` .
- **Secretos en disco:** `settings.json` (contraseña RCON) y `group.json` (tokens hasheados) con permisos `0o600` en Linux y ACL equivalente en Windows si es posible; nunca incluir en `doctor --copy` ni en ZIP/logs.
- **Supply chain:** fijar no solo SHA-256 de `python-embed.zip` y `cloudflared`, sino también URL canónica `https://www.python.org/ftp/...` y verificación TLS; documentar fallback si python.org o GitHub está caído y cómo el usuario verifica el hash manualmente.

### 13.4 Privacidad y datos
- Minimización: micrófono solo tras gesto del usuario, `track.stop()` inmediato (ya previsto), y no persistir audio sin `Save`.
- Transparencia: declarar en README qué se almacena dónde (`data_dir()`), qué sale por red (solo con `Host for the group` activo, solo API sync, nunca UI ni micrófono), y retención: blobs huérfanos tras poda y `blobs/` sin referencia deben limpiarse en `store` sin borrar activos/en-conflicto.
- Consentimiento de grupo: al crear/unirse, mostrar en una línea qué comparte (tomas + historial de líneas + display names) y que el host ve IPs via `CF-Connecting-IP`.

### 13.5 Resiliencia, observabilidad y mantenimiento
| Tema | Estado actual | Añadido recomendado |
|---|---|---|
| Migración de esquema | `PROTOCOL_VERSION=1`, `collection.json` sin versionado interno | Añadir `format_version` en `collection.json`/`group.json`; T8/T11 deben rechazar versiones futuras con mensaje claro y migrar versiones antiguas sin pérdida |
| Corrupción doble (`json` + `.bak`) | Se recupera de `.bak` | Si ambos corruptos, renombrar a `.corrupt-<timestamp>` y arrancar colección vacía con aviso en UI + `doctor`, sin borrar blobs |
| Disco lleno / corte de corriente | `atomic_write+fsync+replace` cubre caso normal | Añadir pruebas de `ENOSPC` y corte a mitad de `atomic_write` antes de Ola 3; `doctor` debe reportar espacio libre en `data_dir()` |
| Logs y diagnóstico | No hay log persistente | Escribir `data_dir()/logs/tf2reaudio.log` rotativo (p. ej. 1 MB, 3 archivos), sin secretos, con nivel INFO; `doctor --copy` lo adjunta opcionalmente |
| Limpieza | Poda de tomas inactivas >5 | Añadir GC de blobs huérfanos y de `disabled_mod` antiguos, y test de que `export_zip` no incluye blobs huérfanos |
| Dependencias externas | Python y cloudflared fijados | Documentar EOL de Python 3.12 y política de actualización de `cloudflared` (cuándo se cambia SHA y cómo se comunica) |
| Actualización del juego | VPK puede cambiar con update de TF2 | `catalog.build` debe tolerar líneas nuevas/desaparecidas sin romper `store`; `doctor` avisa si `vo_index` del VPK no coincide con `vo_index.txt` del build |

### 13.6 Estrategia de pruebas y criterios falsables
El plan ya separa fixtures/fake servers y reserva TF2 real al hito humano. Para que el §11 sea evaluable, añadir:

- **Pirámide de pruebas:** unit (T0–T10, `test_server.py`), integración sync (T13, 6 escenarios ya definidos), e2e web con Playwright (5 tests existentes) + 5 personas Ola 4 con métrica 4/5 MEDIC! sin ayuda, cronómetro y checklist de teclado/zoom/lector.
- **Matriz de red:** T12 debe probar partición (host caído 5 min), reconexión con ETag 304, blob interrumpido y reanudado, y `426` por versión. Son los criterios de aceptación de Ola 3 que hoy están narrados pero no listados como checklist.
- **Performance budget:** `catalog.build` <200 ms para 12k entradas, `sync_files` sin tocar archivos con hash idéntico, UI con <100 ms de respuesta a `set_active` local (medido en Playwright).
- **No regresión Windows:** cada cambio en `util.atomic_write`/`server.py`/`game.py` debe pasar `test_build_zip` (permisos ejecutables) y `docs/launchers.md` checklist antes de cada ZIP.

### 13.7 Métricas de éxito y recorte para release solo-local
Para responder a §11(d), fijar métricas que permitan recortar:

- **Métrica primaria:** tiempo desde doble-clic hasta MEDIC! audible <5 min en 4/5 usuarios nuevos sin ayuda verbal.
- **Recorte propuesto si Ola 1 se alarga:** posponer variantes por archivo (`#02`), `Pending only` y `Suggested voice` a T20; mantener solo `soldier/medic` como camino dorado, más `Use original on my PC` y `Undo`. Esto ya es compatible con T8 sin reescribir modelo.

> Historial: v0 esqueleto · v2 incorpora auditoría · v3 adelanta uso local · v4 revisión local (T0–T10 en master, T14–T17 en disco) · **v5 consolida estado 2026-10-15 para evaluación externa sin cambiar decisiones** · **v5.1 añade §13 con huecos detectados en revisión (no cambia decisiones, solo explicita pendientes)**.
