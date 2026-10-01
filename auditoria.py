import os
import re
import subprocess
import sys

import requests

# Cargar .env solo si python-dotenv está instalado (en CI no es necesario).
# load_dotenv() NO sobrescribe variables que ya existan en el entorno.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


MODELO_POR_DEFECTO = "qwen/qwen2.5-coder-14b"


def obtener_config():
    url = os.getenv("LM_STUDIO_URL")
    if not url:
        raise RuntimeError(
            "Falta LM_STUDIO_URL. Defínela en .env (local) "
            "o como secret en GitHub Actions."
        )

    # Se usa 'or' porque en GitHub Actions una variable no definida
    # llega como cadena vacía.
    return {
        "url": url.rstrip("/"),
        "modelo": os.getenv("LM_STUDIO_MODEL") or MODELO_POR_DEFECTO,
        "timeout": int(os.getenv("LM_STUDIO_TIMEOUT") or "300"),
        "api_key": os.getenv("LM_STUDIO_API_KEY") or "",
        "base_ref": os.getenv("BASE_REF") or "",
        "fallar": (os.getenv("FALLAR_EN_CRITICAL") or "false").lower() == "true",
    }


try:
    CONFIG = obtener_config()
except RuntimeError as e:
    print(f"❌ Error de configuración: {e}")
    sys.exit(1)

LM_STUDIO_URL = CONFIG["url"]

EXTENSIONES = (".py"
               #, ".go", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs"
               )


def headers():#
    h = {"Content-Type": "application/json"}
    if CONFIG["api_key"]:
        h["Authorization"] = f"Bearer {CONFIG['api_key']}"
    return h


def obtener_modelo():
    try:
        response = requests.get(
            f"{LM_STUDIO_URL}/api/v1/models",
            headers=headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        modelos = [m for m in data.get("models", []) if m.get("type") == "llm"]
        if not modelos:
            raise RuntimeError("No se encontró ningún modelo LLM en LM Studio")

        ids_disponibles = [m.get("key") for m in modelos]
        preferido = CONFIG["modelo"]

        if preferido in ids_disponibles:
            return preferido

        print(
            f"Advertencia: modelo '{preferido}' no encontrado. "
            f"Usando: {ids_disponibles[0]}"
        )
        return ids_disponibles[0]

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"No se pudo conectar a LM Studio: {e}")


def obtener_archivos_modificados():
    """En un PR compara contra la rama base; si no, contra el commit anterior."""
    if CONFIG["base_ref"]:
        comando = ["git", "diff", "--name-only", f"origin/{CONFIG['base_ref']}...HEAD"]
    else:
        comando = ["git", "diff", "--name-only", "HEAD^", "HEAD"]

    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError:
        print("No se pudo obtener el diff (¿primer commit o rama base ausente?).")
        return []

    return [
        a
        for a in resultado.stdout.strip().splitlines()
        if a.endswith(EXTENSIONES) and os.path.isfile(a)
    ]


def leer_archivo(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            return archivo.read()
    except UnicodeDecodeError:
        return None
    except Exception as e:
        print(f"Error leyendo {ruta}: {e}")
        return None


def auditar_codigo(modelo, archivo, codigo):
    codigo_numerado = "\n".join(
        f"{i}: {linea}" for i, linea in enumerate(codigo.splitlines(), 1)
    )

    prompt = f"""Archivo: {archivo}

=== CÓDIGO ===
{codigo_numerado}
=== FIN DEL CÓDIGO ===

Responde esta lista completa, una línea por punto, con SI (indicando las
líneas) o NO:

1. SQL injection (consultas construidas concatenando texto):
2. Command injection (os.system, subprocess con shell, exec.Command con entrada del usuario):
3. Ejecución dinámica de código (eval, exec, pickle):
4. Credenciales, claves o contraseñas escritas en el código:
5. Path traversal (rutas controladas por el usuario):
6. Manejo incorrecto de errores (except vacío, errores ignorados):
7. Falta de validación de entradas:

Después, por cada punto con SI escribe:

SEVERIDAD: CRITICAL | HIGH | MEDIUM | LOW
LÍNEA: <número>
PROBLEMA: <una frase>
RECOMENDACIÓN: <una frase>

Reglas:
- eval/exec, command injection y credenciales hardcodeadas son CRITICAL.
- Marca SI solo si hay una vulnerabilidad clara en el código mostrado.
- Leer secretos desde variables de entorno es correcto y NO es un problema.
"""

    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un auditor de seguridad de código. "
                    "Analizas el código con rigor y respondes en español, "
                    "de forma concisa."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 1500,
        "stream": False,
    }

    try:
        response = requests.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            json=payload,
            headers=headers(),
            timeout=CONFIG["timeout"],
        )
        response.raise_for_status()
        data = response.json()

        if data.get("choices"):
            return data["choices"][0]["message"]["content"]
        return "Error: La API no devolvió ninguna elección válida."

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error al comunicar con LM Studio: {e}")


def tiene_critical(resultado):
    return re.search(
        r"^\s*\**SEVERIDAD:?\**\s*CRITICAL\s*$", resultado, re.MULTILINE | re.IGNORECASE
    ) is not None


def main():
    print("=" * 70)
    print("🤖 AUDITORÍA DE CÓDIGO CON IA LOCAL")
    print("=" * 70)

    print("\nConectando con LM Studio...")
    try:
        modelo = obtener_modelo()
    except RuntimeError as e:
        print(f"❌ Error crítico: {e}")
        sys.exit(1)

    print(f"Modelo utilizado: {modelo}")
    print(f"Modo: {'BLOQUEANTE (falla con CRITICAL)' if CONFIG['fallar'] else 'INFORMATIVO'}")

    archivos = obtener_archivos_modificados()
    if not archivos:
        print("\nNo se encontraron archivos modificados para analizar.")
        sys.exit(0)

    print("\nArchivos a analizar:")
    for archivo in archivos:
        print(f"  - {archivo}")

    archivos_con_critical = []

    for archivo in archivos:
        codigo = leer_archivo(archivo)
        if codigo is None:
            print(f"\n⚠️ No se pudo leer: {archivo}")
            continue

        print("\n" + "=" * 70)
        print(f"🔍 ANALIZANDO: {archivo}")
        print("=" * 70)

        try:
            resultado = auditar_codigo(modelo, archivo, codigo)
            print(resultado)
            if tiene_critical(resultado):
                archivos_con_critical.append(archivo)
        except Exception as error:
            print(f"\n❌ Error durante la auditoría de {archivo}: {error}")

    print("\n" + "=" * 70)
    if archivos_con_critical:
        print("🚨 Hallazgos CRITICAL en:")
        for a in archivos_con_critical:
            print(f"  - {a}")
        if CONFIG["fallar"]:
            print("Quality gate: el pipeline falla.")
            sys.exit(1)
    else:
        print("✅ Sin hallazgos CRITICAL.")


if __name__ == "__main__":
    main()
