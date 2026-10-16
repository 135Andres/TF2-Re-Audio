# Auditoría de facilidad de uso — TF2 Re-Audio

Fecha: 11 de octubre de 2026. Alcance: `PLAN.md` y los archivos disponibles en esta carpeta.

**Dictamen:** la idea de conservar las voces localmente y permitir grabar sin conexión es una buena base. Sin embargo, el plan actual describe una herramienta para amigos con ayuda técnica. Para que una persona nueva pueda usarla sola, cambiaría primero la instalación, la primera grabación y la recuperación de errores. Agregar cuentas y sincronización antes de resolver esos recorridos aumentaría la dificultad de uso.

> **Seguimiento 2026-10-12:** esta auditoría describe el estado inicial y conserva sus observaciones históricas. Desde entonces se implementaron T0–T10 (base Python, pruebas, almacenamiento local, puente con TF2, lanzadores y CLI); la suite actual pasa 144 pruebas en Linux. La aplicación web, `run`/`host`, grupos y sincronización siguen pendientes. El plan revisado (`PLAN.md` v3) adelanta el primer uso local y la prueba de Windows antes de la colaboración.

> **Current follow-up — 2026-10-15:** the observations below and the 2026-10-12 note are historical. The local web app, setup, recorder, recovery/history, manual apply and private packaging now exist. Coordinator verification: 198 tests, OK, 9 skipped without browser; 198 tests, OK, 2 skipped with seven Chromium checks. The variant-save focus regression is fixed in the uncommitted T15 snapshot; T8 simulated persistence failures preserve committed state and return module errors. Reports [01](docs/agent-reports/01-keyboard-focus.md), [02](docs/agent-reports/02-storage-recovery.md), [05](docs/agent-reports/05-private-candidate.md) and [06](docs/agent-reports/06-integration-status.md) identify the evidence. These checks establish limited keyboard/200% zoom coverage, not full accessibility acceptance.
>
> **Recommendation disposition:** adopted and implemented: Linux-first solo workflow, guided recording, separate save/apply states, explicit restore scope, history/Undo and local backups. Pending human acceptance: physical microphone, real TF2/RCON and Casual, native Windows, full keyboard/zoom/screen-reader coverage and the five-person study. Deferred until the human gate: collaboration, invitations and reconnect/conflict UX. Optional convenience, persistent logs and expanded diagnostics need separately scoped work. English-only UI, private distribution and deferred license/publication are current decisions. No new user or visual study was performed by coordination.

Esta es una auditoría del diseño y del prototipo, no una evaluación visual de una interfaz terminada. Las recomendaciones son propuestas; no se han implementado.

## 1. Qué existe y qué se pudo comprobar

| Elemento | Estado observado | Qué permite concluir |
|---|---|---|
| `PLAN.md` | Describe arquitectura, pantallas y cuatro fases. | Hay una dirección de producto, pero faltan recorridos completos y criterios de aceptación. |
| `phase0_test.py` | Prototipo de 157 líneas para instalar pitidos, reproducir una línea, recargar audio y retirar la prueba. | Comprueba piezas técnicas; todavía no ofrece grabación ni interfaz web. |
| `rcon_password.txt` | Existe un archivo local de credencial. No fue necesario leer su contenido. | Conviene excluir credenciales y datos personales de cualquier distribución. |
| Aplicación final | No existe `tf2reaudio.py` en esta carpeta. Tampoco hay frontend, sincronización, cuentas o instalador implementados. | Las pantallas del plan aún no se pueden auditar en navegador. |
| Documentación y pruebas | No hay README ni suite de pruebas en los archivos encontrados. La carpeta no es un repositorio Git. | Faltan instrucciones independientes del plan y una forma repetible de validar entregas. |

Comprobaciones realizadas sin instalar sonidos, modificar Steam ni enviar comandos al juego:

- Sintaxis de `phase0_test.py`: válida.
- Detección de TF2 en esta máquina Linux: correcta.
- Lectura del índice VPK local: **12 728 entradas** y **24 archivos de llamadas MEDIC** entre las nueve clases. Son variantes de esa llamada, no 24 comandos diferentes.
- Respuesta RCON simulada con una cabecera recibida parcialmente: provoca `unpack requires a buffer of 4 bytes`.
- VPK sintético truncado dentro de una cadena: el parser no termina; el proceso aislado se detuvo al superar un segundo. El bucle no contempla el fin de archivo.

No se comprobaron reproducción real, Casual, latencia en partida, Windows, permisos de micrófono ni accesibilidad de una interfaz. Los resultados de audio de la fase 0 son los que declara el plan, no verificaciones nuevas de esta auditoría.

## 2. Prioridades de producto

**P0:** necesario para que una persona nueva complete el recorrido principal. **P1:** necesario antes de ampliar la prueba con amigos. **P2:** mejora posterior. Las prioridades de colaboración aplican antes de habilitar esa función; no deben retrasar una primera versión local útil.

| Prioridad | Cambio | Motivo | Criterio de aceptación propuesto |
|---|---|---|---|
| P0 | Abrir con doble clic, sin instalar Python manualmente. | La terminal es la primera barrera del plan. | Una persona con Windows limpio abre la aplicación siguiendo instrucciones gráficas. |
| P0 | Asistente local con detección y selección manual de TF2. | Un fallo de detección no debe ser un callejón sin salida. | Se puede corregir la carpeta y continuar sin editar archivos. |
| P0 | Probar micrófono, grabar, escuchar y guardar antes de compartir. | Evita distribuir tomas accidentales o silenciosas. | La primera voz se completa sin cuenta y sin conexión. |
| P0 | Mostrar por separado guardado, sincronización y aplicación al juego. | Un único mensaje «listo» no explica qué ocurrió. | El usuario identifica si falta compartir o recargar el audio. |
| P0 | Deshacer y aclarar el alcance de restaurar. | Una acción ambigua puede afectar las voces del grupo. | Se recupera una toma sustituida sin buscar archivos. |
| P1 | Unirse y cambiar anfitrión desde la interfaz. | Los enlaces temporales se convierten en trabajo recurrente. | Un enlace nuevo reconecta la misma colección sin perder pendientes. |
| P1 | Conservar alternativas cuando dos personas cambian una línea. | «Gana el último» puede descartar trabajo sin explicarlo. | Ambas tomas se pueden escuchar y recuperar después de sincronizar. |
| P1 | Español/inglés y accesibilidad desde las primeras pantallas. | El idioma y los controles solo con símbolos limitan el acceso. | El recorrido principal funciona con teclado y etiquetas comprensibles. |
| P1 | Diagnóstico guiado y prueba temprana en Windows. | Los problemas de entorno deben resolverse antes de construir la colaboración completa. | La persona puede resolver un micrófono bloqueado y una ruta incorrecta siguiendo la interfaz. |
| P2 | Grabación en serie, filtros y mejoras de audio sencillas. | Reducen el esfuerzo de completar muchas voces. | Se avanza a la siguiente línea pendiente sin navegar repetidamente. |

## 3. Cambios que haría en la experiencia

### 3.1. La instalación debe formar parte del producto

**Evidencia:** `PLAN.md:33–54` requiere PowerShell o terminal, instalar Python, descargar un script, ejecutar argumentos y copiar opciones a Steam. `PLAN.md:156` descarta el ejecutable con la afirmación «Python + un script es suficiente».

Reabriría esa decisión. Mantener el servidor Python y la interfaz en navegador es compatible con entregar un paquete que incluya lo necesario y se abra con doble clic. No hace falta construir una interfaz nativa completa.

El primer inicio debería ofrecer «Empezar solo» y «Unirme a amigos», abrir el navegador automáticamente y conservar los ajustes. También debe explicar si cerrar la pestaña mantiene el programa activo y ofrecer una salida clara. Una segunda apertura debería llevar a la instancia existente.

La descarga de la aplicación debería estar disponible en un lugar estable, independiente del anfitrión del día. Los datos deben sobrevivir a una actualización o al cambio de carpeta del ejecutable. Incluiría versión visible e instrucciones de actualización manual antes de pensar en actualizaciones automáticas.

**Prueba:** una persona que nunca ha utilizado Python puede abrir, cerrar y volver a abrir la aplicación sin ayuda verbal.

### 3.2. El asistente debe resolver errores, además de detectar rutas

**Evidencia:** `PLAN.md:45–50` describe solo el caso exitoso. En `phase0_test.py:21–38`, la búsqueda termina si no encuentra el VPK inglés en las rutas esperadas. En Windows parte de una ubicación de Steam; no ofrece selección manual.

Mostraría la instalación detectada y un botón «Elegir otra carpeta». El asistente debe verificar lectura del VPK y capacidad de escritura en el destino, y distinguir instalación ausente, ruta incorrecta y falta de permisos. Si hay varias instalaciones, debe permitir elegir.

Configurar la comunicación con TF2 puede ser un paso posterior a probar la grabadora. Para Steam: instrucciones visuales breves, botón «Copiar opciones», aviso de conservar opciones existentes y botón «Comprobar conexión». Nunca presentar una conexión fallida como pérdida de la grabación.

Ofrecería «Continuar y aplicar al reiniciar TF2» cuando la recarga en caliente no esté configurada. Detectaría también la carpeta de la prueba `tf2reaudio_test` para ofrecer retirarla antes de validar las voces nuevas.

**Prueba:** con detección automática fallida o TF2 cerrado, el usuario todavía puede entender el problema y avanzar en lo que sí está disponible.

### 3.3. La grabadora necesita un recorrido completo

**Evidencia:** `PLAN.md:61–64` enumera controles por fila; `PLAN.md:131` explica conversión y recorte. No se define la preparación del micrófono ni la revisión de una toma.

Propondría este recorrido:

1. Elegir clase y línea, con nombre legible y texto de referencia cuando esté disponible.
2. Escuchar el original si se desea.
3. Elegir micrófono y comprobar un medidor de entrada.
4. Iniciar y detener con un botón, mostrando duración y el límite de diez segundos.
5. Escuchar la toma y elegir «Repetir», «Descartar» o «Guardar».
6. Mostrar qué variantes reemplaza y si se guardará solo localmente o se compartirá con el grupo.

No mantendría el micrófono activo fuera del momento necesario. El recorte automático debe poder desactivarse si elimina una consonante o una voz suave. Una toma silenciosa o saturada merece una explicación y la opción de repetir, sin descartar automáticamente el trabajo.

La frase «siendo local, nunca da problemas» debe corregirse: `localhost` permite el contexto adecuado, pero el permiso puede denegarse, faltar el dispositivo o producirse errores de acceso. Se necesitan mensajes específicos para esos casos. [Referencia: MDN, getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).

**Prueba:** bloquear el permiso, desconectar el micrófono y grabar silencio produce instrucciones comprensibles, sin quedar en una espera indefinida.

### 3.4. Guardar, compartir y aplicar son resultados distintos

**Evidencia:** `PLAN.md:11`, `PLAN.md:28` y `PLAN.md:80–85` combinan instalación local, sincronización periódica y recarga del juego. No se especifica cómo se comunican sus estados.

Cada toma debe indicar su situación real. Por ejemplo: «Guardada en este equipo · Pendiente de compartir · Pendiente de aplicar a TF2». En la cabecera bastan estados independientes de TF2 y del grupo, con una acción para resolver cada pendiente.

Preferiría un botón «Aplicar 3 cambios a TF2» y recarga manual por defecto durante la validación inicial. Una espera de cinco segundos agrupa cambios, pero no demuestra que recargar en ese momento sea cómodo durante una partida. El modo automático puede añadirse como preferencia después de medir su efecto.

Mostraría mensajes como «El anfitrión está desconectado. Tus 2 grabaciones siguen guardadas aquí» o «Cambios instalados; abre TF2 para escucharlos». No marcaría «Escuchado en el juego» por el simple envío de un comando.

También explicaría el alcance que se desprende de esta arquitectura: se modifican los sonidos instalados en cada equipo; para disfrutar la colección compartida, los amigos necesitan recibirla e instalarla. No se debe dar a entender que grabar aquí transmite la voz por el chat de la partida.

### 3.5. Compartir debe poder hacerse sin conocer el concepto de túnel

**Evidencia:** `PLAN.md:54`, `PLAN.md:90–101`. El enlace cambia al hostear; se pide una cuenta y se replica la lista de miembros. No está definido el recorrido para volver a conectarse al mismo grupo mediante un anfitrión distinto.

Usaría «Crear grupo», «Unirme a un grupo», «Compartir invitación» y «Actualizar enlace». El código o enlace se pega en la aplicación local. «Anfitrión» puede aparecer con una explicación corta: «Este equipo mantiene conectados a los demás mientras la aplicación está abierta».

Definiría una identidad estable de colección, independiente de la dirección temporal y del nombre del usuario. Cambiar el anfitrión no debería crear otra colección ni exigir volver a configurar Steam. Es necesario contemplar invitaciones vencidas, enlace caído, conexión interrumpida, versiones incompatibles y descargas reanudables.

Quick Tunnel puede servir para la prueba inicial. Cloudflare lo presenta para desarrollo y pruebas, sin garantía de disponibilidad y con dirección variable. Mi recomendación es diseñar recuperación y cambio de enlace desde el principio; un webhook de Discord no reemplaza ese recorrido. [Referencia: Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Separaría «quién aloja la conexión» de «quién administra el grupo». El plan debe resolver quién puede expulsar miembros, cómo se recupera el acceso y qué sucede con credenciales y revocaciones en copias que estuvieron desconectadas. Replicar hashes de contraseñas no resuelve por sí solo esas decisiones. Para la primera versión local, no hace falta cuenta.

### 3.6. Restaurar y sincronizar no deben sorprender al grupo

**Evidencia:** `PLAN.md:63` propone «Restore original»; `PLAN.md:93–95` incluye borrados sincronizados y fusión por fecha. No se define si restaurar afecta a una persona o a todas.

Separaría «Escuchar el original», «Usar el original en mi equipo» y «Restaurar el original para el grupo». La última acción debe nombrar su alcance y ofrecer deshacer. El historial debe permitir escuchar una versión antes de recuperarla.

Si dos personas graban la misma línea sin conexión, conservaría ambas tomas y avisaría del conflicto con autor y fecha. Se puede mantener una toma activa por defecto sin pedir resolver cada cambio, pero la alternativa debe quedar visible. No confiaría únicamente en el reloj de cada PC para decidir cuál es la nueva.

Las tres versiones previstas son útiles como historial corto, pero no equivalen a una copia de seguridad. Añadiría exportar/importar colección y definiría cómo proteger versiones en conflicto antes de eliminarlas por límite de historial.

**Prueba:** dos equipos modifican la misma línea desconectados; al reconectar, ninguna toma desaparece sin posibilidad de recuperación. Un borrado antiguo no reaparece por sincronizar con una copia desactualizada.

### 3.7. El catálogo debe guiar hacia la próxima acción

**Evidencia:** `PLAN.md:59–76` ofrece nueve clases, varias pestañas, variantes y un porcentaje por clase. Es una buena organización, pero puede mostrar demasiadas decisiones al empezar.

Mantendría la cuadrícula y abriría cada clase con «Empieza con MEDIC!» o «Continuar grabando». Añadiría «Solo pendientes» y «Siguiente línea». El reparto de voces debería llamarse «Responsable sugerido» si cualquiera puede grabar: «Voiced by» puede atribuir todas las voces a alguien que no las grabó.

El progreso debe contar comandos lógicos por separado de archivos y variantes. Una grabación que cubre tres archivos no debería aparentar tres tareas completadas. La interfaz debe mostrar el alcance antes de reemplazar variantes individuales existentes.

Los nombres técnicos y el editor por variante pueden estar en detalles. Las imágenes necesitan una alternativa local o textual: depender exclusivamente de la wiki deja incompleta la experiencia sin internet.

### 3.8. Accesibilidad e idioma deben ser requisitos de entrada

**Evidencia:** `PLAN.md:56` fija todo en inglés y `PLAN.md:63` utiliza símbolos como controles. No hay requisitos de teclado, lectores de pantalla o escalado.

Recomendaría español e inglés con preferencia persistente, etiquetas «Escuchar original», «Escuchar mi voz», «Grabar» y «Restaurar», y texto para los estados además del color. La interfaz debe funcionar con teclado, foco visible, zoom al 200 % y lectores de pantalla. Evitaría que grabar exija mantener presionado un botón.

Usaría WCAG 2.2 AA como objetivo verificable para la interfaz: contraste de texto normal de al menos 4.5:1, nombres accesibles y anuncios de estado. Para controles frecuentes apuntaría a 44 × 44 píxeles CSS por comodidad; el criterio AA de tamaño mínimo es 24 × 24 con excepciones, no 44 obligatorio. [Referencia: W3C, WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/).

«Todos» necesita un alcance explícito: inicialmente personas que juegan TF2 en las versiones de Windows y Linux probadas, incluidas personas sin experiencia técnica. No prometería compatibilidad universal. Importar una toma existente puede facilitar participar a quien no usa micrófono o prefiere otra herramienta; lo dejaría como mejora posterior al recorrido básico.

## 4. Riesgos técnicos que afectan directamente la experiencia

Estos puntos no invalidan la prueba de concepto. Deben resolverse antes de reutilizarla como base de una aplicación cotidiana.

| Evidencia | Problema y efecto visible | Mejora recomendada |
|---|---|---|
| `phase0_test.py:49–53` | El lector de cadenas no termina ante EOF sin terminador. Reproducido con un VPK sintético truncado. La app parecería congelada. | Detectar EOF, limitar la lectura al árbol declarado y mostrar un error recuperable de archivo incompleto. |
| `phase0_test.py:104–109` | Se supone que `recv(4)` entrega cuatro bytes. La cabecera fragmentada reproduce un error; tampoco se maneja EOF dentro del cuerpo. | Leer exactamente lo necesario, validar tamaños y convertir desconexiones y tiempos de espera en estados de conexión. |
| `phase0_test.py:116–124` | Se confirma el envío del comando, no el resultado audible. | Comunicar «Solicitud enviada» y ofrecer una comprobación de sonido; no confundirlo con aplicación verificada. |
| `phase0_test.py:127–141` | El instalador de prueba aún exige ffmpeg o lame y genera MP3 para ocho clases. | Etiquetarlo como prueba experimental. No presentarlo como implementación de la aplicación sin dependencias descrita en el plan. |
| `PLAN.md:120–124` | Se describen piezas como hechas, aunque `vpk_files` solo enumera nombres y RCON necesita robustez adicional. | Distinguir «prototipo comprobado» de «listo para integrar»; falta lectura de contenido y recuperación de errores. |
| `PLAN.md:92–95`, `PLAN.md:123–127` | Grabación, sincronización y servidor compartirían almacenamiento. No se define cómo evitar escrituras simultáneas o parciales. | Guardados atómicos, coordinación de escrituras y copia recuperable del manifiesto. JSON puede bastar si se prueban estas garantías. |
| `PLAN.md:13` | «Todos guardan la colección completa» no garantiza copia de una toma aún no sincronizada ni protege de borrados propagados. | Mostrar pendientes y última sincronización; ofrecer exportación y recuperación. Acotar «nadie pierde nada». |
| `PLAN.md:111` | Borrar la carpeta del mod retira sonidos, pero no datos, credenciales ni opciones añadidas a Steam. | Separar desactivar voces, borrar colección y desinstalar; guiar la limpieza sin eliminar otros ajustes. |

Mantendría un único artefacto fácil de distribuir, pero no haría del «único archivo fuente» una condición del producto. Si dificulta probar y mantener interfaz, audio y sincronización, separar el código internamente resulta compatible con una instalación sencilla.

## 5. Cómo modificaría las fases de PLAN.md

| Orden propuesto | Entrega | Condición para avanzar |
|---|---|---|
| 1. Primer uso local | Paquete abrible, detección/manual de TF2, micrófono, original, grabación, revisión, guardado y restauración. Español/inglés y teclado en ese recorrido. | Una persona nueva completa una voz sin ayuda ni cuenta. Probar Windows aquí, no al final. |
| 2. Uso durante una partida | Aplicación manual, diagnóstico de conexión, reinicio como alternativa y medida del efecto de `snd_restart`. | El usuario sabe cuándo oirá los cambios y puede recuperarse si la conexión falla. |
| 3. Colaboración básica | Grupo, invitación desde la UI, identidad de colección, sincronización, pendientes, cambio de anfitrión e historial. | Dos personas intercambian voces y conservan trabajo durante una desconexión y un conflicto. |
| 4. Distribución fiable | Actualización manual documentada, exportación/importación, desinstalación guiada y diagnóstico sin secretos. | Actualizar, cambiar de equipo o retirar el mod no requiere reconstruir la colección. |
| 5. Comodidad | Grabación consecutiva, filtros, importación de audio y ajustes simples de volumen/recorte. | Se justifican por dificultades observadas en usuarios reales. |

Mantendría fuera del primer alcance un editor multipista, generación con IA y una infraestructura permanente compleja. Priorizaría la primera voz y su recuperación sobre nuevas funciones sociales.

Cambios concretos de redacción del plan:

- Sustituir «Python + un script es suficiente» por una meta de apertura sin terminal para usuarios finales.
- Sustituir «siendo local, nunca da problemas» por requisitos de permisos, dispositivo y diagnóstico.
- Sustituir «todo es en caliente» por estados y condiciones comprobadas de aplicación al juego.
- Acotar «nadie pierde nada» a datos efectivamente replicados y recuperables.
- Sustituir «todo en inglés» por idiomas soportados y terminología coherente.
- Llevar la prueba de Windows y de usuarios nuevos a la primera fase.
- Añadir criterios de aceptación de interacción, no solo pruebas de funciones internas.

## 6. Validación con usuarios

Probaría con cinco personas que no hayan visto el proyecto, procurando distintas experiencias técnicas y ambos sistemas operativos. El tamaño sirve para una primera ronda cualitativa; no demuestra accesibilidad universal. Les pediría estas tareas, sin explicar por adelantado dónde pulsar:

| Tarea | Qué observar | Meta inicial propuesta |
|---|---|---|
| Instalar y grabar MEDIC | Dudas sobre instalación, TF2 y micrófono. | Al menos 4 de 5 completan la tarea sin instrucciones verbales; objetivo orientativo de 5 minutos, excluyendo descargas grandes. |
| Guardar y escuchar en TF2 | Si diferencian guardar de aplicar. | Todos pueden explicar qué paso queda pendiente. |
| Repetir y recuperar la primera toma | Confusión sobre sustitución o historial. | Recuperación en menos de un minuto. |
| Bloquear micrófono o elegir carpeta incorrecta | Calidad del mensaje y de la salida del error. | Se recuperan siguiendo la interfaz. |
| Grabar sin anfitrión y reconectar | Temor a perder trabajo y claridad de pendientes. | No se pierden tomas y el estado termina siendo comprensible. |
| Cambiar de anfitrión | Si confunden dirección nueva con grupo nuevo. | Conservan identidad, colección y configuración local. |
| Completar el flujo con teclado y zoom | Foco, nombres, tamaño y orden de controles. | Ninguna acción esencial queda inaccesible. Complementar con lector de pantalla. |

Estas cifras son objetivos propuestos, no resultados obtenidos. Tras cada ronda, corregiría los bloqueos observados antes de añadir funcionalidades.

**Orden recomendado de inversión:** apertura sencilla → primera voz guiada → estados claros → deshacer → colaboración recuperable. Es la secuencia que más probablemente permita a los amigos usar el programa sin depender de su autor.
