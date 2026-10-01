import os
import subprocess
import requests
import sys


LM_STUDIO_URL = os.getenv(
    "LM_STUDIO_URL",
    "http://192.168.0.27:1234"
)


def obtener_modelo():
    """Obtiene el nombre del modelo desde LM Studio o env vars."""
    try:
        response = requests.get(
            f"{LM_STUDIO_URL}/api/v1/models",
            timeout=10
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

        # Usar el modelo configurado en ENV o el primero disponible
        modelo_preferido = os.getenv(
            "LM_STUDIO_MODEL",
            modelos[0].get("id") # Fallback al primer modelo si no hay ENV
        )
        
        # Verificar si el modelo preferido existe en la lista descargada
        ids_disponibles = [m.get("id") for m in modelos]
        if modelo_preferido in ids_disponibles:
            return modelo_preferido
        else:
            print(f"Advertencia: Modelo '{modelo_preferido}' no encontrado. Usando el primero disponible: {ids_disponibles[0]}")
            return ids_disponibles[0]

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"No se pudo conectar a LM Studio: {e}")


def obtener_archivos_modificados():
    try:
        resultado = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "HEAD^",
                "HEAD"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        archivos = resultado.stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        print("No se pudo obtener el diff (posiblemente primer commit o sin cambios). Se analizarán archivos de ejemplo.")
        return []

    extensiones = (
        ".go", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".txt"
    )

    return [
        archivo
        for archivo in archivos
        if archivo.endswith(extensiones)
        and os.path.isfile(archivo)
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
    
    # CORRECCIÓN CRÍTICA: Inyectar el código en el prompt
    prompt = f"""
Eres un revisor de código dentro de un pipeline CI/CD.

Tu objetivo es detectar problemas reales introducidos por el cambio.

Analiza únicamente problemas respaldados por el código proporcionado.

Prioriza:
1. Vulnerabilidades de seguridad.
2. Errores lógicos.
3. Manejo incorrecto de errores.
4. Problemas de concurrencia.
5. Validación insuficiente de entradas.
6. Uso incorrecto de APIs.
7. Problemas que puedan provocar fallos en producción.
8. Problemas de mantenibilidad relevantes.

NO marques como problema:
- preferencias de estilo personales;
- refactorizaciones innecesarias;
- cambios que no tengan impacto real;
- problemas hipotéticos sin evidencia.

Para cada hallazgo devuelve:

SEVERIDAD: CRITICAL | HIGH | MEDIUM | LOW

ARCHIVO:
LÍNEA:
PROBLEMA:
EXPLICACIÓN:
RECOMENDACIÓN:

Si no encuentras problemas reales:
NO_ISSUES_FOUND

No inventes líneas, vulnerabilidades ni comportamiento que no pueda deducirse del código.

---
CÓDIGO A ANALIZAR ({archivo}):
---
{codigo}
"""

    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un auditor de código especializado "
                    "en revisión de Pull Requests. Sé conciso y directo."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "stream": False
    }

    try:
        response = requests.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        data = response.json()
        
        # Validación básica de la respuesta
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
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
        # Opcional: Salir con éxito si no hay nada que hacer
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
            resultado = auditar_codigo(
                modelo,
                archivo,
                codigo
            )

            print("\n")
            print(resultado)

        except Exception as error:
            print(f"\n❌ Error durante la auditoría de {archivo}: {error}")
            # No salimos inmediatamente para intentar analizar otros archivos si es posible
            # sys.exit(1) 
            
if __name__ == "__main__":
    main()
