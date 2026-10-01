import os
import subprocess
import sys

import requests

# Cargar .env solo si python-dotenv está instalado (en CI no es necesario).
# load_dotenv() NO sobrescribe variables que ya existan en el entorno,
# así que en GitHub Actions siempre manda lo definido en vars/secrets.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


MODELO_POR_DEFECTO = "deepseek-coder-6.7b-base@q4_k_s"


def obtener_config():
    url = os.getenv("LM_STUDIO_URL")
    if not url:
        raise RuntimeError(
            "Falta LM_STUDIO_URL. Defínela en .env (local) "
            "o como secret/variable en GitHub Actions."
        )

    # Se usa 'or' (y no el segundo argumento de getenv) porque en GitHub
    # Actions una variable no definida llega como cadena vacía.
    return {
        "url": url.rstrip("/"),
        "modelo": os.getenv("LM_STUDIO_MODEL") or MODELO_POR_DEFECTO,
        "timeout": int(os.getenv("LM_STUDIO_TIMEOUT") or "300"),
        "api_key": os.getenv("LM_STUDIO_API_KEY") or "",  # opcional
    }


try:
    CONFIG = obtener_config()
except RuntimeError as e:
    print(f"❌ Error de configuración: {e}")
    sys.exit(1)

LM_STUDIO_URL = CONFIG["url"]


def headers():
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

        modelos = [
            modelo
            for modelo in data.get("models", [])
            if modelo.get("type") == "llm"
        ]

        if not modelos:
            raise RuntimeError("No se encontró ningún modelo LLM en LM Studio")

        # En /api/v1/models el identificador está en 'key'
        ids_disponibles = [m.get("key") for m in modelos]

        modelo_preferido = CONFIG["modelo"]

        if modelo_preferido in ids_disponibles:
            return modelo_preferido

        print(
            f"Advertencia: Modelo '{modelo_preferido}' no encontrado. "
            f"Usando el primero disponible: {ids_disponibles[0]}"
        )
        return ids_disponibles[0]

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"No se pudo conectar a LM Studio: {e}")


def obtener_archivos_modificados():
    try:
        resultado = subprocess.run(
            ["git", "diff", "--name-only", "HEAD^", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        archivos = resultado.stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        print(
            "No se pudo obtener el diff "
            "(posiblemente primer commit o sin cambios)."
        )
        return []

    extensiones = (
        ".go", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".txt"
    )

    return [
        archivo
        for archivo in archivos
        if archivo.endswith(extensiones) and os.path.isfile(archivo)
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

Revisa el código anterior buscando vulnerabilidades de seguridad
(SQL injection, command injection, eval/exec, credenciales hardcodeadas,
path traversal), errores lógicos y mal manejo de errores.

Por cada problema responde exactamente así:

SEVERIDAD: CRITICAL | HIGH | MEDIUM | LOW
LÍNEA: <número>
PROBLEMA: <una frase>
RECOMENDACIÓN: <una frase>

Solo si el código no tiene ningún problema, responde: NO_ISSUES_FOUND
"""

    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un auditor de código especializado "
                    "en revisión de seguridad. Sé conciso y directo."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
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

        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        return "Error: La API no devolvió ninguna elección válida."

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error al comunicar con LM Studio: {e}")

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

    archivos = obtener_archivos_modificados()

    if not archivos:
        print("\nNo se encontraron archivos modificados para analizar.")
        sys.exit(0)

    print("\nArchivos a analizar:")
    for archivo in archivos:
        print(f"  - {archivo}")

    for archivo in archivos:
        codigo = leer_archivo(archivo)

        if codigo is None:
            print(f"\n⚠️ No se pudo leer: {archivo}")
            continue

        print("\n")
        print("=" * 70)
        print(f"🔍 ANALIZANDO: {archivo}")
        print("=" * 70)

        try:
            resultado = auditar_codigo(modelo, archivo, codigo)
            print("\n")
            print(resultado)
        except Exception as error:
            print(f"\n❌ Error durante la auditoría de {archivo}: {error}")
            # Se continúa con los demás archivos


if __name__ == "__main__":
    main()
