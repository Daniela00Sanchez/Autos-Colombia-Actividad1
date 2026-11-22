"""Autos Colombia: funciones de parqueadero de las iteraciones 1 y 2."""
import os
import secrets
from pathlib import Path
from functools import wraps
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, send_file

from io import BytesIO
from bd import RUTA_BD, conectar, inicializar
from servicios import (ErrorNegocio, TIPOS_NOVEDAD, consultar_placa, historial,
                       novedades_recientes, registrar_entrada, registrar_novedad,
                       registrar_salida, resumen)
from servicios_i2 import (anular_movimiento, abrir_sesion, autenticar, cambiar_operador,
                         cerrar_sesion, corregir_vehiculo, crear_celda, crear_operador,
                         crear_vehiculo, disponibles, editar_celda, eliminar_celda,
                         eliminar_operador, eliminar_vehiculo, listar_celdas,
                         listar_usuarios, operadores_conectados, resumen_celdas,
                         validar_sesion, ver_auditoria)
from servicios_i3 import (registrar_pago, obtener_pago, listar_pagos,
                          previsualizar_periodo, anular_pago, MEDIOS_PAGO)


def obtener_clave(ruta_bd, pruebas):
    if pruebas:
        return os.environ.get('AUTOS_COLOMBIA_SECRET', 'solo-para-pruebas-locales')
    if os.environ.get('AUTOS_COLOMBIA_SECRET'):
        return os.environ['AUTOS_COLOMBIA_SECRET']
    archivo=Path(ruta_bd).parent/'.session_key'
    if not archivo.exists():
        # Se crea una vez, para que las sesiones sobrevivan a reiniciar el programa.
        try:
            with archivo.open('x',encoding='utf8') as f:
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    return archivo.read_text(encoding='utf8').strip()


def crear_app(ruta_bd=None, pruebas=False):
    app=Flask(__name__)
    destino=Path(ruta_bd or RUTA_BD)
    inicializar(destino)
    app.config.update(SECRET_KEY=obtener_clave(destino,pruebas),TESTING=pruebas,
                      RUTA_BD=destino, MAX_CONTENT_LENGTH=64*1024,
                      SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=bool(os.environ.get('AUTOS_HTTPS')))

    def ruta():
        return app.config['RUTA_BD']

    @app.before_request
    def comprobar_acceso():
        g.usuario=None
        if request.method=='POST' and request.endpoint != 'iniciar_sesion':
            recibido=request.form.get('_csrf','')
            esperado=session.get('_csrf','')
            if not recibido or not esperado or not secrets.compare_digest(str(esperado),str(recibido)):
                return 'Solicitud no válida. Actualiza la página.',400
        if request.endpoint in ('iniciar_sesion','static'):
            return None
        g.usuario=validar_sesion(session.get('_sid'),ruta())
        if not g.usuario:
            session.clear()
            flash('Ingresa con tu usuario para continuar.','error')
            return redirect(url_for('iniciar_sesion'))

    @app.context_processor
    def variables_comunes():
        if '_csrf' not in session:
            session['_csrf']=secrets.token_hex(24)
        return {'csrf_token':session['_csrf'],'usuario_actual':getattr(g,'usuario',None)}

    @app.after_request
    def proteger_respuestas(resp):
        resp.headers['Cache-Control']='no-store'
        resp.headers['X-Content-Type-Options']='nosniff'
        resp.headers['X-Frame-Options']='DENY'
        return resp

    def solo_admin(func):
        @wraps(func)
        def protegido(*args,**kwargs):
            if not g.usuario or g.usuario['rol']!='administrador':
                abort(403)
            return func(*args,**kwargs)
        return protegido

    @app.route('/login',methods=['GET','POST'])
    def iniciar_sesion():
        if request.method=='POST':
            cuenta=autenticar(request.form.get('usuario'),request.form.get('clave'),ruta())
            if cuenta:
                session.clear()
                session['_sid']=abrir_sesion(cuenta['id'],ruta())
                session['_csrf']=secrets.token_hex(24)
                flash(f"Bienvenido/a, {cuenta['nombre']}.",'exito')
                return redirect(url_for('inicio'))
            flash('Usuario o contraseña incorrectos, o cuenta desactivada.','error')
        return render_template('login.html')

    @app.post('/salir')
    def salir():
        cerrar_sesion(session.get('_sid'),ruta())
        session.clear()
        flash('La sesión se cerró correctamente.','exito')
        return redirect(url_for('iniciar_sesion'))

    @app.get('/')
    def inicio():
        return render_template('inicio.html', datos=resumen(ruta()),
                               estado_celdas=resumen_celdas(ruta()),
                               conectados=operadores_conectados(ruta()) if g.usuario['rol']=='administrador' else [],
                               activa='inicio')

    @app.get('/consultar')
    def consultar():
        placa=request.args.get('placa','').strip()
        resultado=None
        if placa:
            try: resultado=consultar_placa(placa,ruta=ruta())
            except ErrorNegocio as exc: flash(str(exc),'error')
        return render_template('consultar.html',placa=placa,resultado=resultado,activa='consultar')

    @app.route('/vehiculos/nuevo',methods=['GET','POST'])
    def vehiculo_nuevo():
        if request.method=='POST':
            try:
                crear_vehiculo(request.form.get('placa'),request.form.get('tipo'),
                               True,'1900-01-01',
                               g.usuario['id'],ruta())
                flash('El vehículo quedó registrado.','exito')
                return redirect(url_for('consultar',placa=request.form.get('placa','').strip().upper()))
            except ErrorNegocio as ex: flash(str(ex),'error')
        return render_template('vehiculo_nuevo.html',activa='vehiculo')

    @app.route('/vehiculos/<placa>/corregir',methods=['GET','POST'])
    @solo_admin
    def vehiculo_corregir(placa):
        with conectar(ruta()) as bd:
            fila=bd.execute('SELECT * FROM vehiculo WHERE placa=?',(placa.upper(),)).fetchone()
            actual=dict(fila) if fila else None
        if not actual: abort(404)
        if request.method=='POST':
            try:
                corregir_vehiculo(placa,request.form.get('placa'),request.form.get('tipo'),
                                  request.form.get('autorizado')=='1',actual['vigencia_hasta'],
                                  g.usuario['id'],ruta())
                flash('Información corregida y registrada en auditoría.','exito')
                return redirect(url_for('consultar',placa=request.form.get('placa','').strip().upper()))
            except ErrorNegocio as ex: flash(str(ex),'error')
        return render_template('vehiculo_corregir.html',actual=actual,activa='vehiculo')

    @app.post('/vehiculos/<placa>/eliminar')
    @solo_admin
    def vehiculo_eliminar(placa):
        try:
            eliminar_vehiculo(placa,g.usuario['id'],ruta())
            flash('Vehículo eliminado y acción registrada.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('consultar',placa=placa))

    @app.route('/entrada',methods=['GET','POST'])
    def entrada():
        placa=(request.form if request.method=='POST' else request.args).get('placa','').strip().upper()
        if request.method=='POST':
            try:
                celda_id=int(request.form.get('celda_id',''))
                resultado=registrar_entrada(placa,ruta=ruta(),celda_id=celda_id,usuario_id=g.usuario['id'])
                flash(f"Entrada registrada: {resultado['placa']} en {resultado['celda']}.",'exito')
                return redirect(url_for('inicio'))
            except (ErrorNegocio,ValueError) as ex: flash(str(ex) if isinstance(ex,ErrorNegocio) else 'Selecciona una celda.','error')
        resultado=None
        if placa:
            try: resultado=consultar_placa(placa,ruta=ruta())
            except ErrorNegocio: pass
        return render_template('entrada.html',placa=placa,resultado=resultado,
                               celdas=disponibles(ruta()),activa='entrada')

    @app.route('/salida',methods=['GET','POST'])
    def salida():
        placa=(request.form if request.method=='POST' else request.args).get('placa','').strip().upper()
        if request.method=='POST':
            try:
                resultado=registrar_salida(placa,ruta=ruta(),usuario_id=g.usuario['id'])
                flash(f"Salida registrada: {resultado['placa']} a las {resultado['fecha_hora_salida']}.",'exito')
                return redirect(url_for('inicio'))
            except ErrorNegocio as ex: flash(str(ex),'error')
        resultado=None
        if placa:
            try: resultado=consultar_placa(placa,ruta=ruta())
            except ErrorNegocio as ex: flash(str(ex),'error')
        return render_template('salida.html',placa=placa,resultado=resultado,activa='salida')

    @app.route('/novedades',methods=['GET','POST'])
    @solo_admin
    def novedades():
        placa=(request.form if request.method=='POST' else request.args).get('placa','').strip().upper()
        tipo=request.form.get('tipo','Observacion general')
        descripcion=request.form.get('descripcion','')
        if request.method=='POST':
            try:
                registrar_novedad(placa,tipo,descripcion,ruta=ruta(),usuario_id=g.usuario['id'])
                flash(f'Novedad guardada para {placa}.','exito')
                return redirect(url_for('novedades'))
            except ErrorNegocio as ex: flash(str(ex),'error')
        resultado=None
        if placa:
            try: resultado=consultar_placa(placa,ruta=ruta())
            except ErrorNegocio: pass
        return render_template('novedades.html',placa=placa,tipo=tipo,descripcion=descripcion,
                               resultado=resultado,tipos=TIPOS_NOVEDAD,
                               recientes=novedades_recientes(ruta()),activa='novedades')

    @app.get('/historial')
    def ver_historial():
        placa=request.args.get('placa','').strip()
        desde=request.args.get('desde','')
        hasta=request.args.get('hasta','')
        registros=[]
        try: registros=historial(placa,desde,hasta,ruta=ruta())
        except ErrorNegocio as ex: flash(str(ex),'error')
        return render_template('historial.html',registros=registros,placa=placa,
                               desde=desde,hasta=hasta,activa='historial')

    @app.post('/historial/<int:id_>/anular')
    @solo_admin
    def anular(id_):
        try:
            anular_movimiento(id_,g.usuario['id'],ruta())
            flash('Movimiento anulado. Queda constancia en auditoría.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('ver_historial'))

    @app.get('/celdas')
    def celdas():
        return render_template('celdas.html',celdas=listar_celdas(ruta()),
                               totales=resumen_celdas(ruta()),activa='celdas')

    @app.post('/celdas/nueva')
    @solo_admin
    def celda_nueva():
        try:
            crear_celda(request.form.get('codigo'),g.usuario['id'],ruta())
            flash('Celda creada correctamente.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('celdas'))

    @app.post('/celdas/<int:id_>/editar')
    @solo_admin
    def celda_editar(id_):
        try:
            editar_celda(id_,request.form.get('codigo'),request.form.get('activa')=='1',g.usuario['id'],ruta())
            flash('Celda actualizada.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('celdas'))

    @app.post('/celdas/<int:id_>/eliminar')
    @solo_admin
    def celda_eliminar(id_):
        try:
            eliminar_celda(id_,g.usuario['id'],ruta())
            flash('Celda eliminada.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('celdas'))

    @app.get('/usuarios')
    @solo_admin
    def usuarios():
        return render_template('usuarios.html',usuarios=listar_usuarios(ruta()),
                               conectados=operadores_conectados(ruta()),activa='usuarios')

    @app.post('/usuarios/nuevo')
    @solo_admin
    def usuario_nuevo():
        try:
            crear_operador(request.form.get('nombre'),request.form.get('usuario'),
                           request.form.get('clave'),g.usuario['id'],ruta())
            flash('Operador creado.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('usuarios'))

    @app.post('/usuarios/<int:id_>/editar')
    @solo_admin
    def usuario_editar(id_):
        try:
            cambiar_operador(id_,request.form.get('nombre'),request.form.get('clave'),
                             request.form.get('activo')=='1',g.usuario['id'],ruta())
            flash('Cuenta de operador actualizada.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('usuarios'))

    @app.post('/usuarios/<int:id_>/eliminar')
    @solo_admin
    def usuario_eliminar(id_):
        try:
            eliminar_operador(id_,g.usuario['id'],ruta())
            flash('Acceso eliminado; se conserva el historial del empleado.','exito')
        except ErrorNegocio as ex: flash(str(ex),'error')
        return redirect(url_for('usuarios'))

    @app.get('/pagos')
    def pagos():
        placa = request.args.get('placa','').strip()
        try:
            registros = listar_pagos(placa or None, ruta())
        except ErrorNegocio as ex:
            flash(str(ex), 'error')
            registros = []
        return render_template('pagos.html', registros=registros, placa=placa, activa='pagos')

    @app.route('/pagos/nuevo', methods=['GET','POST'])
    def pago_nuevo():
        placa = (request.form if request.method=='POST' else request.args).get('placa','').strip().upper()
        primera_fecha = (request.form if request.method=='POST' else request.args).get('primera_fecha','').strip()
        if request.method=='POST':
            try:
                id_pago = registrar_pago(placa, request.form.get('importe'),
                    request.form.get('medio_pago'),g.usuario['id'],ruta(),
                    primera_fecha=primera_fecha or None,
                    referencia=request.form.get('referencia',''),
                    token_operacion=request.form.get('token_operacion'))
                flash('Mensualidad registrada. Ya puedes descargar el recibo.','exito')
                return redirect(url_for('pago_detalle',id_pago=id_pago))
            except ErrorNegocio as ex:
                flash(str(ex),'error')
        periodo = None
        if placa:
            try:
                periodo = previsualizar_periodo(placa, ruta(), primera_fecha or None)
            except ErrorNegocio as ex:
                flash(str(ex),'error')
        return render_template('pago_nuevo.html', token_operacion=(request.form.get('token_operacion') if request.method=='POST' else secrets.token_urlsafe(24)), placa=placa,
                               periodo=periodo, primera_fecha=primera_fecha,
                               medios=MEDIOS_PAGO, activa='pagos')

    @app.get('/pagos/<int:id_pago>')
    def pago_detalle(id_pago):
        pago = obtener_pago(id_pago,ruta())
        if not pago: abort(404)
        return render_template('pago_detalle.html',pago=pago,activa='pagos')

    @app.get('/pagos/<int:id_pago>/recibo.pdf')
    def pago_recibo(id_pago):
        pago = obtener_pago(id_pago,ruta())
        if not pago: abort(404)
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        buf = BytesIO()
        doc = canvas.Canvas(buf,pagesize=A4)
        w,h = A4
        doc.setFillColor(HexColor('#234e73'))
        doc.rect(0,h-88,w,88,fill=1,stroke=0)
        doc.setFillColorRGB(1,1,1)
        doc.setFont('Helvetica-Bold',19)
        doc.drawString(44,h-44,'AUTOS COLOMBIA')
        doc.setFont('Helvetica',11)
        doc.drawString(44,h-64,'Recibo de mensualidad del parqueadero')
        doc.setFillColor(HexColor('#233047'))
        y=h-137
        lineas=[('Recibo',pago['numero_recibo']),
                ('Placa',pago['placa']),
                ('Valor registrado',f"$ {pago['importe_pesos']:,.0f} COP".replace(',','.')),
                ('Medio de pago',pago['medio_pago'].capitalize()),
                ('Referencia',pago['referencia_pago'] or 'No aplica'),
                ('Fecha y hora de pago',pago['fecha_pago']),
                ('Inicio de mensualidad',pago['inicio_periodo']),
                ('Fin de mensualidad',pago['fin_periodo']),
                ('Registrado por',pago['responsable']),
                ('Estado',pago['estado'])]
        for etiqueta,valor in lineas:
            doc.setFont('Helvetica-Bold',10)
            doc.drawString(45,y,etiqueta+':')
            doc.setFont('Helvetica',10)
            doc.drawString(218,y,str(valor))
            y-=33
        doc.setStrokeColor(HexColor('#d7e0e9'))
        doc.line(45,y-3,w-45,y-3)
        y-=27
        doc.setFont('Helvetica',9)
        doc.drawString(45,y,'La fecha de pago es diferente a la fecha de inicio de la mensualidad.')
        doc.drawString(45,y-18,'Documento generado desde el sistema Autos Colombia.')
        doc.showPage()
        doc.save()
        buf.seek(0)
        return send_file(buf,mimetype='application/pdf',as_attachment=True,
                         download_name=f"Recibo_{pago['numero_recibo']}.pdf")

    @app.post('/pagos/<int:id_pago>/anular')
    @solo_admin
    def pago_anular(id_pago):
        try:
            anular_pago(id_pago,request.form.get('motivo'),g.usuario['id'],ruta())
            flash('Pago anulado. Se conservó el registro en el historial.','exito')
        except ErrorNegocio as ex:
            flash(str(ex),'error')
        return redirect(url_for('pago_detalle',id_pago=id_pago))

    @app.get('/auditoria')
    @solo_admin
    def auditoria():
        return render_template('auditoria.html',registros=ver_auditoria(ruta()),activa='auditoria')

    return app

if __name__=='__main__':
    instancia=crear_app()
    print('Autos Colombia. Abre http://127.0.0.1:5000')
    instancia.run(host='127.0.0.1',port=5000,debug=False,threaded=True)
