# TF2 Re-Audio — Tareas para agentes

Lee `PLAN.md` antes de cualquier tarea. Cada tarea es **dueña** de los archivos que lista y no debe editar los de otra; si necesita un cambio en otro módulo, lo anota en su reporte. Las interfaces de abajo son el contrato entre tareas: se respetan aunque la implementación interna cambie.

## Reglas para todos los agentes

- **Python ≥3.10, solo biblioteca estándar.** Nada de `pip install`.
- Debe funcionar en **Windows y Linux**: usar `pathlib` siempre, nunca asumir `/`, y fijar `newline`/`encoding="utf-8"` explícitos.
- Pruebas con `unittest` en `tests/test_<modulo>.py`. Se corren con `python -m unittest` desde la raíz y no deben tocar el TF2 real ni la red. Para eso se usan fixtures y servidores falsos en `127.0.0.1` con puerto 0.
- Toda escritura de datos persistentes pasa por `util.atomic_write`.
- Texto visible para el usuario: **en inglés**.
- Errores esperables (archivo faltante, red caída, juego cerrado) → excepciones propias del módulo con un mensaje claro. Nunca un traceback al usuario.
- Al terminar, el reporte incluye: qué se hizo, cómo se probó, qué no se probó (sobre todo Windows) y los cambios que necesitas de otras tareas.

## Mapa de dependencias y orden de entrega

```
Ola 0 · completada: T0 → T1–T10
Ola 1 · siguiente: T14 servidor local (solo recorrido local)
                  → T15 shell/dashboard/clase · T16 grabadora · T17 asistente
                  → T19 ZIP candidato para probar el recorrido local
Ola 2:            hito humano Linux + Windows + TF2 real + T19 release candidato
Ola 3:            T11 group(→T8) → T12 sync(→T8,T11,T4,T5) → T13 integración
                  → T7 túnel real desde host → T18 UI de grupo
Ola 4:            prueba con 5 personas, accesibilidad y correcciones
Ola 5:            T19 release final y T20 comodidad opcional
```

### Collaboration follow-up — user authorization, 2026-10-15

The user approved applying the collaboration ideation. Wave 3 development is now authorized ahead of the previous Wave 2 sequencing gate; human Windows and TF2 acceptance remains pending. Implementation was performed inline by task stage (T11, T12, T13, T14 delivery 2, T18 and T15 integration). No T8 implementation files were edited. See `docs/collaboration-report.md` for test evidence, the conservative no-prune shared-history policy, limitations and T8/T10/T19 owner requests.

### Regla de ejecución

**Prioridad del usuario (2026-10-15):** primero completar y comprobar el recorrido funcional local en Linux. Windows aún no se ha probado y su validación se pospone hasta estabilizar Linux; no bloquea mejoras ni pruebas locales. Esto no marca el hito de la Ola 2 como completado ni autoriza iniciar colaboración.

**Current integration — 2026-10-15:** source `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c` plus uncommitted T8/T15 changes passed 198 tests (9 skipped without browser; 2 skipped with all seven Chromium checks). The prior 192-test focus failure is historical. Local Linux implementation is ready for human testing; this is not a clean-commit or Wave 2 acceptance claim. See [report 06](docs/agent-reports/06-integration-status.md). Ownership and the Linux-first gate remain unchanged.

T14–T17 se pueden desarrollar como una rebanada local aunque T11, T12 y T7 no existan. El servidor expone primero solo API local; sus endpoints de grupo se añaden después de T12 bajo el mismo propietario de archivos. T7 no bloquea ningún hito local. T19 se ejecuta dos veces: primero como ZIP candidato y después con la colaboración terminada.

---

## Ola 0

### T0 — Esqueleto del repositorio
**Archivos:** `tf2reaudio/__init__.py`, `tf2reaudio/__main__.py`, `tf2reaudio/util.py`, `tests/test_util.py`, `.gitignore`, `AGENTS.md`
- `git init`. El `.gitignore` excluye `rcon_password.txt`, `__pycache__/`, `dist/` y cualquier carpeta de datos.
- En `__init__.py`: `__version__ = "0.1.0"` y `PROTOCOL_VERSION = 1`.
- En `util.py`:
  - `data_dir() -> Path`: `%APPDATA%\TF2ReAudio` en Windows, `$XDG_DATA_HOME/tf2reaudio` o `~/.local/share/tf2reaudio` en Linux. La crea si no existe.
  - `atomic_write(path, data: bytes)`: escribe a un temporal en el mismo directorio, hace `fsync` y luego `os.replace`.
  - `set_low_priority()`: `os.nice(10)` en Linux; `SetPriorityClass(BELOW_NORMAL)` con `ctypes` en Windows. Si falla, no hace nada.
- En `__main__.py`: un `argparse` con subcomandos vacíos (`run`, `doctor`, `host`) y `--version`.
- En `AGENTS.md`: copia las "Reglas para todos los agentes".
- **Aceptación:** `python -m tf2reaudio --version` imprime la versión y `python -m unittest` pasa (incluida una prueba de que `atomic_write` no deja temporales si falla).

---

## Ola 1 (en paralelo)

### T1 — Encontrar y validar TF2 (`steam.py`)
**Archivos:** `tf2reaudio/steam.py`, `tests/test_steam.py`
```python
def find_installs() -> list[Path]          # carpetas "tf" válidas, sin duplicados
def check_install(tf: Path) -> InstallCheck  # dataclass(ok: bool, problem: str|None, detail: str)
# problem ∈ {"not_found", "wrong_folder", "vpk_unreadable", "not_writable"}
```
- Raíces de Steam en Windows: `HKCU\Software\Valve\Steam\SteamPath` (`winreg`) y `%ProgramFiles(x86)%\Steam`. En Linux: `~/.local/share/Steam`, `~/.steam/steam` y Flatpak (`~/.var/app/com.valvesoftware.Steam/.local/share/Steam`).
- Leer **todas** las bibliotecas de `steamapps/libraryfolders.vdf` (con las barras escapadas `\\`).
- `check_install` acepta tanto la carpeta `tf` como la raíz `Team Fortress 2` (en ese caso la corrige). Verifica que se pueda abrir el VPK de voces y prueba escribir en `tf/custom` con un archivo temporal que luego borra.
- **Aceptación:** pruebas con árboles falsos en `tempfile` para cada `problem`, varias bibliotecas, rutas de Windows dentro del VDF y duplicados por symlink (`~/.steam/steam` → `~/.local/share/Steam`).

### T2 — Lector de VPK robusto (`vpk.py`)
**Archivos:** `tf2reaudio/vpk.py`, `tests/test_vpk.py`, `tests/fixtures/make_vpk.py`
```python
class VpkError(Exception)
class VpkIndex:
    def __init__(self, dir_vpk: Path)      # parsea el índice; lanza VpkError
    def names(self) -> list[str]           # "sound/vo/soldier_medic01.mp3"
    def read(self, name: str) -> bytes     # contenido completo (preload + archivo)
    def __contains__(self, name) -> bool
```
- Soporta las versiones 1 y 2. Corrige los bugs de la auditoría: detectar fin de archivo en cadenas sin terminador y no leer más allá de `tree_size`; un archivo truncado debe lanzar `VpkError`, nunca colgarse.
- `read`: `archive_index == 0x7FFF` significa que los datos están dentro del propio `_dir.vpk`, después del árbol. Si no, están en `<prefix>_<NNN>.vpk`. Hay que concatenar primero los bytes de *preload*. Se valida contra el CRC32 de la entrada.
- `make_vpk.py` genera VPKs sintéticos para las pruebas.
- **Aceptación:** pruebas con VPK v1 y v2, preload, datos en `_dir` y en un archivo externo, truncado en cada sección (debe lanzar `VpkError` en menos de 100 ms) y CRC incorrecto. Prueba manual: leer `sound/vo/soldier_medic01.mp3` real y comprobar que empieza con `ID3`.

### T3 — Cliente RCON robusto (`rcon.py`)
**Archivos:** `tf2reaudio/rcon.py`, `tests/test_rcon.py`
```python
class RconError(Exception); class RconNotRunning(RconError); class RconAuthFailed(RconError)
def send(command: str, password: str, port: int = 27015, timeout: float = 3.0) -> str
def launch_options(password: str, port: int = 27015) -> str
# → "-usercon +ip 127.0.0.1 +hostport 27015 +rcon_password <pw> +net_start"
```
- Conecta solo a `127.0.0.1`. Usa una función `_recv_exact(n)` que tolera fragmentos y lanza `RconError` si la conexión se cierra antes de tiempo. Valida que el tamaño del paquete esté entre 10 y 4096+10. Hay que ignorar el `RESPONSE_VALUE` vacío que el servidor manda antes del `AUTH_RESPONSE`.
- Conexión rechazada o timeout al conectar → `RconNotRunning`. Auth `id == -1` → `RconAuthFailed`.
- **Aceptación:** servidor falso que manda la cabecera de a 1 byte, cierra a mitad del cuerpo, rechaza la contraseña y nunca responde (timeout). Ningún caso puede colgarse más de `timeout`+1 s.

### T4 — Validación y análisis de WAV (`audio.py`)
**Archivos:** `tf2reaudio/audio.py`, `tests/test_audio.py`
```python
MAX_SECONDS = 10; MAX_BYTES = 1_000_000; RATE = 44100
class InvalidWav(Exception)               # .reason legible
@dataclass class WavInfo: duration_s: float; peak: float; rms: float; warnings: list[str]  # "silent", "clipping"
def inspect_wav(data: bytes) -> WavInfo    # valida y analiza
```
- Solo acepta RIFF/WAVE PCM (`fmt` 1), 16 bits, mono, 44100 Hz, `data` no vacío, ≤ `MAX_SECONDS` y ≤ `MAX_BYTES`. Debe recorrer los chunks con cuidado: tolerar `LIST` y otros, el padding impar y rechazar tamaños que mientan sobre el largo real.
- Avisos: `silent` si RMS < −45 dBFS; `clipping` si más del 0.1 % de las muestras están en ±32767.
- **Aceptación:** pruebas con WAV válidos, estéreo, 48 kHz, 8 bits, truncados, con chunk `LIST`, silencio y saturación.

### T5 — Catálogo de líneas (`catalog.py`)
**Archivos:** `tf2reaudio/catalog.py`, `tests/test_catalog.py`, `tests/fixtures/vo_index.txt`
**Depende de:** nada en código. Genera `vo_index.txt` (un nombre por línea) leyendo el VPK real de esta máquina (`~/.local/share/Steam/steamapps/common/Team Fortress 2/tf/tf2_sound_vo_english_dir.vpk`) con un script temporal que **no** se commitea.
```python
CLASSES = ["scout","soldier","pyro","demoman","heavy","engineer","medic","sniper","spy"]
@dataclass class Line: id: str; cls: str; label: str; category: str; files: list[str]
# id: "soldier/medic" (comando con variantes) o "soldier/raw/soldier_jeers03" (archivo suelto)
# category ∈ {"voice_menu", "pain_death", "domination", "other"}
def build(names: list[str]) -> Catalog
class Catalog:
    def lines(self, cls: str, category: str | None = None) -> list[Line]
    def line(self, line_id: str) -> Line              # KeyError si no existe
    def is_vo_path(self, path: str) -> bool            # está en el VPK de voces
```
- Tabla curada para el voice menu (los 24 comandos del PLAN) y para pain & death y domination: patrones regex sobre los nombres reales. Hay que **investigar los nombres reales** en `vo_index.txt` (por ejemplo, el comando "Go" puede ser `_go\d+` y "Spy!" `_cloakedspy\d+`). Solo `sound/vo/<class>_*.mp3`; se ignoran `mvm/`, `taunts/`, etc. en las categorías prioritarias, pero aparecen en "other".
- **Referencia externa:** [robbilookatme/tf2-voice-pack-reference](https://github.com/robbilookatme/tf2-voice-pack-reference) tiene CSV y JSON con cada archivo de voz por clase, su transcripción y el "criteria" que lo dispara (p. ej. "did use Help voice command"). **No tiene licencia declarada:** úsalo solo para verificar a mano tus patrones; no copies sus datos al repo. La fuente de verdad en el juego son `scripts/talker/<class>.txt` (dentro de `tf2_misc_dir.vpk`). Las transcripciones no están en los archivos locales del juego (`closecaption_english.txt` solo trae los comentarios de los desarrolladores), así que las etiquetas son curadas a mano.
- Cada archivo de clase pertenece a **una sola** línea: los prioritarios a su comando y el resto a una línea `raw`.
- **Aceptación:** con el fixture real, cada comando del voice menu tiene al menos 1 archivo en cada clase (documenta las excepciones reales; por ejemplo, el Pyro tiene menos variantes). No hay archivos repetidos entre líneas. Hay una prueba que imprime el conteo por clase y categoría.

### T6 — Lanzadores (`TF2ReAudio.cmd`, `tf2reaudio.sh`)
**Archivos:** `TF2ReAudio.cmd`, `tf2reaudio.sh`, `docs/launchers.md`
- Funcionan con **doble clic o desde la consola**. Ejecutan `python -m tf2reaudio run` desde la carpeta donde están.
- **Windows:** busca `py -3` o `python` ≥3.10 (cuidado con el alias falso de la Microsoft Store, que abre la tienda: hay que comprobar la versión). Si no hay, descarga `python-3.12.x-embed-amd64.zip` de python.org, **verifica el SHA-256 fijado** en el script, lo descomprime en `runtime\` junto al lanzador y lo usa. Sin admin, sin winget. Si algo falla, el mensaje dice qué hacer y la ventana espera una tecla antes de cerrarse.
- **Linux:** usa `python3` ≥3.10. Si no hay, imprime el comando para instalarlo según la distro detectada en `/etc/os-release` (pacman/apt/dnf).
- **Aceptación:** probado en Linux. En Windows, se documenta en `docs/launchers.md` la prueba manual que hará el amigo en el hito de la Ola 2. Python embeddable no trae `tkinter` ni `pip`; confirmar que no hacen falta.

### T7 — Túnel (`tunnel.py`)
**Archivos:** `tf2reaudio/tunnel.py`, `tests/test_tunnel.py`
```python
class TunnelError(Exception)
class Tunnel:
    def __init__(self, local_port: int)
    def start(self, timeout: float = 30) -> str   # devuelve "https://xxxx.trycloudflare.com"
    def stop(self)
    @property running: bool
def ensure_cloudflared() -> Path                  # descarga una vez a data_dir()/bin, con SHA-256 verificado
```
- Elige el binario según SO y arquitectura (windows-amd64.exe, linux-amd64, linux-arm64), con versión fija y hash fijado en el código. Lanza `cloudflared tunnel --url http://127.0.0.1:<port> --no-autoupdate` y lee el link de su salida con una regex. El proceso muere junto con la app; en Windows con `CREATE_NO_WINDOW`.
- **Aceptación:** la regex se prueba con salidas reales grabadas (fixtures). La descarga y el arranque se prueban a mano en Linux (prueba marcada con `skipUnless(os.environ.get("NET_TESTS"))`).

**Orden revisado:** aunque T7 ya está implementada y probada de forma aislada, no bloquea la Ola 1 ni la Ola 2. Solo se integra en el flujo `host` después de que T12 pase sus pruebas locales.

---

## Ola 2

### T8 — Colección local (`store.py`)
**Archivos:** `tf2reaudio/store.py`, `tests/test_store.py`
**Depende de:** T0 (`util`), T4 (`inspect_wav`). Recibe el `Catalog` (T5) por parámetro.
Implementa el **modelo de datos de PLAN §4** al pie de la letra.
```python
ORIGINAL = "ORIGINAL"
class Store:
    def __init__(self, root: Path, device_id: str)        # root = data_dir()/collection
    def add_take(self, line_id, wav: bytes, author_member_id) -> str      # take_id; valida con inspect_wav
    def set_active(self, line_id, take_id_or_ORIGINAL) -> str             # event_id
    def undo(self, line_id) -> str | None                                 # reactiva la toma anterior (es un evento nuevo)
    def active(self, line_id) -> str | None                               # take_id, ORIGINAL o None si nunca se tocó
    def history(self, line_id) -> list[dict]                              # tomas con autor y fecha, más cuál está activa
    def conflicts(self) -> list[str]                                      # line_ids
    def resolve(self, line_id, take_id_or_ORIGINAL) -> str
    def set_local_override(self, line_id, use_original: bool)             # no se sincroniza
    def state(self, line_id) -> set[str]                                  # {"pending_share", "pending_apply", ...}
    def snapshot(self) -> dict ; def merge(self, snapshot: dict) -> list[str]   # devuelve las líneas cambiadas
    def blob(self, sha) -> bytes ; def missing_blobs(self) -> list[str] ; def put_blob(self, data) -> str
    def mark_shared(self, ids) ; def mark_applied(self)
    def export_zip(self, path) ; def import_zip(self, path)               # importar = merge
```
- Un `threading.Lock` por instancia. Cada cambio escribe `collection.json` con `atomic_write`, y antes rota `collection.json.bak`. Si al arrancar `collection.json` está corrupto, se carga el `.bak` y se avisa.
- Reloj Lamport: `max(local, visto) + 1`. Ganador: mayor `(lamport, device_id)`. Conflicto: dos eventos de una línea con el mismo `parent_event_id`, sin un `resolve` posterior.
- Poda: más de 5 tomas inactivas por línea → se borran las más viejas, **excepto** las de líneas en conflicto.
- **Aceptación:** pruebas de undo y redo; merge conmutativo e idempotente (A∪B == B∪A, merge dos veces == una vez); conflicto concurrente que conserva ambas tomas; un borrado viejo no resucita; recuperación desde `.bak`; ningún archivo temporal tras simular un fallo a mitad de escritura.

**Refuerzos T8 integrados (2026-10-15, OpenCode/Opus hasta `0c65512`):** formato interno versión 1 compatible con colecciones anteriores; versiones futuras rechazadas antes de recuperar desde respaldo; corrupción doble conserva datos y muestra un error. Importación ZIP limitada a 10.000 entradas y 128 MiB descomprimidos, con rechazo de duplicados y rutas inesperadas. GC conserva la unión de audios referenciados por colección y respaldo, omite limpieza si el respaldo es ilegible/incompatible y respeta archivos ajenos, directorios y enlaces. Las pruebas restauran la retención exacta y detectan la eliminación de cada límite ZIP. Validación del coordinador: suite completa con Chromium, 191 pruebas, OK, 2 omitidas; comprobación adicional de archivos/enlaces/directorios en Linux. Sin validación nativa de Windows ni de audio dentro del juego.

**T8 follow-up verified (2026-10-15):** [report 02](docs/agent-reports/02-storage-recovery.md) covers five added tests with nine injected failure subcases. Failed backup/primary/local-state/blob replacement preserves committed state and backup-referenced audio; persistence errors surface as StoreError. Integrated suite passes. Physical power loss, real disk exhaustion and native Windows locking remain untested; no cross-module implementation fix is currently requested.

### T9 — Puente con el juego (`game.py`)
**Archivos:** `tf2reaudio/game.py`, `tests/test_game.py`
**Depende de:** T1, T2, T3, T5, T8.
```python
MOD_DIR = "tf2reaudio"     # tf/custom/tf2reaudio/sound/vo/...
class Game:
    def __init__(self, tf_dir: Path, store, catalog, settings)   # settings: rcon password/puerto
    def sync_files(self) -> int        # escribe/borra en tf/custom solo lo que cambió; devuelve el número de archivos
    def pending_apply(self) -> int
    def apply(self) -> str             # snd_restart; "sent" | "not_running" | "auth_failed"
    def status(self) -> str            # "connected" | "not_running" | "not_configured" | "auth_failed"
    def mod_folder_is_new(self) -> bool    # la carpeta se creó con TF2 abierto → "Restart TF2 once"
    def test_mod_present(self) -> bool ; def remove_test_mod(self)
    def disable(self) ; def enable(self) ; def uninstall(self, delete_collection: bool)
```
- Para cada línea activa (respetando el override local) escribe la toma en **cada** archivo de `line.files`, con la misma ruta pero bajo `tf/custom/tf2reaudio/`. Antes de escribir, verifica `catalog.is_vo_path`. Las líneas que vuelven a ORIGINAL se borran. Escribe con `atomic_write` y no toca archivos idénticos (se compara el hash).
- `disable` mueve la carpeta a `data_dir()/disabled_mod` (no la borra).
- La contraseña RCON se genera la primera vez y se guarda en `data_dir()/settings.json`.
- **Aceptación:** pruebas con una carpeta `tf` falsa y un RCON falso (reusar el de T3). Un archivo fuera de `sound/vo` jamás se escribe, ni con datos maliciosos en el store.

### T10 — CLI `doctor` y grabación de prueba
**Archivos:** `tf2reaudio/__main__.py` (subcomandos `doctor`, `apply`, `import-wav`), `tests/test_cli.py`
**Depende de:** T1, T2, T3, T9.
- `doctor`: imprime la versión de Python y de la app, el SO, las instalaciones de TF2 con su `check_install`, si el VPK se puede leer, el estado de RCON, si existe la carpeta del mod o la de prueba, y la ruta de datos. **Nunca** imprime contraseñas ni tokens. Con `--copy` deja el reporte en un archivo de texto.
- `import-wav <line_id> <archivo.wav>`: agrega la toma, la activa y llama `sync_files`. Con eso se hace la prueba del hito sin web.
- `apply`: llama `game.apply()` y muestra el resultado en texto claro.
- **Aceptación:** probado en Linux contra el TF2 real.

### ★ Hito de la Ola 2: prueba en Windows (la hacen humanos; el agente prepara la guía)
- Un amigo con Windows descomprime el ZIP, abre `TF2ReAudio.cmd`, corre `doctor`, importa un WAV en `soldier/medic`, abre TF2 y presiona E.
- Tú, en partida Casual: `import-wav` + `apply` **mientras juegas**. Anotar si hay tirón, cuánto dura y si se oye la voz nueva. Con eso se decide si el modo automático se ofrece.
- Comprobar también que `rcon.send()` contra el TF2 real **no** termina en timeout. El cliente detecta el final de la respuesta mandando un paquete vacío y esperando su eco, como hacen los servidores dedicados; si el cliente de TF2 no devuelve ese eco, hay que volver a leer solo el primer paquete de respuesta.
- **No se pasa a la Ola 3 hasta que esto funcione en Windows.**

---

## Ola 3

### T11 — Grupo, miembros e invitaciones (`group.py`)
**Archivos:** `tf2reaudio/group.py`, `tests/test_group.py`
**Depende de:** T8 (usa el mismo patrón de eventos con Lamport y la persistencia atómica).
```python
class Group:   # se guarda en data_dir()/group.json; la parte replicable va en el snapshot del store
    @staticmethod
    def create(name, my_display_name) -> "Group"         # yo = admin; genera group_id
    def create_invite(self, ttl_hours=24) -> str           # código legible tipo "TF2-ABCD-EFGH"; solo admin
    def redeem_invite(self, code, display_name) -> (member_id, device_token)   # lo ejecuta el host
    def verify_token(self, token) -> member_id | None      # compara sha256(token) con hmac.compare_digest
    def remove_member(self, member_id) ; def promote(self, member_id)          # solo admin, como eventos
    def set_suggested_voice(self, cls, member_id)          # el "cast menu", como evento
    def members(self) -> list[dict] ; def is_admin(self, member_id) -> bool
    def known_hosts(self) -> list[str] ; def set_host_url(self, url)            # "Update link"
```
- Las invitaciones se replican hasheadas; una invitación canjeada es un evento, así que no se puede usar dos veces aunque se canjee en hosts distintos después de sincronizar. **Riesgo aceptado y documentado:** si dos hosts sin sincronizar canjean la misma invitación al mismo tiempo, se aceptan ambos miembros.
- **Aceptación:** pruebas de crear grupo, invitar, canjear, invitación vencida o reusada, expulsión replicada (después del merge, el token deja de funcionar), y que un no admin no puede invitar ni expulsar.

### T12 — Sincronización: servidor del host y cliente (`sync.py`)
**Archivos:** `tf2reaudio/sync.py`, `tests/test_sync.py`
**Depende de:** T4, T5, T8, T11. Usa T7 solo desde `run`/`host`, no en las pruebas.
- **Servidor** (`http.server.ThreadingHTTPServer` en `127.0.0.1:<puerto>`; el túnel apunta ahí):
  - `GET /api/hello` → `{group_id, protocol_version, app_version}` (sin auth).
  - `POST /api/redeem` `{code, display_name}` → `{member_id, token, group snapshot}`. Limitado a 5 intentos por minuto por IP; detrás de Cloudflare se usa el header `CF-Connecting-IP`.
  - `GET /api/snapshot` (Bearer token, con ETag/`If-None-Match` → 304).
  - `POST /api/snapshot` → merge del snapshot del cliente. Solo se aceptan tomas y eventos cuyo autor sea el miembro del token.
  - `GET /api/blob/<sha>` y `PUT /api/blob/<sha>`: validar el hash con el contenido, `inspect_wav` y `MAX_BYTES`. Es idempotente.
  - `GET /download/TF2ReAudio.zip` (sin auth; sirve el ZIP de T19 si existe).
  - Un `protocol_version` distinto → `426` con un mensaje "Update the app".
- **Cliente:** `sync_once(store, group, url, token) -> SyncResult(pushed, pulled, conflicts, error)`. Hace un pull del snapshot, `merge`, baja los blobs que faltan (validando cada uno), sube los propios que falten y hace push del snapshot. `Syncer` es un hilo que corre cada 15 s con backoff exponencial (hasta 2 min) si el host está caído; expone `last_sync`, `status` ("synced" / "host_offline" / "auth_failed" / "update_required") y `pending_share`.
- Rechaza cualquier línea o ruta que no exista en el catálogo, **también al recibir**.
- **Aceptación:** pruebas con el servidor en `127.0.0.1` con puerto 0: token inválido → 401; blob con hash falso o WAV inválido → 400; ruta inventada → rechazada; 304 si no hubo cambios; versión incompatible → 426.

### T13 — Pruebas de integración de sincronización
**Archivos:** `tests/test_integration_sync.py`
**Depende de:** T12. Simula 3 dispositivos (A host, B y C) en procesos o threads con carpetas temporales:
1. B graba sin conexión, el host vuelve y B sincroniza: la toma llega a A y a C.
2. B y C graban la misma línea sin conexión: después de sincronizar, ambas tomas existen en los 3, la línea está en conflicto y el ganador es el mismo en los 3.
3. A restaura el original para el grupo y C, desactualizado, sincroniza su toma vieja: el original **no** se revierte.
4. Cambio de host: C se vuelve host con un link nuevo, A y B hacen "Update link" y el `group_id` y la colección se conservan.
5. Expulsión: A expulsa a C, C intenta sincronizar con A → 401; B sincroniza con A y luego C intenta con B → 401.
6. Descarga interrumpida (se corta la conexión a mitad de un blob): el siguiente `sync_once` termina bien.

---

## Ola 1 (primer uso local; web)

### T14 — Servidor local y API (`server.py`)
**Archivos:** `tf2reaudio/server.py`, `tf2reaudio/__main__.py` (subcomandos `run`, `host`), `tests/test_server.py`, `tests/test_cli.py` (solo las pruebas de `run`/`host`, relevo de T10)
**Depende en la primera entrega:** T1, T2, T3, T4, T5, T8, T9 y T10. Los endpoints de grupo dependen además de T11/T12 y se incorporan en una segunda entrega de esta misma tarea.
- `ThreadingHTTPServer` en `127.0.0.1:8440` (si está ocupado, prueba el siguiente puerto). Guarda el puerto en `data_dir()/instance.json`. **Instancia única:** si ya hay una corriendo (responde `/api/ping`), solo abre el navegador y termina.
- Rechaza cualquier petición cuyo `Host` no sea `127.0.0.1:<port>` o `localhost:<port>`. Los `POST` exigen `Content-Type: application/json` o el WAV, más un header `X-TF2RA: 1` (contra CSRF).
- API JSON local de la primera entrega: estado general (TF2, grupo, pendientes), clases y líneas con su estado, `GET /api/original/<line>` (MP3 leído del VPK), `GET /api/take/<id>`, `POST /api/take` (WAV), set-active, undo, resolve, override local, apply, settings (ruta de TF2, puerto RCON), launch options, `check-connection` y export/import/disable/uninstall. Los endpoints de grupo (crear, invitar, unirse, update link, miembros y cast) se incorporan después de T12.
- `run`: llama `set_low_priority()`, abre el navegador con `webbrowser` y arranca el servidor local; el `Syncer` se añade cuando exista un grupo. `host` puede arrancar primero como entrada local y solo añade el servidor de sincronización de T12 y el túnel de T7 después de completar la Ola 3.
- Sirve `tf2reaudio/web/` como estático, con las imágenes de las clases incluidas en el paquete (sin depender de la wiki).
- **Aceptación:** pruebas de la API con `urllib` (no hace falta navegador), de la instancia única y del rechazo de `Host` ajeno.

**Entrega 1, obligatoria antes de colaborar:** `/api/ping`, estado de instalación/TF2, catálogo, original, toma WAV, historial, set-active, undo, override local, apply, ajustes, export/import, disable y uninstall. `run` debe abrir el navegador; `host` puede mostrar temporalmente un mensaje claro de que la colaboración aún no está habilitada.

**Entrega 2, después de T12:** endpoints de grupo y sincronización de la UI. No se debe introducir una dependencia artificial de red en el primer uso local.

**Avance T14 (2026-10-15):** integradas las cabeceras CSP y Referrer-Policy de OpenCode/Opus (`55fb725`), conservando no-store, nosniff y DENY. `media-src 'self' blob:` permite preescuchar tomas locales. Pruebas de servidor cubren respuestas normales y errores JSON; una prueba de navegador verifica bloqueo real de scripts inline y reproducción blob. Suite completa con Chromium: 179 pruebas, OK, 2 omitidas. Seguimiento de OpenCode/Opus (`d209314`) integrado: `end_headers()` cubre también errores 501/431 del framework sin duplicar cabeceras y preserva HEAD sin cuerpo; la prueba del coordinador exige estado y cuerpo exactos. Esto no acredita Windows ni funcionamiento de RCON/audio dentro del juego.

### T15 — Web: shell, dashboard y página de clase
**Archivos:** `tf2reaudio/web/index.html`, `web/app.js`, `web/style.css`, `web/strings.js`, `web/img/`, `tests/test_web.py` (aceptación integrada de la web; micrófono y TF2 falsos)
- HTML, CSS y JS sin frameworks ni build, todo local (sin CDNs). Todos los textos van en `strings.js`.
- Cabecera con los estados de TF2 y del grupo, más "Apply N changes to TF2" (PLAN §7.7).
- Dashboard: 9 tarjetas con imagen, nombre debajo, "Suggested voice" y progreso por comandos lógicos.
- Página de clase: "Start with MEDIC!" / "Continue recording", las pestañas, el buscador, "Pending only", "Next line" y "Details" con las variantes. Las acciones de restaurar van con su alcance escrito (PLAN §7.8), más el historial y los conflictos.
- **Aceptación:** WCAG 2.2 AA (PLAN §7.9), revisada con `playwright-cli` a 200 % de zoom y navegando solo con teclado.

**T15 follow-up verified (2026-10-15):** [report 01](docs/agent-reports/01-keyboard-focus.md) fixes focus lost when saving rerenders the line list. Current Chromium checks cover variant/whole-line save, Escape, Discard, failed save/retry and subsequent Tab. All seven browser checks ran in the coordinator's 198-test suite, OK, 2 skipped. Full WCAG, physical inputs and native Windows remain pending.

### T16 — Web: grabadora
**Archivos:** `tf2reaudio/web/recorder.js`, `web/wav.js`
- El flujo de PLAN §7.6, completo. Selector de micrófono con `enumerateDevices` y medidor de nivel con `AnalyserNode`. Usa `MediaRecorder` → `decodeAudioData` → `OfflineAudioContext` a 44100 Hz mono → WAV PCM16 en `wav.js`. Recorte de silencio con un umbral y opción para desactivarlo. Corta solo a los 10 s.
- Cada error de `getUserMedia` tiene su mensaje y su solución: `NotAllowedError` (permiso bloqueado, con cómo desbloquearlo), `NotFoundError` (no hay micrófono), `NotReadableError` (otra app lo usa) y `OverconstrainedError`. Nunca se queda esperando para siempre.
- El micrófono se detiene (`track.stop()`) en cuanto se termina de grabar.
- **Aceptación:** `wav.js` produce un WAV que `audio.inspect_wav` acepta (prueba con Playwright → POST → 200). Los avisos de silencio y saturación se muestran pero no bloquean el guardado.

### T17 — Web: asistente de primer uso y ajustes
**Archivos:** `tf2reaudio/web/setup.js`
- PLAN §7.1–7.3: "Start solo" / "Join friends", TF2 detectado más "Choose another folder" (campo de ruta validado por la API, porque el navegador no puede abrir un selector de carpetas del sistema), los tres errores distinguidos, retirar `tf2reaudio_test`, "Restart TF2 once", "Copy launch options" con su aviso y "Check connection".
- Ajustes: carpeta de TF2, modo de aplicar (manual/auto, si el hito de la Ola 2 lo permite), export/import y desinstalación en tres niveles.

**Estado revisado (2026-10-13):** T14–T17 tienen implementación del recorrido local y de recuperación: restore, undo, historial/escucha, overrides, detalles/variantes, resolución de conflictos importados, export/import, RCON port, test mod, recordatorios de reinicio y desinstalación guiada. Se corrigieron el micrófono al cerrar con Escape, el temporizador de 10 s, framing y reutilización de puerto en Windows. La suite con Chromium activado pasa 173 pruebas (2 omitidas), incluidas cinco pruebas de navegador con fixtures. T19 prepara el ZIP candidato. **Aceptación aún pendiente:** Windows nativo, micrófonos físicos, TF2 real/RCON/Casual, todos los recorridos por teclado, lectores de pantalla y WCAG completa. No se marcan esos hitos como entregados. Informe: `docs/local-ui-review.md`.

## Ola 3 (colaboración)

### T18 — Web: grupo
**Archivos:** `tf2reaudio/web/group.js`
- "Create group", "Join a group" (pegar link + código), "Share invite" (copia el link y el código juntos), "Update link", miembros y roles (solo los admins ven expulsar y promover), el "cast menu" (Suggested voice por clase) y "Host for the group" (on/off, muestra el link). El host se explica en una línea: "This PC keeps everyone connected while the app is open."
- Mensajes de estado del PLAN: "Host offline – N recordings saved here", "Update required" y la invitación vencida.

### ★ Hito de la Ola 4: prueba con usuarios y accesibilidad
Las tareas de AUDITORIA_UX.md §6 con 5 personas que no conocen el proyecto (Windows y Linux). Se corrigen los bloqueos antes de seguir.

---

## Ola 5

### T19 — Empaquetado y release
**Archivos:** `tools/build_zip.py`, `tests/test_build_zip.py`, `docs/README.md` (en inglés, para usuarios), `docs/local-ui-review.md` (informe de entrega y límites de validación)
- **Decisión del usuario (2026-10-15): mantener el proyecto privado por ahora.** Se permiten builds locales para revisión; no publicar repositorio, ZIP ni releases y no elegir licencia. La publicación queda aplazada hasta una instrucción futura del usuario.
- Arma `dist/TF2ReAudio-<version>.zip` con `tf2reaudio/`, los lanzadores y el README, **sin** datos, `rcon_password.txt` ni `__pycache__`. Imprime el SHA-256 del ZIP.
- README: instalar, actualizar (reemplazar la carpeta; los datos viven aparte), desinstalar y qué hacer si algo falla (correr `doctor`).

**Entrega revisada:** implementada la generación reproducible y atómica del ZIP candidato, con exclusión de datos/secretos/cachés y pruebas de integridad. Se ejecuta ahora para validar el recorrido local en Linux y preparar las pruebas posteriores de Windows. Se repetirá para el candidato final privado después de T18 y de la aceptación humana. El candidato actual no demuestra compatibilidad nativa con Windows ni el funcionamiento de los reemplazos dentro de TF2 real.

**T19 current handoff (2026-10-15):** [report 05](docs/agent-reports/05-private-candidate.md) identifies the reproducible private candidate with SHA-256 `60c105c1631860e1e516bd524282fd552c9f3a7ffac22b6a6c0fdd954d01ff33`. Coordinator independently checked archive integrity and implementation bytes, and reran the two packaging tests successfully. The frozen archive predates coordinator changes to `docs/milestone-wave2.md`; current guidance supplements that build. T19 should rebuild with a new checksum after incorporating documentation requests from report 06. No publication or human acceptance is implied.

### T20 — Comodidad posterior (opcional)
**Archivos:** los que se definan en una tarea específica después de la prueba con usuarios.
- Solo se crea si la Ola 4 identifica una fricción concreta: grabación consecutiva, filtros, importar audio o controles de volumen/recorte.
- No se inicia por anticipado ni se usa para bloquear el release local.
