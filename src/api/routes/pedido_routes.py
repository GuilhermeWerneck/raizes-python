from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.infrastructure.database.database import get_db
from src.application.services.services import (
    criar_pedido, listar_pedidos, buscar_pedido, atualizar_status_pedido,
    decodificar_token
)
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter(tags=["Pedidos"])


def get_current_user(token: str = Depends(oauth2_scheme)):
    return decodificar_token(token)


class ItemPedidoSchema(BaseModel):
    produto_id: int
    quantidade: int = Field(gt=0)
    preco_unitario: float = Field(gt=0)


class CriarPedidoSchema(BaseModel):
    usuario_id: Optional[int] = None
    unidade_id: int
    canal_pedido: str = Field(..., description="APP, TOTEM, BALCAO, PICKUP ou WEB")
    valor_total: float = Field(gt=0)
    forma_pagamento: str = Field(default="MOCK")
    consentimento_lgpd: bool = Field(..., description="Consentimento LGPD obrigatório")
    itens: List[ItemPedidoSchema] = Field(..., min_length=1)


@router.post("/", summary="Criar novo pedido", status_code=201)
def criar(dados: CriarPedidoSchema, db: Session = Depends(get_db),
          current_user: dict = Depends(get_current_user)):
    """
    Fluxo crítico: cria pedido → verifica estoque → pagamento mock → atualiza status.

    - **canal_pedido**: obrigatório — APP, TOTEM, BALCAO, PICKUP ou WEB
    - **consentimento_lgpd**: obrigatório — true (LGPD)
    """
    pedido = criar_pedido(db, dados.model_dump())
    return {
        "id": pedido.id,
        "canal_pedido": pedido.canal_pedido,
        "status": pedido.status,
        "status_pagamento": pedido.status_pagamento,
        "valor_total": pedido.valor_total,
        "forma_pagamento": pedido.forma_pagamento,
        "gateway_transaction_id": pedido.gateway_transaction_id,
        "consentimento_lgpd": pedido.consentimento_lgpd,
        "criado_em": pedido.criado_em.isoformat() if pedido.criado_em else None,
        "itens": [
            {"produto_id": i.produto_id, "quantidade": i.quantidade, "preco_unitario": i.preco_unitario}
            for i in pedido.itens
        ]
    }


@router.get("/", summary="Listar pedidos")
def listar(
    canal_pedido: Optional[str] = Query(None, description="APP, TOTEM, BALCAO, PICKUP, WEB"),
    status: Optional[str] = Query(None, description="AGUARDANDO_PAGAMENTO, PAGO, EM_PREPARO, PRONTO, ENTREGUE, CANCELADO"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Lista pedidos com filtros opcionais por canal e status."""
    pedidos = listar_pedidos(db, canal_pedido, status)
    return [
        {
            "id": p.id,
            "usuario_id": p.usuario_id,
            "unidade_id": p.unidade_id,
            "canal_pedido": p.canal_pedido,
            "status": p.status,
            "status_pagamento": p.status_pagamento,
            "valor_total": p.valor_total,
            "forma_pagamento": p.forma_pagamento,
            "consentimento_lgpd": p.consentimento_lgpd,
            "criado_em": p.criado_em.isoformat() if p.criado_em else None,
        }
        for p in pedidos
    ]


@router.get("/{pedido_id}", summary="Buscar pedido por ID")
def buscar(pedido_id: int, db: Session = Depends(get_db),
           current_user: dict = Depends(get_current_user)):
    """Retorna detalhes completos de um pedido."""
    p = buscar_pedido(db, pedido_id)
    return {
        "id": p.id,
        "usuario_id": p.usuario_id,
        "unidade_id": p.unidade_id,
        "canal_pedido": p.canal_pedido,
        "status": p.status,
        "status_pagamento": p.status_pagamento,
        "valor_total": p.valor_total,
        "forma_pagamento": p.forma_pagamento,
        "gateway_transaction_id": p.gateway_transaction_id,
        "consentimento_lgpd": p.consentimento_lgpd,
        "criado_em": p.criado_em.isoformat() if p.criado_em else None,
        "itens": [
            {"produto_id": i.produto_id, "quantidade": i.quantidade, "preco_unitario": i.preco_unitario}
            for i in p.itens
        ]
    }


@router.patch("/{pedido_id}/status", summary="Atualizar status do pedido (GERENTE/COZINHA/ADMIN)")
def atualizar_status(
    pedido_id: int,
    novo_status: str = Query(..., description="PAGO, EM_PREPARO, PRONTO, ENTREGUE ou CANCELADO"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Transições válidas: AGUARDANDO_PAGAMENTO→PAGO→EM_PREPARO→PRONTO→ENTREGUE

    Perfis permitidos: ADMIN, GERENTE, ATENDENTE, COZINHA
    """
    p = atualizar_status_pedido(db, pedido_id, novo_status, current_user)
    return {
        "id": p.id,
        "status": p.status,
        "atualizado_em": p.atualizado_em.isoformat() if p.atualizado_em else None
    }
