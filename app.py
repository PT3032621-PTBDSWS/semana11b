import os
import sys
from threading import Thread
from flask import Flask, render_template, session, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
import requests
from datetime import datetime

# ----------------------------------------------
# Configurações básicas do Flask
# ----------------------------------------------
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hard to guess string'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Variáveis de ambiente (Mailgun / SendGrid)
app.config['API_KEY'] = os.environ.get('API_KEY')
app.config['API_URL'] = os.environ.get('API_URL')
app.config['API_FROM'] = os.environ.get('API_FROM')
app.config['FLASKY_MAIL_SUBJECT_PREFIX'] = '[Flasky]'
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')

# Inicialização de extensões
bootstrap = Bootstrap(app)
moment = Moment(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# ----------------------------------------------
# Modelos de banco
# ----------------------------------------------
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return '<Role %r>' % self.name


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    def __repr__(self):
        return '<User %r>' % self.username


class Email(db.Model):
    __tablename__ = 'emails'
    id = db.Column(db.Integer, primary_key=True)
    remetente = db.Column(db.String(120))
    destinatario = db.Column(db.String(200))
    assunto = db.Column(db.String(200))
    texto = db.Column(db.Text)
    data_hora = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Email {self.assunto}>'

# ----------------------------------------------
# Função de envio de e-mail (Mailgun)
# ----------------------------------------------
def send_simple_message(to, subject, newUser):
    print('Enviando mensagem (POST)...', flush=True)
    print('URL: ' + str(app.config['API_URL']), flush=True)
    print('api: ' + str(app.config['API_KEY']), flush=True)
    print('from: ' + str(app.config['API_FROM']), flush=True)
    print('to: ' + str(to), flush=True)
    print('subject: ' + str(app.config['FLASKY_MAIL_SUBJECT_PREFIX']) + ' ' + subject, flush=True)

    texto_email = (
        f"Prontuário: PT3032621\n"
        f"Nome: Gustavo Maximo Da Silva\n"
        f"Novo usuário cadastrado: {newUser}"
    )

    resposta = requests.post(
        app.config['API_URL'],
        auth=("api", app.config['API_KEY']),
        data={
            "from": app.config['API_FROM'],
            "to": to,
            "subject": app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
            "text": texto_email
        }
    )

    print('Enviando mensagem (Resposta)...' + str(resposta) + ' - ' + datetime.now().strftime("%d/%m/%Y, %H:%M:%S"), flush=True)

    # --- Persistir no banco ---
    try:
        novo_email = Email(
            remetente=app.config['API_FROM'],
            destinatario=str(to),
            assunto=subject,
            texto=texto_email,
            data_hora=datetime.now()
        )
        db.session.add(novo_email)
        db.session.commit()
        print("✅ E-mail salvo no banco com sucesso.", flush=True)
    except Exception as e:
        print("❌ Erro ao salvar e-mail no banco:", e, flush=True)

    return resposta

# ----------------------------------------------
# Formulário da página inicial
# ----------------------------------------------
class NameForm(FlaskForm):
    name = StringField('Qual é o seu nome?', validators=[DataRequired()])
    email = BooleanField('Deseja enviar e-mail para flaskaulasweb@zohomail.com?')
    submit = SubmitField('Enviar')

# ----------------------------------------------
# Contexto do shell
# ----------------------------------------------
@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Role=Role, Email=Email)

# ----------------------------------------------
# Rota principal
# ----------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    form = NameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()
        if user is None:
            user = User(username=form.name.data)
            db.session.add(user)
            db.session.commit()
            session['known'] = False

            if app.config['FLASKY_ADMIN']:
                print('Enviando mensagem...', flush=True)
                destinatarios = [app.config['FLASKY_ADMIN']]
                if form.email.data:
                    destinatarios.append("flaskaulasweb@zohomail.com")

                send_simple_message(destinatarios, 'Novo usuário', form.name.data)
                print('Mensagem enviada...', flush=True)
        else:
            session['known'] = True

        session['name'] = form.name.data
        return redirect(url_for('index'))

    users_list = User.query.order_by(User.username).all()
    return render_template('index.html', form=form, name=session.get('name'),
                           known=session.get('known', False), users=users_list)

# ----------------------------------------------
# Rota para listagem de e-mails enviados
# ----------------------------------------------
@app.route('/emailsEnviados')
def emails_enviados():
    emails = Email.query.order_by(Email.data_hora.desc()).all()
    return render_template('emails_enviados.html', emails=emails)
