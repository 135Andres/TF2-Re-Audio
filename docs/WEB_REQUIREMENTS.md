# TF2 Re-Audio — Qué debe tener la web

Documento funcional para diseñar la interfaz. Fecha: 15 de octubre de 2026.

Este documento reúne los requisitos vigentes de PLAN.md, TASKS.md y la interfaz local existente. No fija colores, tipografías, composición, estilo de ilustración ni animaciones: esas decisiones quedan abiertas para el diseño. Tampoco autoriza nuevas funciones de backend.

## 1. Qué es y para quién

Una aplicación local para reemplazar voces de Team Fortress 2 con grabaciones propias. Se abre en el navegador desde un programa que corre en la misma PC. El usuario debe poder completar su primera voz sin cuenta, sin grupo y sin conexión a internet.

Recorrido principal: abrir → elegir la instalación de TF2 → elegir clase y línea → escuchar el original → grabar → escuchar la toma → guardar → aplicar o reiniciar TF2 → escuchar dentro del juego → recuperar una versión anterior si lo desea.

Las voces se instalan en cada PC. No se transmiten por el chat de voz de una partida. La web no puede verificar por sí sola que una grabación se haya escuchado dentro del juego.

## 2. Alcance del diseño

| Área | Situación | Qué diseñar |
|---|---|---|
| Uso individual local | Implementado; pendiente de aceptación humana completa | Recorrido completo, incluidos errores, recuperación y ajustes |
| Grupo y sincronización | Futuro; implementación pendiente | Pantallas futuras separadas y claramente identificadas |
| Aplicación automática de cambios | No habilitada | Mantener aplicación manual; no presentar un interruptor operativo |
| Idioma | Interfaz en inglés | Usar los rótulos ingleses de este documento como referencia |
| Distribución | Proyecto privado | No hace falta landing pública, registro, precios ni descarga pública |

Se puede maquetar el futuro de grupos, pero el prototipo debe distinguirlo de lo que funciona hoy. En la aplicación actual, `Join friends` aparece como `Coming soon`.

## 3. Mapa de vistas

La organización visual puede cambiar. Deben existir estos espacios funcionales, como páginas, paneles o diálogos:

1. Primera apertura y selección de TF2.
2. Colección: elección de clase.
3. Clase: catálogo de líneas.
4. Grabadora y revisión de una toma.
5. Historial y recuperación.
6. Configuración, conexión, copias y retirada de voces.
7. Confirmaciones, avisos globales y resultados de operaciones.
8. Grupo y sincronización, en una fase futura.

La configuración y los avisos importantes deben poder encontrarse desde el recorrido principal. Debe haber una forma clara de volver de una clase a todas las clases, y de ajustes a la vista anterior.

## 4. Información compartida entre vistas

- Nombre de la aplicación: `TF2 Re-Audio`; versión visible en algún lugar accesible.
- Estado de TF2, separado del estado de la colección o del grupo.
- Estado actual de grupo: `Solo`.
- Acción `Apply N changes to TF2`, con cantidad de cambios pendientes. Esa cantidad corresponde a archivos pendientes y no debe confundirse con el progreso de comandos grabados.
- Avisos de reinicio necesario, voces deshabilitadas, recuperación de respaldo o problemas de instalación.
- Acceso a `Setup & settings`.
- Respuestas visibles al guardar, importar, restaurar o fallar una acción.

Estados de conexión que el diseño debe contemplar:

| Estado | Rótulo orientativo | Siguiente acción comprensible |
|---|---|---|
| Consultando | `TF2: checking…` | Esperar; no mostrar éxito todavía |
| Conectado | `TF2: connected` | Aplicar cambios si hay pendientes |
| Juego cerrado | `TF2: not running` | Abrir TF2 o cargar las voces al reiniciarlo |
| Sin configurar | `TF2: not configured` | Abrir configuración de conexión |
| Autenticación fallida | `TF2: password rejected` | Revisar opciones de Steam y comprobar conexión |
| Otro error | `TF2: connection error` | Mensaje claro y opción de reintentar |

## 5. Primera apertura y selección de TF2

Objetivo: llegar a la colección sin editar archivos manualmente.

Contenido y acciones:

- Explicación breve: las grabaciones permanecen en esta PC; compartir vendrá después.
- Acción principal `Start solo`.
- Instalación de TF2 detectada, con su ruta y resultado de validación.
- Posibilidad de elegir entre instalaciones detectadas cuando corresponda.
- `Choose another folder`: introducir la ruta de Team Fortress 2 o de su subcarpeta `tf` y validar con `Use this folder`.
- Error y recuperación distintos para instalación no encontrada, carpeta incorrecta, archivo de voces ilegible y carpeta sin permiso de escritura.
- Estado de validación en curso y confirmación cuando la carpeta sea aceptada.
- Si existe el mod experimental `tf2reaudio_test`, aviso y acción explícita para retirarlo con confirmación.

La selección actual de carpeta utiliza un campo de ruta; no hay un explorador nativo del sistema implementado en la web.

La conexión avanzada con TF2 es opcional. No debe convertirse en un requisito para grabar una vez configurada una instalación válida.

## 6. Colección: elección de clase

Mostrar las nueve clases: Scout, Soldier, Pyro, Demoman, Heavy, Engineer, Medic, Sniper y Spy.

Cada clase necesita:

- Nombre e identificación visual que funcionen sin internet; los recursos actuales incluyen emblemas SVG locales.
- Progreso de comandos con grabaciones respecto del total.
- Entrada clara al catálogo de esa clase.
- Si se muestra `Suggested voice`, en modo solo su contenido es `you (solo)`; no implica que esa persona haya grabado todas las tomas.

El progreso cuenta comandos lógicos. Una grabación que reemplaza tres variantes no representa tres comandos terminados. Contemplar colección sin grabaciones, progreso parcial y todas las líneas cubiertas.

## 7. Clase: catálogo de líneas

Cabecera con nombre de clase, progreso y vuelta a `All classes`.

Acciones de avance:

- `Start with MEDIC!` como primera tarea guiada.
- `Continue recording` cuando corresponda.
- `Next line` para avanzar sin volver a la colección.

Navegación del catálogo:

- `Voice menu`.
- `Pain & death`.
- `Domination & revenge`.
- `All lines`, que incluye también líneas fuera de las categorías anteriores.
- Buscador `Find a line` / `Search names or labels`.
- Filtro `Pending only`.
- Mensaje para búsqueda sin resultados y para categoría completada.

Cada línea debe mostrar nombre legible, estado y acciones disponibles. Los identificadores técnicos pueden vivir en detalles. No se debe inventar una transcripción de cada voz si el catálogo no la proporciona.

| Acción | Efecto que debe quedar claro |
|---|---|
| `Play original` | Escucha el audio original; no cambia la selección |
| `Play recording` | Escucha la grabación seleccionada |
| `Record voice` / `Record again` | Abre la grabadora para esa línea |
| `History` | Abre versiones anteriores y sus preescuchas |
| `Undo last change` | Recupera la selección anterior cuando existe |
| `Use original on my PC only` | Usa el original localmente, conservando la selección de la colección |
| `Use collection voice on my PC` | Quita la preferencia local por el original |
| `Restore original for this collection` | Cambia la selección de la colección al original |
| `Details & variants` | Explica y permite editar variantes individuales |

No es obligatorio poner todas las acciones al mismo nivel visual. Sí deben ser encontrables y conservar nombres y alcance comprensibles.

### Variantes

Una línea como MEDIC! puede corresponder a varios archivos del juego. Por defecto una toma puede reemplazarlos todos; una variante individual puede tener su propia toma.

En detalles mostrar variantes, archivos afectados, selección propia o heredada y acciones de grabación, escucha, historial y recuperación. Antes de guardar, indicar `Replaces N game files`. Una variante editada sigue siendo independiente de la selección general; restaurar la línea completa no elimina automáticamente todas las ediciones individuales.

## 8. Grabadora

Debe identificar siempre la clase, la línea o variante que se está grabando, cuántos archivos afectará y que el guardado es local.

| Etapa | Contenido y acciones necesarias |
|---|---|
| Preparada | Selector de micrófono, `Test microphone`, nivel de entrada, `Start recording`, cierre |
| Solicitando permiso | Indicación de espera y posibilidad de salir; no aparentar que ya está grabando |
| Grabando | Micrófono activo, medidor, tiempo transcurrido frente al límite de 10 segundos y `Stop` |
| Procesando | Estado de espera mientras se prepara el audio; evitar envíos repetidos |
| Revisando | Reproductor de la toma, `Retake`, `Discard`, `Save recording` |
| Guardando | Estado en curso y prevención de guardado duplicado |
| Guardado | Confirmación local, actualización de pendientes y regreso con foco útil a la línea |
| Fallo al guardar | Error claro, conservar la preescucha y permitir reintentar |

Requisitos adicionales:

- Iniciar y detener con botones; no exigir mantener pulsado.
- Parada automática al alcanzar 10 segundos.
- Opción `Trim silence around the recording`, desactivable.
- Avisos de silencio y saturación. Permitir guardar la toma de todos modos.
- El micrófono debe dejar de capturar al detener, descartar o cerrar, incluido Escape.
- Distinguir `Microphone off` de `Microphone active` con algo más que color.
- Manejar permiso denegado, dispositivo ausente, dispositivo ocupado, configuración incompatible, espera agotada y formato no decodificable. Cada error necesita una instrucción de recuperación.
- Salir o descartar sin guardar no debe reemplazar la selección anterior.

Una forma de onda no es un requisito actual. Si se utiliza como recurso visual, no implica un editor de audio con funciones nuevas.

## 9. Guardado, instalación y aplicación

El diseño debe distinguir estos resultados:

| Resultado | Qué significa |
|---|---|
| `Saved on this computer` | La toma quedó guardada en la colección local |
| `Pending: apply to TF2` | Queda cargar los cambios en el juego |
| `Apply request sent` | Se solicitó la recarga; el usuario debe escuchar el resultado dentro del juego |
| `Using the original` | La selección correspondiente usa la voz original |
| `Original on this PC only` | Hay una preferencia local por el original |
| Guardado correcto, instalación fallida | La toma sigue guardada; mostrar cómo volver a intentar actualizar TF2 |

Cuando la carpeta del mod acaba de crearse, mostrar `Restart TF2 once`, explicar por qué y permitir confirmar `I restarted TF2`. Descartar ese recordatorio no demuestra conexión ni reproducción correctas.

Con TF2 cerrado o sin RCON configurado, ofrecer `Apply when you restart TF2`. La aplicación manual puede interrumpir brevemente el audio; su comportamiento en Casual sigue pendiente de validación humana. No prometer un resultado instantáneo o sin tirones.

## 10. Historial y conflictos importados

El historial debe mostrar la línea, las tomas disponibles, fecha, autor disponible, cuál está seleccionada y un reproductor por toma. Si el autor solo tiene un identificador local, no inventar un perfil o avatar de cuenta.

Acciones: `Use this recording` y regreso a la línea. Contemplar historial vacío.

Hoy pueden aparecer conflictos al importar colecciones, aunque no exista sincronización entre amigos. En ese caso:

- Aviso `Conflicting recordings`.
- Permitir escuchar ambas alternativas.
- Acción `Use this recording & resolve conflict`.
- Resolver la selección conservando las alternativas en el historial.

## 11. Setup & settings

Agrupar las funciones con nombres comprensibles; la distribución visual queda abierta.

### Instalación y conexión

- Consultar y cambiar la carpeta TF2, con validación.
- Puerto RCON editable entre 1 y 65535.
- `Copy launch options`, con alternativa de selección/copia manual si el portapapeles falla.
- Explicar que se añaden al final de las opciones existentes de Steam, conservando las demás.
- `Check connection`, resultado y recuperación.
- Alternativa de cargar las voces al reiniciar el juego.
- Detección y retirada confirmada del mod experimental.
- Las opciones de conexión contienen una credencial local: no mostrarlas como información pública para compartir.

### Copias de la colección

- `Export collection`: descargar una copia ZIP.
- Elegir un ZIP y `Import collection ZIP`.
- Explicar que importar combina con la colección existente; no la reemplaza sin más.
- Resultados de exportación/importación y errores de archivo inválido o demasiado grande.
- Aviso posterior para revisar selecciones y aplicar o reiniciar.

### Deshabilitar y retirar

| Acción | Alcance y confirmación |
|---|---|
| `Disable voices` | Retira temporalmente el mod del juego, conserva grabaciones y explica el reinicio |
| `Enable voices` | Reactiva las voces guardadas y explica cómo cargarlas |
| `Delete collection` | Borra grabaciones y voces instaladas; confirmación explícita y recomendación de exportar antes |
| `Uninstall` | Retira el mod y guía para quitar el programa y sus opciones de Steam |
| `Also delete my local collection` | Opción explícita al desinstalar; conservar la colección por defecto |

La guía final debe explicar qué debe hacer todavía el usuario fuera de la web: retirar solo las opciones correspondientes de Steam, cerrar el programa y borrar su carpeta si desea hacerlo. No presentar la eliminación de una colección como reversible mediante Undo.

## 12. Estados transversales para el diseño

Preparar ejemplos visuales de:

- Carga inicial y carga de catálogo.
- Colección vacía, con grabaciones y con voces deshabilitadas.
- Búsqueda vacía y categoría completada.
- Operación en curso, éxito, advertencia y error recuperable.
- Servidor local inaccesible: explicar que debe mantener abierta la ventana del lanzador y reintentar.
- TF2 cerrado y conexión rechazada.
- Grabación guardada con instalación fallida.
- Colección recuperada desde respaldo y colección ilegible que necesita atención; no ofrecer borrar datos como solución automática.
- Confirmación y cancelación de acciones destructivas.

Un error debe nombrar el problema y el siguiente paso. Mantener los datos del formulario o la toma cuando puedan recuperarse.

## 13. Accesibilidad y adaptación

- Recorrido esencial completo con teclado y foco claramente visible.
- Al cerrar un diálogo, volver al control de la línea editada o a un destino útil si ya no está visible.
- Si falla Guardar, mantener el diálogo y una acción accesible de reintento.
- Pestañas utilizables con flechas, Home y End; estructura y nombres accesibles.
- Zoom al 200 % sin desplazamiento horizontal en el recorrido esencial.
- Contraste de texto normal de al menos 4.5:1; objetivos de interacción de al menos 44 × 44 como meta del producto.
- Controles con nombre y texto para estados; no depender solo de iconos o color.
- Avisos de cambio y errores anunciables por lector de pantalla, sin convertir cada actualización del medidor en una interrupción.
- Diálogos, listas largas y paneles de configuración utilizables en ventanas pequeñas.
- Si se añade movimiento, debe respetar la preferencia de movimiento reducido y no impedir una acción.

WCAG 2.2 AA es el objetivo. Las pruebas existentes de teclado y zoom son parciales; no equivalen a una certificación.

## 14. Grupo — diseño futuro separado

Reservar una propuesta futura para:

- `Create group`: nombre de grupo y nombre visible de la persona.
- `Join a group`: enlace del anfitrión y código de invitación.
- `Share invite`: compartir enlace y código juntos; mostrar vencimiento o uso previo.
- Miembros, roles y responsable sugerido por clase.
- Acciones de administración: invitar, expulsar y promover; alojar la conexión no convierte a alguien en administrador.
- `Host for the group`: activar alojamiento y mostrar el enlace mientras esté disponible.
- Explicación: `This PC keeps everyone connected while the app is open.`
- `Update link`: cambiar la dirección del anfitrión manteniendo el mismo grupo y colección.
- Estado de sincronización, última sincronización y tomas pendientes de compartir, separados de TF2.
- Anfitrión desconectado, reconexión, invitación inválida/vencida, acceso revocado y `Update required`.
- Conflictos con ambas tomas recuperables.
- Explicación breve de qué datos se compartirán al crear o entrar al grupo.

No hace falta diseñar una cuenta con correo y contraseña: no forma parte del modelo vigente. Estos recorridos requieren backend todavía no implementado y no deben aparecer como operativos en la versión local.

## 15. Qué conviene entregar con la propuesta visual

- [ ] Primera apertura: instalación detectada y error de carpeta.
- [ ] Colección con las nueve clases: vacía y con progreso.
- [ ] Clase con lista de líneas, categorías, búsqueda y filtro.
- [ ] Línea grabada, original, con preferencia local y con variantes desplegadas.
- [ ] Grabadora preparada, grabando, revisando y con error de permiso/guardado.
- [ ] Historial con varias tomas y un conflicto importado.
- [ ] Cabecera con TF2 conectado, cerrado, pendientes y aviso de reinicio.
- [ ] Configuración de conexión, copias y retirada de voces.
- [ ] Confirmación destructiva y su cancelación.
- [ ] Una vista a 200 % de zoom y ejemplos de foco de teclado.
- [ ] Si se trabaja en grupos: propuesta futura aparte.

Los ejemplos pueden usar Soldier → MEDIC! con tres variantes, una toma seleccionada, una anterior y una variante individual editada. Son datos de muestra, no resultados de pruebas reales.

## 16. Referencias y límites de este documento

Fuentes: [plan general](../PLAN.md), [contratos por tarea](../TASKS.md), [auditoría histórica](../AUDITORIA_UX.md), [informe de la interfaz local](local-ui-review.md), [protocolo humano](milestone-wave2.md), [HTML actual](../tf2reaudio/web/index.html) y [textos actuales](../tf2reaudio/web/strings.js).

Los textos ingleses aquí sirven como referencia funcional; su redacción final puede pulirse conservando el significado y el alcance. La implementación mantiene sus textos en strings.js. La estructura visual del HTML actual no obliga al nuevo diseño.

Preparación: se contrastaron las pantallas y acciones con el plan, las tareas y los controles actuales. Solo se crea este documento; no cambia la aplicación, el backend ni la propiedad de archivos de otras tareas. No se ejecutaron pruebas de aplicación por este cambio documental. Windows nativo, micrófono físico, reproducción real en TF2/Casual y accesibilidad completa conservan sus validaciones pendientes. No se requieren cambios de otros módulos para usar este brief.
