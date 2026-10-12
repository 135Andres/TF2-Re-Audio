# TF2 Re-Audio — Plan (v2, incorpora AUDITORIA_UX.md)

Las tareas para agentes están en `TASKS.md`.

## 1. Hechos comprobados (Fase 0, 2026-10-11)

| Hecho | Origen |
|---|---|
| Los audios de voz son `.mp3` (44.1 kHz, mono) dentro de `tf2_sound_vo_english_dir.vpk` (12,728 entradas). | Índice del VPK |
| Los archivos en `tf/custom/<mod>/sound/vo/` **suenan en Casual**. | Prueba del usuario |
| Un **WAV renombrado a `.mp3` funciona**, así que no hace falta codificar MP3. | Prueba del usuario (Scout) |
| RCON + `snd_restart` funcionan **en el menú**. | Prueba del usuario |
| TF2 solo detecta carpetas nuevas de `tf/custom/` **al arrancar**. Los archivos nuevos dentro de una carpeta ya montada sí se detectan. | Comportamiento del motor Source; volver a comprobarlo |

**Sin comprobar todavía:** el efecto de `snd_restart` en medio de una partida, Windows, el acceso al micrófono en Windows y la accesibilidad.

`phase0_test.py` es un **prototipo experimental**: usa ffmpeg/lame y tiene dos bugs que la auditoría reprodujo (el parser del VPK se cuelga si el archivo está truncado, y RCON falla si la cabecera llega fragmentada). No se reutiliza tal cual. Las tareas T2 y T3 lo reescriben bien.

## 2. Decisiones

| Tema | Decisión | Nota sobre la auditoría |
|---|---|---|
| Idioma de la interfaz | **Solo inglés** (decisión del usuario). | La auditoría pide español e inglés. Los textos quedan en un solo archivo (`web/strings.js`) para que añadir español después sea traducir y no reescribir. |
| Distribución | **Un ZIP con lanzadores**: `TF2ReAudio.cmd` (Windows) y `tf2reaudio.sh` (Linux). Funcionan con doble clic **o** desde la consola. | La auditoría pide abrir sin instalar Python a mano. En Windows, el lanzador descarga **Python embeddable oficial** (con SHA-256 fijado) si no hay Python ≥3.10. No hace falta winget ni permisos de administrador. |
| Código | **Paquete de Python** (`tf2reaudio/`) con módulos separados, solo biblioteca estándar. | Se abandona la regla del "archivo único": varios agentes pueden trabajar en paralelo y se prueba mejor. El usuario sigue recibiendo un solo ZIP. |
| Dónde se descarga | **GitHub Releases** del repo del usuario: un lugar fijo, independiente del host del día. Los amigos no necesitan cuenta para descargar. El host también puede servir el ZIP. | Auditoría 3.1. |
| Aplicar al juego | **Manual por defecto**: botón "Apply N changes to TF2" (manda `snd_restart`). El modo automático queda como preferencia **después** de medir el tirón. | Auditoría 3.4. |
| Cuentas | **Sin contraseñas.** Al aceptar una invitación, el equipo recibe un **token de dispositivo** aleatorio de 32 bytes; en la colección viaja solo su hash SHA-256. | Mejor que replicar hashes de contraseñas, que cualquier miembro podría intentar crackear sin conexión. Si se pierde el acceso, un admin re-invita. |
| Primer uso | **Sin cuenta y sin conexión.** "Start solo" funciona completo; los grupos son opcionales. | Auditoría 3.5 y fase 1. |
| Conflictos | **Ninguna toma se pierde por sincronizar.** Si hay conflicto, se conservan ambas y se muestran. No se usa el reloj de la PC para decidir. | Auditoría 3.6. |

## 3. Arquitectura

```
 PC de cada miembro (todas iguales)
 ┌──────────────────────────────────────────────────────────┐
 │ navegador ─► 127.0.0.1:8440  (UI + API local)            │
 │                 │                                        │
 │   tf2reaudio (paquete Python)                            │
 │    ├─ steam    → encuentra TF2 (auto + manual)            │
 │    ├─ vpk      → lista/lee los originales                │
 │    ├─ catalog  → comandos prioritarios → archivos        │
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

- La interfaz **siempre es local**. Aun así el micrófono puede fallar (permiso denegado, sin dispositivo, en uso), y la UI debe explicar cada caso ([MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)).
- **Instancia única:** si se abre la app dos veces, la segunda solo abre el navegador en la que ya corre.
- **Datos fuera de la carpeta del programa:** `%APPDATA%\TF2ReAudio` en Windows y `~/.local/share/tf2reaudio` en Linux. Sobreviven a actualizaciones y a mover la carpeta.

## 4. Modelo de datos (`store`)

Todo se guarda en archivos con **escritura atómica** (archivo temporal + `os.replace`), un **lock** de escritura único en el proceso y un **respaldo del manifiesto** (`collection.json` + `collection.json.bak`).

- **Toma (take):** inmutable. Tiene `take_id` (uuid4), `sha256`, `line` (comando lógico, p. ej. `soldier/medic`), `author_member_id`, `device_id` y `created_at`. Este último es solo para mostrar; no decide nada. El audio vive en `blobs/<sha256>.wav`.
- **Línea:** un registro de eventos `set_active(take_id | ORIGINAL)`. Cada evento lleva `event_id`, `parent_event_id`, un reloj **Lamport** y `device_id`.
  - El ganador es el de mayor `(lamport, device_id)`. Es determinista y no depende del reloj de la PC.
  - **Conflicto:** dos eventos con el mismo `parent`. Se marca la línea; ambas tomas siguen disponibles y se pueden escuchar.
  - "Restaurar el original para el grupo" = `set_active(ORIGINAL)`. Es un evento más, así que se puede deshacer, y un borrado viejo no "resucita" nada.
- **Alcance de variantes:** por defecto la toma se instala en todas las variantes (`medic01..03`). Opcionalmente, una variante puede tener su propia línea (`soldier/medic#02`).
- **Override local:** "Use original on my PC only" no se sincroniza.
- **Estados por línea** (los expone la API y los muestra la UI): `saved_locally` · `pending_share` · `pending_apply` · `applied_requested`. Nunca se usa "escuchado en el juego", porque enviar un comando no prueba que sonó.
- **Retención:** se conservan todas las tomas activas o en conflicto. Las inactivas se podan después de N=5 por línea, **nunca** si están en conflicto. Existen **Exportar e importar colección** (ZIP).
- **Sincronización** = unión de tomas (un conjunto que solo crece) + unión de eventos. Es idempotente y conmutativa, y los blobs se piden por hash, así que una descarga interrumpida se puede reanudar.

## 5. Grupo y seguridad

- **`group_id`** (uuid) es la identidad estable. Cambiar de host o de link **no** crea otra colección. "Update link" solo cambia la dirección.
- **Roles:** `admin` (quien creó el grupo, y los que él promueva) y `member`. **Hostear no da permisos:** el host solo transporta datos.
- **Invitaciones:** un admin genera un código de un solo uso, válido 24 h. Con él, el miembro recibe su token de dispositivo.
- **Expulsar o re-invitar** son eventos de membresía (con reloj Lamport) que se replican. **Riesgo aceptado:** un host que no ha sincronizado una expulsión podría aceptar al expulsado hasta su siguiente sincronización. En un grupo de amigos es aceptable, y queda documentado.
- **API pública del host:** todo requiere token, excepto `redeem-invite` y `GET /download`. Login limitado a 5 intentos por minuto por IP. Lleva `protocol_version`: si no coincide, se rechaza con un mensaje claro ("Update the app").
- **Validación en ambos extremos** (el host valida lo que sube y el cliente lo que baja):
  - La ruta debe existir en el índice del VPK de voces.
  - El contenido debe ser un WAV RIFF PCM de 16 bits, mono, 44.1 kHz y de ≤10 s.
  - El SHA-256 debe coincidir con el contenido.
  - Tamaño máximo de 1 MB.
- **UI local:** solo escucha en `127.0.0.1` y comprueba el header `Host` (contra *DNS rebinding*).
- **RCON:** `+ip 127.0.0.1` y una contraseña aleatoria por PC, guardada en la carpeta de datos (no junto al programa).
- **Túnel:** Cloudflare Quick Tunnel para empezar. Está pensado para pruebas: no garantiza disponibilidad y su link cambia ([docs](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)). Por eso existe "Update link" y la reconexión con el mismo `group_id`. `cloudflared` se descarga con SHA-256 verificado y solo si eres host.
- **Desinstalación guiada** en tres niveles:
  1. *Disable voices*: mueve la carpeta fuera de `tf/custom`.
  2. *Delete collection*: borra los datos locales.
  3. *Uninstall*: borra todo y muestra cómo quitar las Launch Options **sin borrar las demás opciones que tengas**.
- **Diagnóstico** (`doctor`): un reporte sin secretos (sin tokens ni contraseña RCON) para pedir ayuda.

## 6. Rendimiento (que no afecte al juego)

- El juego solo lee archivos locales; la app nunca está en su camino.
- La app corre con prioridad baja (`os.nice(10)` / `BELOW_NORMAL_PRIORITY_CLASS`).
- La sincronización consulta cada 15 s con ETag; si no hubo cambios, el host responde `304`. Las descargas se piden por hash.
- `snd_restart` es manual por defecto. Medir su efecto en partida es un criterio de aceptación de T8.
- Escribir en `tf/custom` toca solo los archivos que cambiaron.

## 7. Experiencia de uso (resumen; detalle en las tareas web)

1. **Primer inicio:** "Start solo" o "Join friends". Se abre el navegador automáticamente.
2. **Asistente:** muestra la instalación de TF2 detectada con un botón "Choose another folder". Distingue "TF2 not found", "Wrong folder" y "Can't write here".
   - Ofrece retirar la carpeta de prueba `tf2reaudio_test` si existe.
   - Explica "Restart TF2 once" cuando se crea la carpeta del mod.
3. **Conexión con TF2 (opcional y posterior):** botón "Copy launch options", con el aviso "keep your existing options", y un botón "Check connection". Si falla, se ofrece "Apply when you restart TF2". Una conexión fallida nunca se presenta como pérdida de la grabación.
4. **Dashboard:** las 9 clases con imagen (incluida en el paquete o guardada en caché, con un respaldo de texto) y "Suggested voice: <name>". El progreso cuenta **comandos lógicos**, no archivos.
5. **Página de clase:** "Start with MEDIC!" / "Continue recording", el filtro "Pending only" y el botón "Next line". Pestañas: Voice menu · Pain & death · Domination & revenge · All lines (con buscador). Los nombres técnicos y la edición por variante van en "Details".
6. **Grabadora:**
   1. Elegir micrófono y ver un medidor de nivel.
   2. Pulsar Start, luego Stop (no hay que mantener presionado). Se ve la duración contra el límite de 10 s.
   3. Revisar la toma: Retake · Discard · Save.
   4. Antes de guardar se muestran las variantes que reemplaza y si la toma queda solo local o se comparte con el grupo.
   - El recorte de silencio se puede desactivar. Si la toma es silenciosa o está saturada, la app avisa y deja decidir; no la descarta sola.
   - El micrófono se apaga en cuanto se deja de grabar.
7. **Cabecera:** estado de TF2 (Connected / Not running / Not configured) y del grupo (Synced 2 min ago / Host offline – 2 recordings saved here / Solo). También el botón "Apply N changes to TF2".
8. **Restaurar** tiene tres acciones con su alcance escrito: "Play original", "Use original on my PC", "Restore original for the group" (esta última con Undo). El historial se puede escuchar antes de recuperar una versión.
9. **Accesibilidad:** objetivo WCAG 2.2 AA.
   - Todo funciona con teclado, con foco visible y al 200 % de zoom.
   - Los botones tienen texto y no solo símbolos.
   - Contraste de al menos 4.5:1. Los cambios de estado se anuncian con `aria-live`.
   - Los controles frecuentes miden al menos 44×44 px.

## 8. Orden de trabajo

Se construyen primero las bases (módulos con pruebas y una CLI `doctor` para probar en Windows **pronto**), después la colaboración y al final la web. Detalle en `TASKS.md`.

| Ola | Qué | Condición para pasar a la siguiente |
|---|---|---|
| 0 | Esqueleto del repo y convenciones | Corren `python -m unittest` y `python -m tf2reaudio --version` |
| 1 | steam, vpk, rcon, audio, catalog, launchers, tunnel (en paralelo) | Cada módulo con sus pruebas en verde |
| 2 | store, game, CLI `doctor` | **Prueba en Windows real con un amigo** (`doctor` + grabar una toma de prueba por CLI) y medición de `snd_restart` en partida |
| 3 | group, sync (host + cliente), pruebas de integración | Dos colecciones intercambian tomas, sobreviven a una desconexión y a un conflicto, y un borrado viejo no resucita |
| 4 | Servidor local + web (asistente, dashboard, clase, grabadora, grupo) | Prueba con 5 personas nuevas (auditoría §6): al menos 4 de 5 graban MEDIC! sin ayuda |
| 5 | Comodidad: grabación consecutiva, importar un audio, volumen | Solo si los usuarios lo piden |

## 9. Fuera del alcance

Editor multipista, voces con IA, link fijo del host (requiere dominio en Cloudflare), actualización automática y app nativa de escritorio.
