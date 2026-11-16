# instagram-unfollowers

Script en Python que compara tus seguidores con las cuentas que sigues y te muestra:

- 🔻 Quién no te sigue de vuelta
- 🔺 A quién no sigues de vuelta

Usa **solo el export oficial de Instagram**. No inicia sesión, no usa scraping y no necesita credenciales, así que no arriesga tu cuenta.

## Requisitos

- Python 3.8 o superior
- Sin dependencias externas (solo usa `json` y `pathlib`)

## Cómo usarlo

1. Descarga tus datos desde Instagram:
   **Configuración → Centro de cuentas → Tu información y permisos → Descargar tu información**
   - Elige formato **JSON**
   - Selecciona solo *Seguidores y seguidos*
2. Del archivo descargado, copia la carpeta `followers_and_following` (que contiene `followers_*.json` y `following.json`) a la misma carpeta que `main.py`.
3. Ejecuta:

   ```bash
   python3 main.py
   ```

## Ejemplo de salida

```
Sigues a 210 cuentas.
Te siguen 90 cuentas.

🔻 No te siguen de vuelta (135):
  - usuario_ejemplo1
  - usuario_ejemplo2

🔺 Te siguen pero no los sigues (15):
  - usuario_ejemplo3
```

## Privacidad

Los archivos `followers_*.json` y `following.json` contienen nombres de usuario de otras personas. Están incluidos en el `.gitignore` para que no se suban por accidente.

## Cómo funciona

- Lee todos los `followers_*.json` y `following.json` dentro de `followers_and_following/`, extrayendo los usernames (en orden: `title` → `value` → final de `href`).
- Los guarda en `set` de Python.
- Calcula las diferencias con operaciones de conjuntos: `following - followers` y `followers - following`.
