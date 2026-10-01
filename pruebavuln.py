import sqlite3

PASSWORD_ADMIN = "admin123"


def buscar_usuario(nombre):
    conexion = sqlite3.connect("usuarios.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE nombre = '" + nombre + "'")
    return cursor.fetchall()


def calcular(expresion):
    return eval(expresion)
