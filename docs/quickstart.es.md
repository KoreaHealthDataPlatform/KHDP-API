# Quickstart

[English](./quickstart.en.md) · [한국어](./quickstart.ko.md) · **Español** · [中文](./quickstart.zh-CN.md) · [日本語](./quickstart.ja.md)

> *Traducción IA. Fuente canónica: [quickstart.en.md](./quickstart.en.md). Última sincronización: 2026-05-30.*

De cero a una primera llamada autenticada a la API de KHDP — unos cinco minutos.

Esta guía complementa el [README](../README.md), que muestra cuatro puntos de entrada en paralelo. Aquí recorremos el camino Python / CLI de principio a fin y terminamos integrando Claude Code.

## Antes de empezar

- Python ≥ 3.10
- Una de las siguientes credenciales:
  - **Token personal de API** — la opción más rápida: <https://khdp.net> → *Settings → Account → API Token*. Una cadena que empieza por `khdp_pat_…`.
  - **`app_id`** — solicítelo al equipo de KHDP si necesita login PKCE o autenticación App Key. Las apps tipo CLI deben registrar `http://127.0.0.1:*/callback` como URL de redirección permitida.
- Para el paso del agente: [Claude Code](https://claude.com/claude-code) instalado.

> Los tres primeros pasos funcionan sin `app_id` — basta con un token personal de API (o ninguna credencial para búsquedas públicas).

## 1. Instalación

```bash
pipx install khdp          # aísla del Python del sistema
# o bien
pipx install 'khdp[keyring]'   # guarda los tokens en el llavero del SO
```

Verifique:

```bash
khdp --version
khdp config              # imprime la configuración resuelta
```

## 2. Configuración

Elija un camino. Puede cambiar más tarde.

### Camino A — Token personal de API (recomendado para el primer intento)

```bash
export KHDP_TOKEN="khdp_pat_…"
```

Listo. No hace falta `khdp login`; todas las llamadas usan el token directamente. Larga duración, sin refresh.

### Camino B — `app_id` + login PKCE

```bash
export KHDP_APP_ID="00000000-0000-0000-0000-000000000000"
khdp login                 # abre el navegador y captura el callback localmente
khdp status                # confirme: autenticado, expiración del token
```

`--no-browser` imprime la URL para máquinas remotas / sin navegador.

## 3. Buscar conjuntos de datos públicos (funciona anónimo)

CLI:

```bash
khdp datasets list --query heart --limit 5
```

La misma llamada desde Python:

```python
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/open/datasets", params={"query": "heart", "limit": 5})
    for d in r.json()["items"]:
        print(d["code"], "—", d["title"])
```

Elija un `code` de la salida — en el resto de la guía lo llamaremos `<CODE>`.

## 4. Inspeccionar un dataset Open

El listado de archivos requiere el scope `datasets` en la credencial que use.

```bash
khdp datasets show     <CODE>
khdp datasets files    <CODE>            # listado raíz
khdp datasets files    <CODE> --key imaging/
```

> Si recibe `403 App does not have datasets scope`, pida al equipo de KHDP que conceda el scope `datasets` a su aplicación. Aplica tanto a App Key como a OAuth.

## 5. Descargar archivos

Primero un dry-run para ver qué pasaría — no se transfieren bytes:

```bash
khdp datasets download <CODE> --out ./data --dry-run
```

Luego, la descarga real:

```bash
khdp datasets download <CODE> --out ./data
```

`download` pagina el endpoint `files-download-link-all` del servidor (1000 claves por página) y descarga cada archivo en streaming. Use `--max-pages N` para detenerse tras N páginas cuando solo quiera verificar el flujo.

> Solo se pueden descargar datasets con `accessPolicy=open`. Los Restricted / Credentialed / ContributorReview devuelven `400 Is Not Open Access Dataset` — solicite acceso desde la web de KHDP.

## 6. Llamar desde Claude Code (MCP)

```bash
claude mcp add khdp -- khdp-mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
```

Abra Claude Code y pruebe:

> *"Use las herramientas khdp para buscar en KHDP datasets sobre enfermedades cardíacas y muéstreme el listado de archivos del mejor resultado."*

Claude Code llama al servidor MCP, que reutiliza la caché de tokens del paso 2. La contraseña nunca pasa por el contexto del LLM.

El mismo servidor MCP da soporte a [OpenAI Codex CLI](../wrappers/codex/), [Gemini CLI](../wrappers/gemini/) y Cursor.

## Errores frecuentes

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `401` en cualquier llamada | cabecera incorrecta, token OAuth expirado o entorno equivocado | `khdp status`; `khdp refresh`; revise `khdp config` |
| `403 App does not have datasets scope` | la aplicación emisora del token no tiene scope `datasets` | solicite el scope al equipo de KHDP (aplica también a OAuth) |
| `403 Auth type "openApiApp" is not allowed` | endpoint de submission llamado con App Key | use OAuth — submissions son solo de usuario |
| `404 Dataset Not Found` | `code` incorrecto o `version` no publicada | omita la versión (por defecto `@latest`) o use `khdp datasets list` |
| `400 Is Not Open Access Dataset` al descargar | el dataset no es Open | la API externa solo descarga datasets Open |
| `khdp login` se queda colgado | la URL de redirección loopback no está registrada en la app | pida al equipo de KHDP que registre `http://127.0.0.1:*/callback` |
| `khdp-mcp` no encontrado | el shim de `pipx` no está en `PATH` | `pipx ensurepath` y reabra la terminal |

## Qué leer a continuación

- [Referencia de la API REST](./REST_API.md) — cada endpoint, payload, scope y error (en inglés)
- [`AGENTS.md`](../AGENTS.md) — usar el conector desde un agente de codificación en profundidad (en inglés)
- [Especificación canónica KHDP](https://khdp.net/docs/external-api) — sitio oficial
- [Modelo de seguridad](../SECURITY.md) — PKCE, redirección loopback, almacenamiento de tokens, modelo de amenazas (en inglés)
