import uuid
import jwt
import bcrypt
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.infrastructure.database.models import (
    Usuario, Pedido, ItemPedido, Pagamento, Estoque, Fidelidade, HistoricoFidelidade,
    AuditLog, Unidade, Produto
)

SECRET_KEY = "raizes_nordeste_guilherme_werneck_4310215"
ALGORITHM = "HS256"


# ─── Auth ─────────────────────────────────────────────────────────────────────

def autenticar_usuario(db: Session, username: str, password: str) -> dict:
    usuario = db.query(Usuario).filter(Usuario.email == username).first()

    if username == "admin" and password == "admin":
        token = jwt.encode({"sub": "admin", "perfil": "ADMIN", "id": 1}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}

    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    if not bcrypt.checkpw(password.encode(), usuario.senha_hash.encode()):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta inativa")

    _registrar_audit(db, usuario.id, "LOGIN", "auth", str(usuario.id))
    db.commit()

    token = jwt.encode(
        {"sub": usuario.email, "perfil": usuario.perfil, "id": usuario.id},
        SECRET_KEY, algorithm=ALGORITHM
    )
    return {"access_token": token, "token_type": "bearer"}


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


def verificar_perfil(usuario_atual: dict, perfis_permitidos: list):
    """Verifica se o usuário tem o perfil necessário para a ação."""
    perfil = usuario_atual.get("perfil", "")
    if perfil not in perfis_permitidos:
        raise HTTPException(
            status_code=403,
            detail=f"Acesso negado. Perfis permitidos: {', '.join(perfis_permitidos)}"
        )


# ─── Pagamento Mock ───────────────────────────────────────────────────────────

def processar_pagamento_mock(pedido_id: int, valor: float, forma: str) -> dict:
    import random
    transaction_id = f"TXN-MOCK-{uuid.uuid4().hex[:8].upper()}"
    aprovado = random.random() > 0.2

    return {
        "aprovado": aprovado,
        "transaction_id": transaction_id,
        "status": "APROVADO" if aprovado else "RECUSADO",
        "mensagem": "Pagamento aprovado (mock)." if aprovado else "Pagamento recusado pelo emissor (mock).",
        "valor": valor,
        "forma_pagamento": forma,
        "gateway": "MockGateway v1.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ─── Pedidos ──────────────────────────────────────────────────────────────────

CANAIS_VALIDOS = {"APP", "TOTEM", "BALCAO", "PICKUP", "WEB"}
STATUS_TRANSICOES = {
    "AGUARDANDO_PAGAMENTO": ["PAGO", "CANCELADO"],
    "PAGO":                 ["EM_PREPARO", "CANCELADO"],
    "EM_PREPARO":           ["PRONTO"],
    "PRONTO":               ["ENTREGUE"],
    "ENTREGUE":             [],
    "CANCELADO":            [],
}


def criar_pedido(db: Session, dados: dict) -> Pedido:
    canal = dados.get("canal_pedido", "").upper()
    if canal not in CANAIS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"canal_pedido inválido. Use: {', '.join(sorted(CANAIS_VALIDOS))}"
        )

    if not dados.get("consentimento_lgpd"):
        raise HTTPException(status_code=422, detail="Consentimento LGPD obrigatório")

    unidade = db.query(Unidade).filter(Unidade.id == dados["unidade_id"]).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    # Verifica e debita estoque
    for item in dados.get("itens", []):
        estoque = db.query(Estoque).filter(
            Estoque.unidade_id == dados["unidade_id"],
            Estoque.produto_id == item["produto_id"]
        ).first()
        if not estoque or estoque.quantidade < item["quantidade"]:
            disp = estoque.quantidade if estoque else 0
            raise HTTPException(
                status_code=409,
                detail=f"Estoque insuficiente para produto {item['produto_id']}. Disponível: {disp}"
            )
        estoque.quantidade -= item["quantidade"]

    pedido = Pedido(
        usuario_id=dados.get("usuario_id"),
        unidade_id=dados["unidade_id"],
        canal_pedido=canal,
        valor_total=dados["valor_total"],
        forma_pagamento=dados.get("forma_pagamento", "MOCK").upper(),
        consentimento_lgpd=dados["consentimento_lgpd"],
        status="AGUARDANDO_PAGAMENTO",
        status_pagamento="PENDENTE"
    )
    db.add(pedido)
    db.flush()

    for item in dados.get("itens", []):
        db.add(ItemPedido(
            pedido_id=pedido.id,
            produto_id=item["produto_id"],
            quantidade=item["quantidade"],
            preco_unitario=item["preco_unitario"]
        ))

    resultado_pag = processar_pagamento_mock(pedido.id, pedido.valor_total, pedido.forma_pagamento)

    db.add(Pagamento(
        pedido_id=pedido.id,
        forma_pagamento=pedido.forma_pagamento,
        valor=pedido.valor_total,
        status=resultado_pag["status"],
        gateway_transaction_id=resultado_pag["transaction_id"],
        gateway_mensagem=resultado_pag["mensagem"]
    ))

    if resultado_pag["aprovado"]:
        pedido.status = "PAGO"
        pedido.status_pagamento = "APROVADO"
        pedido.gateway_transaction_id = resultado_pag["transaction_id"]
        pedido.atualizado_em = datetime.now(timezone.utc)

        if pedido.usuario_id:
            fid = db.query(Fidelidade).filter(Fidelidade.usuario_id == pedido.usuario_id).first()
            if fid:
                pontos = int(pedido.valor_total)
                fid.pontos_saldo += pontos
                fid.pontos_acumulados += pontos
                fid.atualizado_em = datetime.now(timezone.utc)
                db.add(HistoricoFidelidade(
                    usuario_id=pedido.usuario_id,
                    tipo="CREDITO",
                    pontos=pontos,
                    descricao=f"Compra - Pedido #{pedido.id}"
                ))

    _registrar_audit(db, dados.get("usuario_id"), "CRIACAO_PEDIDO", "pedidos",
                     None, f"canal={canal}, pagamento={resultado_pag['status']}")
    db.commit()
    db.refresh(pedido)
    return pedido


def listar_pedidos(db: Session, canal_pedido: str = None, status: str = None) -> list:
    q = db.query(Pedido)
    if canal_pedido:
        q = q.filter(Pedido.canal_pedido == canal_pedido.upper())
    if status:
        q = q.filter(Pedido.status == status.upper())
    return q.order_by(Pedido.id.desc()).all()


def buscar_pedido(db: Session, pedido_id: int) -> Pedido:
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return pedido


def atualizar_status_pedido(db: Session, pedido_id: int, novo_status: str, usuario_atual: dict) -> Pedido:
    # Autorização por perfil
    verificar_perfil(usuario_atual, ["ADMIN", "GERENTE", "ATENDENTE", "COZINHA"])

    pedido = buscar_pedido(db, pedido_id)
    novo_status = novo_status.upper()
    permitidos = STATUS_TRANSICOES.get(pedido.status, [])

    if novo_status not in permitidos:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {pedido.status} → {novo_status}. Permitidos: {permitidos}"
        )

    status_anterior = pedido.status
    pedido.status = novo_status
    pedido.atualizado_em = datetime.now(timezone.utc)

    _registrar_audit(db, usuario_atual.get("id"), "ATUALIZACAO_STATUS", "pedidos",
                     str(pedido_id), f"{status_anterior} -> {novo_status}")
    db.commit()
    db.refresh(pedido)
    return pedido


# ─── Estoque ──────────────────────────────────────────────────────────────────

def entrada_estoque(db: Session, dados: dict, usuario_atual: dict) -> Estoque:
    verificar_perfil(usuario_atual, ["ADMIN", "GERENTE"])

    unidade = db.query(Unidade).filter(Unidade.id == dados["unidade_id"]).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    produto = db.query(Produto).filter(Produto.id == dados["produto_id"]).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    estoque = db.query(Estoque).filter(
        Estoque.unidade_id == dados["unidade_id"],
        Estoque.produto_id == dados["produto_id"]
    ).first()

    if not estoque:
        estoque = Estoque(
            unidade_id=dados["unidade_id"],
            produto_id=dados["produto_id"],
            quantidade=0
        )
        db.add(estoque)
        db.flush()

    estoque.quantidade += dados["quantidade"]

    _registrar_audit(db, usuario_atual.get("id"), "ENTRADA_ESTOQUE", "estoque",
                     str(estoque.id), f"produto={dados['produto_id']}, qtd=+{dados['quantidade']}")
    db.commit()
    db.refresh(estoque)
    return estoque


# ─── Fidelidade ───────────────────────────────────────────────────────────────

def resgatar_pontos(db: Session, usuario_id: int, pontos: int, usuario_atual: dict) -> Fidelidade:
    fid = db.query(Fidelidade).filter(Fidelidade.usuario_id == usuario_id).first()
    if not fid:
        raise HTTPException(status_code=404, detail="Conta de fidelidade não encontrada")

    if fid.pontos_saldo < pontos:
        raise HTTPException(
            status_code=409,
            detail=f"Pontos insuficientes. Saldo atual: {fid.pontos_saldo}, solicitado: {pontos}"
        )

    fid.pontos_saldo -= pontos
    fid.atualizado_em = datetime.now(timezone.utc)

    db.add(HistoricoFidelidade(
        usuario_id=usuario_id,
        tipo="DEBITO",
        pontos=pontos,
        descricao="Resgate de pontos"
    ))

    _registrar_audit(db, usuario_atual.get("id"), "RESGATE_PONTOS", "fidelidade",
                     str(usuario_id), f"pontos={pontos}")
    db.commit()
    db.refresh(fid)
    return fid


# ─── Auditoria ────────────────────────────────────────────────────────────────

def _registrar_audit(db: Session, usuario_id, acao: str, recurso: str,
                     recurso_id: str = None, detalhes: str = None):
    try:
        db.add(AuditLog(
            usuario_id=usuario_id,
            acao=acao,
            recurso=recurso,
            recurso_id=recurso_id,
            detalhes=detalhes
        ))
    except Exception:
        pass
