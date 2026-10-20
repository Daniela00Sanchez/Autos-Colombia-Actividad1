"""Autos Colombia, iteracion 1: aplicacion web local con Flask + SQLite."""
import secrets
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

from bd import RUTA_BD, inicializar
from servicios import (ErrorNegocio, TIPOS_NOVEDAD, consultar_placa, historial,
                       novedades_recientes, registrar_entrada, registrar_novedad,
                       registrar_salida, resumen)


def crear_app(ruta_bd=None, pruebas=False):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32), TESTING=pruebas,
                      RUTA_BD=Path(ruta_bd or RUTA_BD), MAX_CONTENT_LENGTH=64*1024)
    inicializar(app.config['RUTA_BD'])

    @app.context_processor
    def datos_globales():
        if '_csrf' not in session:
            session['_csrf'] = secrets.token_hex(24)
        return {'csrf_token': session['_csrf']}

    @app.before_request
    def validar_formulario():
        if request.method == 'POST':
            enviado = request.form.get('_csrf', '')
            if not secrets.compare_digest(str(session.get('_csrf', '')), enviado) or not enviado:
                return 'Solicitud no válida. Actualiza la página e inténtalo de nuevo.', 400

    @app.get('/')
    def inicio():
        return render_template('inicio.html', datos=resumen(app.config['RUTA_BD']), activa='inicio')

    @app.get('/consultar')
    def consultar():
        placa = request.args.get('placa', '').strip()
        resultado = None
        if placa:
            try:
                resultado = consultar_placa(placa, ruta=app.config['RUTA_BD'])
            except ErrorNegocio as exc:
                flash(str(exc), 'error')
        return render_template('consultar.html', placa=placa, resultado=resultado, activa='consultar')

    @app.route('/entrada', methods=['GET', 'POST'])
    def entrada():
        placa = (request.form if request.method == 'POST' else request.args).get('placa', '').strip().upper()
        if request.method == 'POST':
            try:
                resultado = registrar_entrada(placa, ruta=app.config['RUTA_BD'])
                flash(f"Entrada registrada: {resultado['placa']} a las {resultado['fecha_hora_entrada']}.", 'exito')
                return redirect(url_for('inicio'))
            except ErrorNegocio as exc:
                flash(str(exc), 'error')
        resultado = None
        if placa:
            try:
                resultado = consultar_placa(placa, ruta=app.config['RUTA_BD'])
            except ErrorNegocio:
                pass
        return render_template('entrada.html', placa=placa, resultado=resultado, activa='entrada')

    @app.route('/salida', methods=['GET', 'POST'])
    def salida():
        placa = (request.form if request.method == 'POST' else request.args).get('placa', '').strip().upper()
        if request.method == 'POST':
            try:
                resultado = registrar_salida(placa, ruta=app.config['RUTA_BD'])
                flash(f"Salida registrada: {resultado['placa']} a las {resultado['fecha_hora_salida']}.", 'exito')
                return redirect(url_for('inicio'))
            except ErrorNegocio as exc:
                flash(str(exc), 'error')
        resultado = None
        if placa:
            try:
                resultado = consultar_placa(placa, ruta=app.config['RUTA_BD'])
            except ErrorNegocio as exc:
                flash(str(exc), 'error')
        return render_template('salida.html', placa=placa, resultado=resultado, activa='salida')

    @app.route('/novedades', methods=['GET', 'POST'])
    def novedades():
        placa = (request.form if request.method == 'POST' else request.args).get('placa', '').strip().upper()
        tipo = request.form.get('tipo', 'Observacion general')
        descripcion = request.form.get('descripcion', '')
        if request.method == 'POST':
            try:
                registrar_novedad(placa, tipo, descripcion, ruta=app.config['RUTA_BD'])
                flash(f'Novedad guardada para {placa}.', 'exito')
                return redirect(url_for('novedades'))
            except ErrorNegocio as exc:
                flash(str(exc), 'error')
        resultado = None
        if placa:
            try:
                resultado = consultar_placa(placa, ruta=app.config['RUTA_BD'])
            except ErrorNegocio:
                pass
        return render_template('novedades.html', placa=placa, tipo=tipo,
                               descripcion=descripcion, resultado=resultado, tipos=TIPOS_NOVEDAD,
                               recientes=novedades_recientes(app.config['RUTA_BD']), activa='novedades')

    @app.get('/historial')
    def ver_historial():
        placa = request.args.get('placa', '').strip()
        desde = request.args.get('desde', '')
        hasta = request.args.get('hasta', '')
        registros = []
        try:
            registros = historial(placa, desde, hasta, ruta=app.config['RUTA_BD'])
        except ErrorNegocio as exc:
            flash(str(exc), 'error')
        return render_template('historial.html', registros=registros, placa=placa,
                               desde=desde, hasta=hasta, activa='historial')

    return app


if __name__ == '__main__':
    aplicacion = crear_app()
    print('Autos Colombia listo. Abre: http://127.0.0.1:5000')
    aplicacion.run(host='127.0.0.1', port=5000, debug=False)
