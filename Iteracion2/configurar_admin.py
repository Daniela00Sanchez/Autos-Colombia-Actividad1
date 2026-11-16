"""Crea la cuenta inicial del administrador por consola, sin clave publicada."""
from getpass import getpass
from bd import inicializar, RUTA_BD
from servicios import ErrorNegocio
from servicios_i2 import crear_administrador_inicial

if __name__=='__main__':
    inicializar(RUTA_BD)
    print('AUTOS COLOMBIA - Crear administrador inicial')
    print('Los caracteres de la contraseña no se muestran al escribirlos.')
    nombre=input('Nombre completo: ').strip()
    usuario=input('Usuario (ejemplo admin01): ').strip()
    clave=getpass('Contraseña (mínimo 10 caracteres): ')
    confirmar=getpass('Repite la contraseña: ')
    if clave != confirmar:
        print('ERROR: Las contraseñas no coinciden.')
    else:
        try:
            crear_administrador_inicial(usuario,nombre,clave,RUTA_BD)
            print('Administrador creado. Ahora puedes iniciar el programa con: python app.py')
        except ErrorNegocio as exc:
            print('ERROR:',exc)
