# KHDP API

[English](./README.md) · [한국어](./README.ko.md) · **Español** · [中文](./README.zh-CN.md) · [日本語](./README.ja.md)

> *Traducción IA. Fuente canónica: [README.md](./README.md). Última sincronización: 2026-05-30.*

La interfaz para desarrolladores de la **Korea Health Data Platform** — buscar, descargar y enviar conjuntos de datos de investigación médica desde `curl`, Python o cualquier agente de codificación con IA.

- API REST en `https://khdp.net/_api` — ver [docs/REST_API.md](./docs/REST_API.md).
- La navegación anónima funciona; la autenticación (App Key / OAuth / API Token) habilita descargas y envíos.
- Una misma sesión autenticada alimenta la CLI, la biblioteca de Python y un servidor MCP para Claude Code, Codex CLI, Cursor y Gemini CLI.

> Repositorio: `khdp-api` · paquete Python: `khdp` (`pip install khdp`).

## Inicio rápido — cuatro formas de llamar a la API

### 1. curl
```bash
curl 'https://khdp.net/_api/open/datasets?query=heart&limit=5' | jq '.items[].code'
```

### 2. Python (SDK `khdp`)
```python
# pip install khdp
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/open/datasets", params={"query": "heart", "limit": 5})
    print([d["code"] for d in r.json()["items"]])
```

### 3. Claude Code (MCP)
```bash
pip install khdp
khdp login
claude mcp add khdp -- khdp-mcp
```
Luego pídale a Claude Code: *"Busca en KHDP conjuntos de datos sobre enfermedades cardíacas y resume los mejores resultados."*

### 4. OpenAI Codex CLI
Añada [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) a `~/.codex/config.toml` y ejecute `khdp login` una vez.

> Guía completa: [docs/quickstart.es.md](./docs/quickstart.es.md). Referencia de endpoints: [docs/REST_API.md](./docs/REST_API.md).

## Instalación

```bash
pipx install khdp                 # recomendado — aísla del Python del sistema
pipx install 'khdp[keyring]'      # + almacenamiento de tokens en el llavero del SO
```

El paquete instala:
- `khdp` — CLI (login, datasets, submissions, comando `api` directo)
- `khdp-mcp` — servidor MCP para agentes de codificación
- `import khdp` — biblioteca de Python

## Autenticación

Tres tipos de credenciales, intercambiables entre CLI, SDK y MCP.

| Tipo | Cabecera(s) | Identidad | Uso típico |
| --- | --- | --- | --- |
| **App Key** | `X-App-Id` + `X-App-Secret` | la aplicación | bots de servidor, espejos de catálogo público |
| **OAuth (PKCE)** | `Authorization: Bearer <jwt>` | el usuario | CLI, MCP, SaaS que actúa en nombre del usuario |
| **API Token** (PAT) | `Authorization: Bearer khdp_pat_…` | el usuario | notebooks, agentes IA (larga duración, sin refresh) |

Solicite un `app_id` al equipo de KHDP. Los tokens personales se generan en *Settings → Account → API Token* en <https://khdp.net>.

```toml
# ./khdp.local.toml  (o ~/.config/khdp/config.toml)
app_id     = "00000000-0000-0000-0000-000000000000"
# app_secret = "..."             # App Key
# api_key    = "khdp_pat_..."    # token personal de API
api_base   = "https://khdp.net/_api"
```

O por variable de entorno: `KHDP_APP_ID`, `KHDP_APP_SECRET`, `KHDP_TOKEN`.

## CLI

```bash
khdp login [--no-browser]                              # login PKCE (redirección loopback)
khdp status | refresh | logout | config

khdp datasets list      [--query KW] [--policy open|restricted|...]
khdp datasets show      <code>[@<version>]
khdp datasets files     <code>[@<version>] [--key PREFIX]
khdp datasets download  <code>[@<version>] [--out DIR] [--dry-run]

khdp api METHOD PATH [--query K=V ...] [--data '{...}']
                     [--auth {auto,app-key,api-key,oauth}]
```

`--auth auto` elige en este orden: API Token → OAuth en caché → App Key.

## Servidor MCP

```bash
khdp mcp     # transporte stdio
```

| Herramienta | Propósito |
| --- | --- |
| `khdp_auth_status`  | ¿Hay sesión iniciada? ¿Cuándo expira el token? |
| `khdp_auth_refresh` | Rotar el refresh token. |
| `khdp_auth_logout`  | Eliminar tokens locales. |
| `khdp_api_request`  | Llamada HTTP autenticada a cualquier endpoint de KHDP. |

El servidor MCP nunca acepta contraseñas en los argumentos de herramientas. El login se inicia fuera de banda con `khdp login` en la terminal del usuario; el servidor MCP solo lee la caché de tokens resultante.

## Wrappers para agentes

| Plataforma | Configuración |
| --- | --- |
| Claude Code | `claude mcp add khdp -- khdp-mcp` y copiar [`wrappers/claude-code/skills/khdp-auth`](./wrappers/claude-code/skills/khdp-auth) a `~/.claude/skills/` |
| OpenAI Codex CLI | Añadir [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) a `~/.codex/config.toml` |
| Gemini CLI | Fusionar [`wrappers/gemini/settings.example.json`](./wrappers/gemini/settings.example.json) en `~/.gemini/settings.json` |

Cursor usa el mismo servidor MCP — apunte su configuración `mcp.servers` a `khdp-mcp`.

## Documentación

- [Quickstart](./docs/quickstart.es.md) — los primeros cinco minutos
- [Referencia de la API REST](./docs/REST_API.md) — endpoints, payloads, scopes, errores (en inglés)
- [`examples/`](./examples/) — scripts de Python ejecutables (búsqueda anónima, detalle de dataset, descarga autenticada)
- [`AGENTS.md`](./AGENTS.md) — usar el conector desde un agente de codificación (en inglés)
- [Especificación canónica](https://khdp.net/docs/external-api) — sitio oficial de documentación

## Seguridad

- Login PKCE (RFC 7636) sobre redirección loopback (RFC 8252). El binario de la CLI no contiene ningún secreto de cliente.
- La interfaz MCP omite deliberadamente el parámetro de contraseña — las contraseñas nunca llegan al contexto del LLM.
- Los tokens se guardan en el llavero del SO cuando `khdp[keyring]` está instalado; si no, en un archivo JSON con permisos `0600` en el directorio de configuración del usuario.
- Aislamiento de tokens por `app_id`.

Modelo de amenazas completo y política de reporte en [`SECURITY.md`](./SECURITY.md).

## Desarrollo

```bash
git clone https://github.com/KoreaHealthDataPlatform/khdp-api.git
cd khdp-api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
pytest
```

## Licencia

MIT. Ver [LICENSE](./LICENSE).
