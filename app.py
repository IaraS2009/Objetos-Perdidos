import os, re, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session as flask_session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from db import db
from models import Utilizador, Anuncio, Conversa, Mensagem

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///refind.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "imagens")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
db.init_app(app)


PASSWORD_MIN_LENGTH = 8
def password_is_valid(password):
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, "A palavra-passe deve ter pelo menos 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return False, "A palavra-passe deve conter uma letra maiúscula."
    if not re.search(r"[a-z]", password):
        return False, "A palavra-passe deve conter uma letra minúscula."
    if not re.search(r"[0-9]", password):
        return False, "A palavra-passe deve conter um número."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "A palavra-passe deve conter um símbolo."
    return True, ""


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def utilizador_atual():
    utilizador_id = flask_session.get("utilizador_id")
    if utilizador_id is None:
        return None
    return db.session.query(Utilizador).filter_by(id=utilizador_id, ativo=True).first()


@app.context_processor
def inserir_utilizador_atual():
    return {"utilizador_atual": utilizador_atual()}


def login_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if flask_session.get("utilizador_id") is None:
            flash("Inicia sessão para continuar.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return decorated


@app.route("/")
def home():
    pesquisa = request.args.get("q", "").strip()
    query = db.session.query(Anuncio)
    if pesquisa:
        termo = f"%{pesquisa}%"
        query = query.filter(
            or_(
                Anuncio.titulo.ilike(termo),
                Anuncio.descricao.ilike(termo),
                Anuncio.local.ilike(termo),
                Anuncio.tipo.ilike(termo),
                Anuncio.estado.ilike(termo)
            )
        )
    anuncios = query.order_by(Anuncio.data_criacao.desc()).all()
    return render_template("home.html", anuncios=anuncios, pesquisa=pesquisa)


@app.route("/registar", methods=["GET", "POST"])
def registar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar_password", "")

        if not nome or not email or not password:
            flash("Preenche todos os campos obrigatórios.", "danger")
            return render_template("registar.html")

        if password != confirmar:
            flash("As palavras-passe não coincidem.", "danger")
            return render_template("registar.html")

        valido, msg = password_is_valid(password)
        if not valido:
            flash(msg, "danger")
            return render_template("registar.html")

        if db.session.query(Utilizador).filter_by(email=email).first():
            flash("Já existe uma conta com esse email.", "danger")
            return render_template("registar.html")

        novo = Utilizador(nome=nome, email=email, password_hash=generate_password_hash(password))
        db.session.add(novo)
        db.session.commit()
        flash("Conta criada com sucesso!", "success")
        return redirect(url_for("login"))
    return render_template("registar.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        utilizador = db.session.query(Utilizador).filter_by(email=email, ativo=True).first()
        if utilizador and check_password_hash(utilizador.password_hash, password):
            flask_session.clear()
            flask_session["utilizador_id"] = utilizador.id
            flash("Sessão iniciada com sucesso.", "success")
            return redirect(url_for("home"))
        flash("Email ou palavra-passe incorretos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    flask_session.clear()
    flash("Sessão terminada.", "success")
    return redirect(url_for("home"))


@app.route("/anuncio/<int:anuncio_id>")
def anuncio(anuncio_id):
    anuncio_obj = db.session.query(Anuncio).filter_by(id=anuncio_id).first()
    if anuncio_obj is None:
        flash("Anúncio não encontrado.", "danger")
        return redirect(url_for("home"))
    return render_template("anuncio.html", anuncio=anuncio_obj)


@app.route("/anuncio/criar", methods=["GET", "POST"])
@login_required
def criar_anuncio():
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        tipo = request.form.get("tipo", "").strip().lower()
        local = request.form.get("local", "").strip()
        data_texto = request.form.get("data_ocorrencia", "").strip()
        imagem_file = request.files.get("imagem")
        utilizador_id = flask_session["utilizador_id"]

        if tipo not in {"perdido", "encontrado"}:
            flash("Seleciona um tipo válido.", "danger")
            return render_template("criar_anuncio.html")
        if not titulo or not local or not data_texto:
            flash("Preenche todos os campos obrigatórios.", "danger")
            return render_template("criar_anuncio.html")
        try:
            data_ocorrencia = datetime.strptime(data_texto, "%Y-%m-%d")
        except ValueError:
            flash("Data inválida.", "danger")
            return render_template("criar_anuncio.html")

        nome_imagem = None
        if imagem_file and imagem_file.filename:
            if not allowed_file(imagem_file.filename):
                flash("Formato de imagem não permitido.", "danger")
                return render_template("criar_anuncio.html")
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            nome_seguro = secure_filename(imagem_file.filename)
            nome_imagem = f"{secrets.token_hex(8)}_{nome_seguro}"
            imagem_file.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_imagem))

        novo = Anuncio(
            titulo=titulo,
            descricao=descricao,
            tipo=tipo,
            local=local,
            data_ocorrencia=data_ocorrencia,
            imagem=nome_imagem,
            estado="perdido" if tipo == "perdido" else "encontrado",
            dono_id=utilizador_id
        )

        db.session.add(novo)
        db.session.commit()
        flash("Anúncio criado com sucesso.", "success")
        return redirect(url_for("anuncio", anuncio_id=novo.id))
    return render_template("criar_anuncio.html")


@app.route("/anuncio/<int:anuncio_id>/editar", methods=["GET", "POST"])
@login_required
def editar_anuncio(anuncio_id):
    anuncio_obj = db.session.query(Anuncio).filter_by(id=anuncio_id).first()
    utilizador_id = flask_session["utilizador_id"]

    if anuncio_obj is None:
        flash("Anúncio não encontrado.", "danger")
        return redirect(url_for("home"))
    if anuncio_obj.dono_id != utilizador_id:
        flash("Não tens autorização.", "danger")
        return redirect(url_for("anuncio", anuncio_id=anuncio_id))
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        tipo = request.form.get("tipo", "").strip().lower()
        local = request.form.get("local", "").strip()
        data_texto = request.form.get("data_ocorrencia", "").strip()
        estado = request.form.get("estado", "").strip().lower()
        imagem_file = request.files.get("imagem")
        if tipo not in {"perdido", "encontrado"} or estado not in {"perdido", "encontrado", "em_andamento", "resolvido"}:
            flash("Opções inválidas.", "danger")
            return render_template("editar_anuncio.html", anuncio=anuncio_obj)
        if not titulo or not local or not data_texto:
            flash("Preenche todos os campos obrigatórios.", "danger")
            return render_template("editar_anuncio.html", anuncio=anuncio_obj)
        try:
            anuncio_obj.data_ocorrencia = datetime.strptime(data_texto, "%Y-%m-%d")
        except ValueError:
            flash("Data inválida.", "danger")
            return render_template("editar_anuncio.html", anuncio=anuncio_obj)

        anuncio_obj.titulo = titulo
        anuncio_obj.descricao = descricao
        anuncio_obj.tipo = tipo
        anuncio_obj.local = local
        anuncio_obj.estado = estado

        if imagem_file and imagem_file.filename:
            if not allowed_file(imagem_file.filename):
                flash("Formato de imagem não permitido.", "danger")
                return render_template("editar_anuncio.html", anuncio=anuncio_obj)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            nome_seguro = secure_filename(imagem_file.filename)
            nome_imagem = f"{secrets.token_hex(8)}_{nome_seguro}"
            imagem_file.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_imagem))
            anuncio_obj.imagem = nome_imagem
        db.session.commit()
        flash("Anúncio atualizado com sucesso.", "success")
        return redirect(url_for("anuncio", anuncio_id=anuncio_id))
    return render_template("editar_anuncio.html", anuncio=anuncio_obj)


@app.route("/anuncio/<int:anuncio_id>/eliminar", methods=["POST"])
@login_required
def eliminar_anuncio(anuncio_id):
    anuncio = db.session.query(Anuncio).filter_by(id=anuncio_id).first()
    utilizador_id = flask_session["utilizador_id"]
    if anuncio is None:
        flash("Anúncio não encontrado.", "danger")
        return redirect(url_for("home"))
    if anuncio.dono_id != utilizador_id:
        flash("Não tens autorização.", "danger")
        return redirect(url_for("anuncio", anuncio_id=anuncio_id))
    if anuncio.imagem:
        caminho = os.path.join(app.config["UPLOAD_FOLDER"], anuncio.imagem)
        if os.path.exists(caminho):
            os.remove(caminho)
    db.session.delete(anuncio)
    db.session.commit()
    flash("Anúncio eliminado com sucesso.", "success")
    return redirect(url_for("home"))


@app.route("/anuncio/<int:anuncio_id>/contactar", methods=["GET", "POST"])
@login_required
def contactar_dono(anuncio_id):
    anuncio_obj = db.session.query(Anuncio).filter_by(id=anuncio_id).first()

    if anuncio_obj is None:
        flash("Anúncio não encontrado.", "danger")
        return redirect(url_for("home"))

    utilizador_id = flask_session["utilizador_id"]
    if anuncio_obj.dono_id == utilizador_id:
        return redirect(url_for("mensagens", anuncio_id=anuncio_id))

    conversa = db.session.query(Conversa).filter_by(
        anuncio_id=anuncio_id,
        utilizador_id=utilizador_id
    ).first()
    if conversa is None:
        conversa = Conversa(
            anuncio_id=anuncio_id,
            dono_id=anuncio_obj.dono_id,
            utilizador_id=utilizador_id
        )
        db.session.add(conversa)
        db.session.commit()

    if request.method == "POST":
        texto = request.form.get("texto", "").strip()
        imagem_file = request.files.get("imagem")
        if not texto and not (imagem_file and imagem_file.filename):
            flash("Escreve uma mensagem ou anexa uma imagem.", "danger")
            return redirect(url_for("contactar_dono", anuncio_id=anuncio_id))
        nome_imagem = None
        if imagem_file and imagem_file.filename:
            if not allowed_file(imagem_file.filename):
                flash("Formato de imagem não permitido.", "danger")
                return redirect(url_for("contactar_dono", anuncio_id=anuncio_id))
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            nome_seguro = secure_filename(imagem_file.filename)
            nome_imagem = f"{secrets.token_hex(8)}_{nome_seguro}"
            imagem_file.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_imagem))

        mensagem = Mensagem(
            conversa_id=conversa.id,
            autor_id=utilizador_id,
            texto=texto or None,
            imagem=nome_imagem
        )
        db.session.add(mensagem)
        db.session.commit()
        return redirect(url_for("chat", conversa_id=conversa.id))
    return render_template("chat.html", conversa=conversa, anuncio=anuncio_obj)


@app.route("/mensagens")
@login_required
def mensagens():
    utilizador_id = flask_session["utilizador_id"]
    conversas = db.session.query(Conversa).filter(
        or_(
            Conversa.dono_id == utilizador_id,
            Conversa.utilizador_id == utilizador_id
        )
    ).order_by(Conversa.data_criacao.desc()).all()
    return render_template("mensagens.html", conversas=conversas)


@app.route("/chat/<int:conversa_id>", methods=["GET", "POST"])
@login_required
def chat(conversa_id):
    utilizador_id = flask_session["utilizador_id"]
    conversa = db.session.query(Conversa).filter(
        Conversa.id == conversa_id,
        or_(Conversa.dono_id == utilizador_id,
            Conversa.utilizador_id == utilizador_id)
    ).first()

    if conversa is None:
        flash("Não tens autorização para aceder a esta conversa.", "danger")
        return redirect(url_for("home"))
    if request.method == "POST":
        texto = request.form.get("texto", "").strip()
        imagem_file = request.files.get("imagem")
        if not texto and not (imagem_file and imagem_file.filename):
            flash("Escreve uma mensagem ou anexa uma imagem.", "danger")
            return redirect(url_for("chat", conversa_id=conversa_id))
        nome_imagem = None
        if imagem_file and imagem_file.filename:
            if not allowed_file(imagem_file.filename):
                flash("Formato de imagem não permitido.", "danger")
                return redirect(url_for("chat", conversa_id=conversa_id))
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            nome_seguro = secure_filename(imagem_file.filename)
            nome_imagem = f"{secrets.token_hex(8)}_{nome_seguro}"
            imagem_file.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_imagem))

        nova_mensagem = Mensagem(
            conversa_id=conversa.id,
            autor_id=utilizador_id,
            texto=texto or None,
            imagem=nome_imagem
        )
        db.session.add(nova_mensagem)
        db.session.commit()
        return redirect(url_for("chat", conversa_id=conversa_id))

    mensagens_lista = db.session.query(Mensagem).filter_by(
        conversa_id=conversa_id
    ).order_by(Mensagem.data_envio.asc()).all()

    return render_template(
        "chat.html",
        conversa=conversa,
        anuncio=conversa.anuncio,
        mensagens=mensagens_lista
    )


@app.route("/perfil")
@login_required
def perfil():
    utilizador = db.session.query(Utilizador).filter_by(
        id=flask_session["utilizador_id"]
    ).first()
    anuncios = db.session.query(Anuncio).filter_by(
        dono_id=utilizador.id
    ).order_by(Anuncio.data_criacao.desc()).all()
    return render_template("perfil.html", utilizador=utilizador, anuncios=anuncios)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(debug=True)