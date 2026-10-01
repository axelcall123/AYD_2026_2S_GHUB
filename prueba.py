import sqlite3

PASSWORD_ADMIN = "admin123"  # Credencial hardcodeada


def buscar_usuario(nombre):
    # SQL Injection: concatenación directa de entrada
    conexion = sqlite3.connect("usuarios.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE nombre = '" + nombre + "'")
    return cursor.fetchall()


def calcular(expresion):
    # Ejecución de código arbitrario con eval
    return eval(expresion)
