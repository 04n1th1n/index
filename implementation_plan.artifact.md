# Plan de Integración: Android Studio Assistant + Claude Code

Este plan establece un mecanismo de memoria compartida para sincronizar el contexto entre el asistente del IDE y la herramienta de CLI Claude Code.

## Cambios Propuestos

### Raíz del Proyecto

#### [NEW] [IDE_CONTEXT.md](file:///C:/Users/Jonathan/hotel_management_system/IDE_CONTEXT.md)
*   Creación de un archivo de bitácora para almacenar el estado de la sesión, objetivos actuales y tareas completadas.

#### [MODIFY] [CLAUDE.md](file:///C:/Users/Jonathan/hotel_management_system/CLAUDE.md)
*   Añadir una sección de "Interoperabilidad con IDE Assistant".
*   Instrucciones para que Claude Code lea `IDE_CONTEXT.md` al inicio y lo actualice al finalizar.

## Plan de Verificación

### Pruebas Automatizadas
*   Ejecutar `claude "quien eres y que sabes del contexto actual?"` vía shell para confirmar que lee el archivo.

### Verificación Manual
*   Confirmar que el usuario puede ver los cambios en ambos entornos.
