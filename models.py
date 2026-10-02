from db import db
from datetime import datetime

class Utilizador(db.Model):
    __tablename__ = "utilizadores"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    anuncios = db.relationship("Anuncio", backref="dono", lazy=True)


class Anuncio(db.Model):
    __tablename__ = "anuncios"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.String(20), nullable=False)
    local = db.Column(db.String(120), nullable=False)
    data_ocorrencia = db.Column(db.Date, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    imagem = db.Column(db.String(255))
    dono_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    conversas = db.relationship("Conversa", backref="anuncio", lazy=True)


class Conversa(db.Model):
    __tablename__ = "conversas"

    id = db.Column(db.Integer, primary_key=True)
    anuncio_id = db.Column(db.Integer, db.ForeignKey("anuncios.id"))
    dono_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"))
    utilizador_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"))
    dono = db.relationship("Utilizador", foreign_keys=[dono_id])
    utilizador = db.relationship("Utilizador", foreign_keys=[utilizador_id])
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    mensagens = db.relationship("Mensagem", backref="conversa", lazy=True)


class Mensagem(db.Model):
    __tablename__ = "mensagens"

    id = db.Column(db.Integer, primary_key=True)
    conversa_id = db.Column(db.Integer, db.ForeignKey("conversas.id"))
    autor_id = db.Column(db.Integer, db.ForeignKey("utilizadores.id"), nullable=False)
    autor = db.relationship("Utilizador", backref="mensagens_autor")
    texto = db.Column(db.Text)
    imagem = db.Column(db.String(255))
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)