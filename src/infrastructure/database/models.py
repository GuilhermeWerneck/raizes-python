from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from .database import Base


class CanalPedidoEnum(str, enum.Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedidoEnum(str, enum.Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO = "PAGO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class PerfilEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    GERENTE = "GERENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    CLIENTE = "CLIENTE"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(String(20), nullable=False, default="CLIENTE")
    ativo = Column(Boolean, default=True)
    consentimento_lgpd = Column(Boolean, default=False)
    consentimento_data = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Unidade(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    endereco = Column(String(255), nullable=False)
    cidade = Column(String(100), nullable=False)
    estado = Column(String(2), nullable=False)
    ativo = Column(Boolean, default=True)


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(String(255))


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(String(500))
    preco = Column(Float, nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"))
    ativo = Column(Boolean, default=True)

    categoria = relationship("Categoria")


class Estoque(Base):
    __tablename__ = "estoque"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, default=0, nullable=False)

    unidade = relationship("Unidade")
    produto = relationship("Produto")


class ItemPedido(Base):
    __tablename__ = "itens_pedido"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, nullable=False)
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Float, nullable=False)


class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    unidade_id = Column(Integer, nullable=False)
    canal_pedido = Column(String(10), nullable=False)
    status = Column(String(30), default="AGUARDANDO_PAGAMENTO", nullable=False)
    valor_total = Column(Float, nullable=False)
    forma_pagamento = Column(String(20), default="MOCK", nullable=False)
    status_pagamento = Column(String(15), default="PENDENTE", nullable=False)
    gateway_transaction_id = Column(String(100), nullable=True)
    consentimento_lgpd = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    itens = relationship("ItemPedido", cascade="all, delete-orphan")


class Pagamento(Base):
    __tablename__ = "pagamentos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), unique=True, nullable=False)
    forma_pagamento = Column(String(20), nullable=False)
    status = Column(String(15), default="PENDENTE", nullable=False)
    valor = Column(Float, nullable=False)
    gateway_transaction_id = Column(String(100), nullable=True)
    gateway_mensagem = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Fidelidade(Base):
    __tablename__ = "fidelidade"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False)
    pontos_saldo = Column(Integer, default=0)
    pontos_acumulados = Column(Integer, default=0)
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, nullable=True)
    acao = Column(String(50), nullable=False)
    recurso = Column(String(50), nullable=False)
    recurso_id = Column(String(100), nullable=True)
    detalhes = Column(Text, nullable=True)
    ip = Column(String(45), nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HistoricoFidelidade(Base):
    __tablename__ = "historico_fidelidade"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(String(10), nullable=False)  # CREDITO ou DEBITO
    pontos = Column(Integer, nullable=False)
    descricao = Column(String(255), nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
