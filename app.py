"""
Multiverso API
API Back-End (Flask) do MVP de componentização.

Domínio: "Explorador do Multiverso" — favoritos de personagens de Rick
and Morty. Além do CRUD de favoritos, tem uma rota de regra de negócio
que consulta a Rick and Morty API para trazer os episódios em que o
personagem favoritado apareceu (2 chamadas encadeadas: personagem ->
episódios).
"""
import sqlite3
from datetime import datetime, timezone
from functools import wraps

import requests
from flask import Flask, g, jsonify, request
from flask_cors import CORS

DB_PATH = "multiverso.db"
RICKMORTY_BASE = "https://rickandmortyapi.com/api"
STATUS_VALIDOS = {"Alive", "Dead", "unknown"}
ORDENACOES_VALIDAS = {
    "criado_em": "criado_em DESC",
    "character_name": "character_name ASC",
    "status": "status ASC",
}

# Autenticação simples por chave de API: protege as rotas de escrita
API_KEY = "multiverso-mvp-2026"


def exige_api_key(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        chave_recebida = request.headers.get("X-API-Key", "")
        if chave_recebida != API_KEY:
            return jsonify(erro="chave de API ausente ou inválida"), 401
        return funcao(*args, **kwargs)

    return wrapper


app = Flask(__name__)
CORS(app)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS favoritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            character_name TEXT NOT NULL,
            status TEXT,
            species TEXT,
            image_url TEXT,
            notas TEXT DEFAULT '',
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {
        "id": row["id"],
        "character_id": row["character_id"],
        "character_name": row["character_name"],
        "status": row["status"],
        "species": row["species"],
        "image_url": row["image_url"],
        "notas": row["notas"],
        "criado_em": row["criado_em"],
    }


@app.get("/api/favoritos")
def listar_favoritos():
    """Lista os favoritos, com paginação, filtro por status/espécie e ordenação."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = max(1, min(50, int(request.args.get("per_page", 6))))
    except ValueError:
        return jsonify(erro="page e per_page devem ser números inteiros"), 400

    status = request.args.get("status", "").strip()
    species = request.args.get("species", "").strip()
    sort = request.args.get("sort", "criado_em")
    order_clause = ORDENACOES_VALIDAS.get(sort, ORDENACOES_VALIDAS["criado_em"])

    where = []
    params = []
    if status:
        if status not in STATUS_VALIDOS:
            return jsonify(erro="status inválido"), 400
        where.append("status = ?")
        params.append(status)
    if species:
        where.append("species LIKE ?")
        params.append(f"%{species}%")
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM favoritos {where_clause}", params).fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM favoritos {where_clause} ORDER BY {order_clause} LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()

    return jsonify(total=total, page=page, per_page=per_page, itens=[row_to_dict(r) for r in rows])


@app.get("/api/favoritos/<int:favorito_id>")
def obter_favorito(favorito_id):
    db = get_db()
    row = db.execute("SELECT * FROM favoritos WHERE id = ?", (favorito_id,)).fetchone()
    if row is None:
        return jsonify(erro="favorito não encontrado"), 404
    return jsonify(row_to_dict(row))


@app.post("/api/favoritos")
@exige_api_key
def criar_favorito():
    dados = request.get_json(silent=True) or {}
    character_id = dados.get("character_id")
    character_name = (dados.get("character_name") or "").strip()
    if not character_id or not character_name:
        return jsonify(erro="campos 'character_id' e 'character_name' são obrigatórios"), 400

    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO favoritos (character_id, character_name, status, species, image_url, notas, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            character_id,
            character_name,
            dados.get("status", "unknown"),
            dados.get("species", ""),
            dados.get("image_url", ""),
            dados.get("notas", ""),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    novo = db.execute("SELECT * FROM favoritos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(row_to_dict(novo)), 201


@app.put("/api/favoritos/<int:favorito_id>")
@exige_api_key
def atualizar_favorito(favorito_id):
    dados = request.get_json(silent=True) or {}
    db = get_db()
    existente = db.execute("SELECT * FROM favoritos WHERE id = ?", (favorito_id,)).fetchone()
    if existente is None:
        return jsonify(erro="favorito não encontrado"), 404

    notas = dados.get("notas", existente["notas"])
    db.execute("UPDATE favoritos SET notas = ? WHERE id = ?", (notas, favorito_id))
    db.commit()
    atualizado = db.execute("SELECT * FROM favoritos WHERE id = ?", (favorito_id,)).fetchone()
    return jsonify(row_to_dict(atualizado))


@app.delete("/api/favoritos/<int:favorito_id>")
@exige_api_key
def remover_favorito(favorito_id):
    db = get_db()
    existente = db.execute("SELECT id FROM favoritos WHERE id = ?", (favorito_id,)).fetchone()
    if existente is None:
        return jsonify(erro="favorito não encontrado"), 404
    db.execute("DELETE FROM favoritos WHERE id = ?", (favorito_id,))
    db.commit()
    return "", 204


@app.get("/api/favoritos/<int:favorito_id>/episodios")
def episodios_do_favorito(favorito_id):
    """
    Regra de negócio: dado um favorito salvo, consulta a Rick and Morty
    API para descobrir em quais episódios o personagem apareceu.
    Faz duas chamadas encadeadas na API externa: personagem -> episódios.
    """
    db = get_db()
    favorito = db.execute("SELECT * FROM favoritos WHERE id = ?", (favorito_id,)).fetchone()
    if favorito is None:
        return jsonify(erro="favorito não encontrado"), 404

    try:
        resp_char = requests.get(f"{RICKMORTY_BASE}/character/{favorito['character_id']}", timeout=6)
    except requests.RequestException:
        return jsonify(erro="não foi possível falar com a Rick and Morty API agora"), 502
    if not resp_char.ok:
        return jsonify(erro="personagem não encontrado na Rick and Morty API"), 502

    episode_urls = resp_char.json().get("episode", [])
    if not episode_urls:
        return jsonify(character_id=favorito["character_id"], episodios=[])

    ids = ",".join(url.rstrip("/").rsplit("/", 1)[-1] for url in episode_urls)
    try:
        resp_eps = requests.get(f"{RICKMORTY_BASE}/episode/{ids}", timeout=6)
    except requests.RequestException:
        return jsonify(erro="não foi possível buscar os episódios agora"), 502
    if not resp_eps.ok:
        return jsonify(erro="falha ao buscar episódios"), 502

    dados_eps = resp_eps.json()
    if isinstance(dados_eps, dict):
        dados_eps = [dados_eps]

    episodios = [
        {"nome": ep.get("name"), "codigo": ep.get("episode"), "data_exibicao": ep.get("air_date")}
        for ep in dados_eps
    ]
    return jsonify(character_id=favorito["character_id"], episodios=episodios)


@app.get("/api/favoritos/estatisticas")
def estatisticas_favoritos():
    """Conta os favoritos agrupados por status, para o gráfico da interface."""
    db = get_db()
    linhas = db.execute(
        "SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS total FROM favoritos GROUP BY status"
    ).fetchall()
    contagem = {"Alive": 0, "Dead": 0, "unknown": 0}
    for linha in linhas:
        contagem[linha["status"] if linha["status"] in contagem else "unknown"] += linha["total"]
    return jsonify(total=sum(contagem.values()), por_status=contagem)


@app.get("/api/health")
def health():
    return jsonify(status="ok")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
