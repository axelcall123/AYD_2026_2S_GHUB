import os
import sqlite3

def buscar_usuario(nombre):
    # Vulnerabilidad: SQL Injection
    conexion = sqlite3.connect('usuarios.db')
    cursor = conexion.cursor()
    query = "SELECT * FROM usuarios WHERE nombre = '" + nombre + "'"
    cursor.execute(query)
    return cursor.fetchall()

def ejecutar_comando_sistema(entrada):
    # Vulnerabilidad: Command Injection
    os.system("echo " + entrada)

def cargar_configuracion(ruta_archivo):
    # Vulnerabilidad: Path Traversal
    with open(ruta_archivo, 'r') as f:
        return f.read()
