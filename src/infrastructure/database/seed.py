import bcrypt
from datetime import datetime, timezone
from .database import SessionLocal
from .models import Usuario, Unidade, Categoria, Produto, Estoque, Fidelidade


def seed_database():
    db = SessionLocal()
    try:
        # Só executa se não houver dados
        if db.query(Usuario).count() > 0:
            return

        print("Populando banco de dados com dados iniciais...")

        # Usuários
        usuarios_data = [
            ("Admin Master", "admin@raizes.com", "password", "ADMIN"),
            ("Gerente Fortaleza", "gerente@raizes.com", "password", "GERENTE"),
            ("Atendente João", "atendente@raizes.com", "password", "ATENDENTE"),
            ("Cozinha Principal", "cozinha@raizes.com", "password", "COZINHA"),
            ("Maria Cliente", "cliente@raizes.com", "password", "CLIENTE"),
        ]
        usuarios = []
        for nome, email, senha, perfil in usuarios_data:
            h = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
            u = Usuario(nome=nome, email=email, senha_hash=h, perfil=perfil,
                        consentimento_lgpd=True, consentimento_data=datetime.now(timezone.utc))
            db.add(u)
            usuarios.append(u)
        db.flush()

        # Unidades
        unidades_data = [
            ("Raízes do Nordeste - Fortaleza Centro", "Av. Domingos Olímpio, 1200", "Fortaleza", "CE"),
            ("Raízes do Nordeste - Recife Boa Viagem", "Av. Boa Viagem, 3500", "Recife", "PE"),
            ("Raízes do Nordeste - Salvador Barra", "Av. Oceânica, 900", "Salvador", "BA"),
        ]
        for nome, end, cidade, estado in unidades_data:
            db.add(Unidade(nome=nome, endereco=end, cidade=cidade, estado=estado))
        db.flush()

        # Categorias
        for nome in ["Lanches", "Bebidas", "Porções", "Sobremesas"]:
            db.add(Categoria(nome=nome))
        db.flush()

        # Produtos
        produtos_data = [
            ("Bauru do Nordeste", "Carne de sol, queijo coalho e cebola", 24.90, 1),
            ("X-Cangaço", "Hambúrguer artesanal com pimenta nordestina", 32.90, 1),
            ("Tapioca Recheada", "Tapioca com carne de sol e queijo", 18.90, 1),
            ("Caldo de Cana", "Caldo de cana fresco 500ml", 8.90, 2),
            ("Suco de Cajá", "Suco natural de cajá 400ml", 9.90, 2),
            ("Limonada Nordestina", "Limonada com gengibre e hortelã", 11.90, 2),
            ("Buchada de Bode", "Prato típico nordestino porção 300g", 29.90, 3),
            ("Queijo Coalho Grelhado", "Queijo coalho na brasa 200g", 19.90, 3),
            ("Bolo de Rolo", "Bolo de rolo pernambucano fatia", 12.90, 4),
            ("Cocada Branca", "Cocada artesanal 100g", 7.90, 4),
        ]
        for nome, desc, preco, cat_id in produtos_data:
            db.add(Produto(nome=nome, descricao=desc, preco=preco, categoria_id=cat_id))
        db.flush()

        # Estoque (unidades 1 e 2)
        for unidade_id in [1, 2]:
            for produto_id in range(1, 11):
                db.add(Estoque(unidade_id=unidade_id, produto_id=produto_id, quantidade=50))
        db.flush()

        # Fidelidade para clientes
        for u in usuarios:
            if u.perfil == "CLIENTE":
                db.add(Fidelidade(usuario_id=u.id, pontos_saldo=0, pontos_acumulados=0))

        db.commit()
        print("Seed concluído com sucesso!")
        print("\nCredenciais:")
        print("  admin@raizes.com / password  (ADMIN)")
        print("  cliente@raizes.com / password (CLIENTE)")

    except Exception as e:
        db.rollback()
        print(f"Erro no seed: {e}")
    finally:
        db.close()
