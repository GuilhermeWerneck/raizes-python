# Raízes do Nordeste - Backend API

**Projeto Multidisciplinar — Trilha: Back-End — UNINTER 2026**
**Aluno:** Guilherme Werneck | **RU:** 4310215

---

## Sobre o projeto

Sistema de gestão multicanal para a rede de lanchonetes **Raízes do Nordeste**. Gerencia pedidos via APP, Totem e Balcão com autenticação JWT, pagamento Mock e registro de consentimento LGPD.

## Tecnologias

- Python 3.10+
- FastAPI (API REST + Swagger automático)
- Pydantic (validação de dados)
- SQLAlchemy + SQLite (banco de dados)
- PyJWT (autenticação)
- Bcrypt (hash de senhas)

## Arquitetura em Camadas

- **API**: Rotas e contratos de entrada/saída (Swagger)
- **Application**: Serviços e regras de fluxo
- **Domain**: Entidades do negócio
- **Infrastructure**: Banco SQLite e segurança JWT

## Como rodar

### 1. Instalar Python 3.10+ em https://python.org

### 2. Criar ambiente virtual (recomendado)
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Iniciar a API
```bash
uvicorn main:app --reload
```

Acesse o Swagger em: **http://127.0.0.1:8000/docs**

---

## Credenciais de teste

| E-mail | Perfil | Senha |
|---|---|---|
| admin@raizes.com | ADMIN | password |
| gerente@raizes.com | GERENTE | password |
| cliente@raizes.com | CLIENTE | password |

Login rápido também aceita: `admin` / `admin`

---

## Endpoints principais

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| POST | /auth/login | Login JWT | Público |
| GET | /produtos | Listar produtos | Público |
| GET | /unidades | Listar unidades | Público |
| GET | /estoque/{id} | Consultar estoque | Público |
| POST | /pedidos/ | Criar pedido | JWT |
| GET | /pedidos/ | Listar pedidos | JWT |
| GET | /pedidos/{id} | Buscar pedido | JWT |
| PATCH | /pedidos/{id}/status | Atualizar status | JWT |
| GET | /fidelidade/{id} | Saldo de pontos | JWT |

## Fluxo crítico

```
POST /auth/login        → obtém token JWT
POST /pedidos/          → cria pedido (canal_pedido obrigatório)
                          → verifica estoque → pagamento mock → status PAGO
PATCH /pedidos/{id}/status → EM_PREPARO → PRONTO → ENTREGUE
```

## LGPD e Segurança

- Senhas armazenadas com BCrypt
- Autenticação via JWT
- `consentimento_lgpd: true` obrigatório em todo pedido
- Logs de auditoria para ações sensíveis
