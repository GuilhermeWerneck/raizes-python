import uuid
from datetime import datetime, timezone

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.routes import pedido_routes
from src.infrastructure.database.database import engine, Base, get_db
from src.infrastructure.database import models
from src.infrastructure.database.seed import seed_database
from src.application.services.services import (
    autenticar_usuario, decodificar_token,
    entrada_estoque, resgatar_pontos
)

Base.metadata.create_all(bind=engine)
seed_database()

SECRET_KEY = "raizes_nordeste_guilherme_werneck_4310215"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class LoginSchema(BaseModel):
    username: str
    password: str


app = FastAPI(
    title="Raízes do Nordeste - API",
    description=(
        "Sistema de gestão multicanal com pagamento Mock, SQLite e JWT.\n\n"
        "**Aluno:** Guilherme Werneck | **RU:** 4310215 | UNINTER 2026\n\n"
        "**Credenciais:** `admin@raizes.com` / `password` · login rápido: `admin` / `admin`"
    ),
    version="1.2.0"
)


# ─── Middleware ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    return response


# ─── Handlers de erro padronizados ────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    detalhes = []
    for erro in exc.errors():
        campo = erro["loc"][-1] if erro["loc"] else "desconhecido"
        detalhes.append({"field": str(campo), "issue": erro["msg"]})
    return JSONResponse(status_code=422, content={
        "error": "UNPROCESSABLE_ENTITY",
        "message": "Erro de validação nos dados enviados.",
        "details": detalhes,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": request.url.path,
        "requestId": getattr(request.state, "request_id", "N/A")
    })


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={
        "error": f"ERROR_{exc.status_code}",
        "message": exc.detail,
        "details": [],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": request.url.path,
        "requestId": getattr(request.state, "request_id", "N/A")
    })


# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)):
    return decodificar_token(token)


@app.post("/token", tags=["Segurança"], include_in_schema=False)
async def login_token(form_data: OAuth2PasswordRequestForm = Depends(),
                      db: Session = Depends(get_db)):
    return autenticar_usuario(db, form_data.username, form_data.password)


@app.post("/auth/login", tags=["Segurança"], summary="Autenticação de Usuário")
async def login_rota(dados: LoginSchema, db: Session = Depends(get_db)):
    """Retorna token JWT. Login rápido: `admin` / `admin`"""
    return autenticar_usuario(db, dados.username, dados.password)


# ─── Pedidos (protegidos) ─────────────────────────────────────────────────────

app.include_router(pedido_routes.router, prefix="/pedidos",
                   dependencies=[Depends(get_current_user)])


# ─── Rotas públicas ───────────────────────────────────────────────────────────

@app.get("/", tags=["Home"])
def home():
    return {"mensagem": "API Raízes do Nordeste ativa!", "aluno": "Guilherme Werneck",
            "ru": "4310215", "docs": "/docs"}


@app.get("/produtos", tags=["Produtos"], summary="Listar produtos do cardápio")
def listar_produtos(db: Session = Depends(get_db)):
    produtos = db.query(models.Produto).filter(models.Produto.ativo == True).all()
    return [{"id": p.id, "nome": p.nome, "descricao": p.descricao, "preco": p.preco,
             "categoria": p.categoria.nome if p.categoria else None} for p in produtos]


@app.get("/produtos/{produto_id}", tags=["Produtos"], summary="Buscar produto por ID")
def buscar_produto(produto_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return {"id": p.id, "nome": p.nome, "descricao": p.descricao, "preco": p.preco,
            "categoria": p.categoria.nome if p.categoria else None}


@app.get("/unidades", tags=["Unidades"], summary="Listar unidades da rede")
def listar_unidades(db: Session = Depends(get_db)):
    return [{"id": u.id, "nome": u.nome, "cidade": u.cidade, "estado": u.estado}
            for u in db.query(models.Unidade).filter(models.Unidade.ativo == True).all()]


# ─── Estoque ──────────────────────────────────────────────────────────────────

@app.get("/estoque/{unidade_id}", tags=["Estoque"], summary="Consultar estoque por unidade")
def consultar_estoque(unidade_id: int, db: Session = Depends(get_db)):
    unidade = db.query(models.Unidade).filter(models.Unidade.id == unidade_id).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")
    itens = db.query(models.Estoque).filter(models.Estoque.unidade_id == unidade_id).all()
    return {
        "unidade_id": unidade_id,
        "nome_unidade": unidade.nome,
        "itens": [{"produto_id": i.produto_id, "nome_produto": i.produto.nome,
                   "quantidade": i.quantidade} for i in itens]
    }


class EntradaEstoqueSchema(BaseModel):
    unidade_id: int
    produto_id: int
    quantidade: int = Field(gt=0, description="Quantidade a adicionar")
    motivo: str = Field(default="Reposição")


@app.post("/estoque/entrada", tags=["Estoque"],
          summary="Entrada de estoque — reposição (ADMIN/GERENTE)")
def entrada_estoque_route(
    dados: EntradaEstoqueSchema,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Registra entrada de produtos no estoque. Perfis: ADMIN, GERENTE."""
    est = entrada_estoque(db, dados.model_dump(), current_user)
    return {
        "unidade_id": est.unidade_id,
        "produto_id": est.produto_id,
        "nome_produto": est.produto.nome,
        "quantidade_atual": est.quantidade,
        "mensagem": f"Entrada de {dados.quantidade} unidade(s) registrada com sucesso."
    }


# ─── Fidelidade ───────────────────────────────────────────────────────────────

@app.get("/fidelidade/{usuario_id}", tags=["Fidelidade"],
         summary="Consultar saldo de pontos")
def consultar_fidelidade(usuario_id: int, db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user)):
    fid = db.query(models.Fidelidade).filter(models.Fidelidade.usuario_id == usuario_id).first()
    if not fid:
        raise HTTPException(status_code=404, detail="Conta de fidelidade não encontrada")

    historico = db.query(models.HistoricoFidelidade)\
        .filter(models.HistoricoFidelidade.usuario_id == usuario_id)\
        .order_by(models.HistoricoFidelidade.id.desc()).limit(10).all()

    return {
        "usuario_id": usuario_id,
        "pontos_saldo": fid.pontos_saldo,
        "pontos_acumulados": fid.pontos_acumulados,
        "historico_recente": [
            {"tipo": h.tipo, "pontos": h.pontos, "descricao": h.descricao,
             "criado_em": h.criado_em.isoformat() if h.criado_em else None}
            for h in historico
        ]
    }


class ResgateSchema(BaseModel):
    pontos: int = Field(gt=0, description="Quantidade de pontos a resgatar")


@app.post("/fidelidade/{usuario_id}/resgatar", tags=["Fidelidade"],
          summary="Resgatar pontos de fidelidade")
def resgatar_pontos_route(
    usuario_id: int,
    dados: ResgateSchema,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Resgata pontos do saldo do cliente. Retorna 409 se pontos insuficientes."""
    fid = resgatar_pontos(db, usuario_id, dados.pontos, current_user)
    return {
        "usuario_id": usuario_id,
        "pontos_resgatados": dados.pontos,
        "pontos_saldo_restante": fid.pontos_saldo,
        "mensagem": f"{dados.pontos} ponto(s) resgatado(s) com sucesso."
    }
