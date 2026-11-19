"""
Carga da base "Folclore Paraibano" no Memgraph (grafo de propriedades).

Lê dados/entidades_paraiba_completo.json (a mesma base do Mini-Projeto 3)
e cria o grafo do zero. Pode ser executado quantas vezes quiser: o script
começa apagando tudo, então o resultado é sempre o mesmo.

Uso:
    python carga.py            # carrega no Memgraph (bolt://localhost:7687)
    python carga.py --dry-run  # só valida o JSON e mostra as contagens esperadas
"""
import argparse
import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO_JSON = PASTA / "dados" / "entidades_paraiba_completo.json"
URI = "bolt://localhost:7687"

# Classificação original (com acento) -> rótulo extra do nó (substitui as
# subclasses do OWL: Assombracao, Encantado, ...).
ROTULOS_TIPO = {
    "Assombração": "Assombracao",
    "Encantado": "Encantado",
    "Guardião": "Guardiao",
    "Metamorfo": "Metamorfo",
    "Maldição": "Maldicao",
    "Origem": "Origem",
}

# tipo da relação na API -> tipo de relacionamento no grafo.
TIPOS_RELACAO = {
    "companion": "COMPANHEIRA_DE",
    "elemental_kin": "PARENTE_ELEMENTAL_DE",
    "variant": "VARIANTE_DE",
    "rival": "RIVAL_DE",
}

# Constraints: o análogo do owl:hasKey / FunctionalProperty do MP3.
CONSTRAINTS = [
    ("Entidade", "slug"),
    ("Estado", "sigla"),
    ("Regiao", "nome"),
    ("Bioma", "id"),
    ("MatrizCultural", "id"),
    ("Povo", "id"),
    ("Elemento", "id"),
    ("Fonte", "id"),
    ("Citacao", "id"),
    ("Variacao", "id"),
]


def limpar(mapa):
    """Remove chaves com valor None (propriedade ausente = sem propriedade)."""
    return {k: v for k, v in mapa.items() if v is not None}


# ------------------------------------------------------------
# 1. Preparar os dados (só Python, não toca no banco)
# ------------------------------------------------------------
def preparar(entidades):
    dados = {
        "entidades": {},       # rótulo de tipo -> lista de linhas
        "referencias": {},     # slug -> nome
        "estados": [], "regioes": [], "biomas": [],
        "matrizes": [], "povos": [], "elementos": [],
        "fontes": [], "citacoes": [], "variacoes": [],
        "relacoes": {},        # tipo do grafo -> lista de linhas
    }
    slugs_completos = {e["slug"] for e in entidades}

    for e in entidades:
        slug = e["slug"]
        texto = e.get("texto") or {}
        rotulo = ROTULOS_TIPO[e["classification"]]

        dados["entidades"].setdefault(rotulo, []).append({
            "slug": slug,
            "props": limpar({
                "slug": slug,
                "nome": texto.get("nome"),
                "descricao": texto.get("descricao_curta"),
                "tagline": texto.get("tagline"),
                "causoCompleto": texto.get("causo_completo"),
                "classificacao": e.get("classification"),
                "nivelAmeaca": e.get("threat_level"),
                "raridade": e.get("rarity_tier"),
                "confianca": e.get("confianca"),
                "origemIncerta": e.get("origem_incerta"),
                "cultoVivo": e.get("culto_vivo"),
                "referencia": False,
            }),
        })

        for sigla in e.get("estados") or []:
            dados["estados"].append({"slug": slug, "sigla": sigla})

        for item in e.get("regioes") or []:
            if item.get("regiao"):
                dados["regioes"].append({
                    "slug": slug, "nome": item["regiao"],
                    "principal": item.get("principal") in (1, True, "1"),
                })

        for item in e.get("biomas") or []:
            if item.get("bioma_id"):
                dados["biomas"].append({
                    "slug": slug, "id": item["bioma_id"],
                    "principal": item.get("principal") in (1, True, "1"),
                })

        for item in e.get("origens") or []:
            if item.get("matriz"):
                dados["matrizes"].append({"slug": slug, "id": item["matriz"]})
            for povo in item.get("povos") or []:
                dados["povos"].append({"slug": slug, "id": povo})

        for papel, campo in (("primario", "element_primary"),
                             ("secundario", "element_secondary")):
            if e.get(campo):
                dados["elementos"].append({
                    "slug": slug, "id": e[campo], "papel": papel,
                })

        for i, v in enumerate(e.get("variacoes") or [], start=1):
            vid = v.get("id") or f"registro-{i}"
            dados["variacoes"].append({
                "slug": slug,
                "props": limpar({
                    "id": f"variacao_{slug}_{vid}",
                    "registro": v.get("registro"),
                    "nomeLocal": v.get("nome_local"),
                    "localidade": v.get("localidade"),
                    "estadoUf": v.get("estado_uf"),
                    "confianca": v.get("confianca"),
                }),
            })

        for i, f in enumerate(e.get("fontes") or [], start=1):
            dados["fontes"].append({
                "slug": slug,
                "props": limpar({
                    "id": f"fonte_{slug}_{i}",
                    "tipo": f.get("tipo"),
                    "ref": f.get("ref"),
                    "licenca": f.get("licenca"),
                }),
            })

        for i, c in enumerate(e.get("citacoes") or [], start=1):
            dados["citacoes"].append({
                "slug": slug,
                "props": limpar({
                    "id": f"citacao_{slug}_{i}",
                    "texto": c.get("citacao"),
                    "autor": c.get("autor"),
                    "obra": c.get("obra"),
                    "ano": c.get("ano"),
                }),
            })

        for r in e.get("relacionadas") or []:
            destino = r.get("relacionada_slug")
            if not destino:
                continue
            if destino not in slugs_completos:
                dados["referencias"].setdefault(destino, r.get("nome"))
            tipo = TIPOS_RELACAO[r["tipo"]]
            dados["relacoes"].setdefault(tipo, []).append({
                "origem": slug, "destino": destino, "motivo": r.get("motivo"),
            })

    return dados


def contagens_esperadas(dados):
    """Contagens que o grafo deve ter depois da carga."""
    unicos = lambda lista, chave: len({x[chave] for x in lista})
    return {
        "Entidades completas": sum(len(v) for v in dados["entidades"].values()),
        "Referências externas": len(dados["referencias"]),
        "Estados": unicos(dados["estados"], "sigla"),
        "Regiões": unicos(dados["regioes"], "nome"),
        "Biomas": unicos(dados["biomas"], "id"),
        "Matrizes culturais": unicos(dados["matrizes"], "id"),
        "Povos": unicos(dados["povos"], "id"),
        "Elementos": unicos(dados["elementos"], "id"),
        "Fontes": len(dados["fontes"]),
        "Citações": len(dados["citacoes"]),
        "Variações": len(dados["variacoes"]),
        "Relações entre entidades": sum(len(v) for v in dados["relacoes"].values()),
    }


# ------------------------------------------------------------
# 2. Gravar no Memgraph
# ------------------------------------------------------------
def carregar(sessao, dados):
    def run(cypher, **params):
        sessao.run(cypher, **params).consume()

    print("Limpando a base...")
    run("MATCH (n) DETACH DELETE n")

    print("Criando constraints de unicidade...")
    for rotulo, prop in CONSTRAINTS:
        try:
            run(f"CREATE CONSTRAINT ON (n:{rotulo}) ASSERT n.{prop} IS UNIQUE")
        except Exception as erro:  # já existe: tudo bem
            print(f"  (constraint {rotulo}.{prop} ignorada: {str(erro)[:60]})")

    print("Criando entidades completas...")
    for rotulo, linhas in dados["entidades"].items():
        # O rótulo vem do dicionário fixo ROTULOS_TIPO, nunca do usuário.
        run(
            f"UNWIND $linhas AS l "
            f"CREATE (e:Entidade:{rotulo}) SET e = l.props",
            linhas=linhas,
        )

    print("Criando referências externas...")
    run(
        "UNWIND $linhas AS l "
        "CREATE (e:Entidade:Referencia {slug: l.slug, nome: l.nome, referencia: true})",
        linhas=[{"slug": s, "nome": n} for s, n in dados["referencias"].items()],
    )

    print("Criando estados, regiões, biomas, matrizes, povos e elementos...")
    run(
        "UNWIND $linhas AS l "
        "MATCH (e:Entidade {slug: l.slug}) "
        "MERGE (x:Estado {sigla: l.sigla}) "
        "MERGE (e)-[:POSSUI_ESTADO]->(x)",
        linhas=dados["estados"],
    )
    run(
        "UNWIND $linhas AS l "
        "MATCH (e:Entidade {slug: l.slug}) "
        "MERGE (x:Regiao {nome: l.nome}) "
        "MERGE (e)-[r:ASSOCIADA_A_REGIAO]->(x) SET r.principal = l.principal",
        linhas=dados["regioes"],
    )
    run(
        "UNWIND $linhas AS l "
        "MATCH (e:Entidade {slug: l.slug}) "
        "MERGE (x:Bioma {id: l.id}) "
        "MERGE (e)-[r:ASSOCIADA_A_BIOMA]->(x) SET r.principal = l.principal",
        linhas=dados["biomas"],
    )
    run(
        "UNWIND $linhas AS l "
        "MATCH (e:Entidade {slug: l.slug}) "
        "MERGE (x:MatrizCultural {id: l.id}) "
        "MERGE (e)-[:TEM_ORIGEM]->(x)",
        linhas=dados["matrizes"],
    )
    run(
        "UNWIND $linhas AS l "
        "MATCH (e:Entidade {slug: l.slug}) "
        "MERGE (x:Povo {id: l.id}) "
        "MERGE (e)-[:ASSOCIADA_AO_POVO]->(x)",
        linhas=dados["povos"],
    )
    run(
        "UNWIND $linhas AS l "
        "MATCH (e:Entidade {slug: l.slug}) "
        "MERGE (x:Elemento {id: l.id}) "
        "MERGE (e)-[r:TEM_ELEMENTO]->(x) SET r.papel = l.papel",
        linhas=dados["elementos"],
    )

    print("Criando fontes, citações e variações...")
    for chave, rotulo, rel in (
        ("fontes", "Fonte", "TEM_FONTE"),
        ("citacoes", "Citacao", "TEM_CITACAO"),
        ("variacoes", "Variacao", "TEM_VARIACAO"),
    ):
        run(
            f"UNWIND $linhas AS l "
            f"MATCH (e:Entidade {{slug: l.slug}}) "
            f"CREATE (e)-[:{rel}]->(n:{rotulo}) SET n = l.props",
            linhas=dados[chave],
        )

    print("Criando relações entre entidades...")
    for tipo, linhas in dados["relacoes"].items():
        run(
            f"UNWIND $linhas AS l "
            f"MATCH (a:Entidade {{slug: l.origem}}), (b:Entidade {{slug: l.destino}}) "
            f"CREATE (a)-[r:{tipo}]->(b) SET r.motivo = l.motivo",
            linhas=linhas,
        )


def conferir(sessao, esperado):
    """Compara o que está no banco com o que o JSON prometia."""
    consultas = {
        "Entidades completas": "MATCH (e:Entidade) WHERE e.referencia = false RETURN count(e) AS n",
        "Referências externas": "MATCH (e:Referencia) RETURN count(e) AS n",
        "Estados": "MATCH (n:Estado) RETURN count(n) AS n",
        "Regiões": "MATCH (n:Regiao) RETURN count(n) AS n",
        "Biomas": "MATCH (n:Bioma) RETURN count(n) AS n",
        "Matrizes culturais": "MATCH (n:MatrizCultural) RETURN count(n) AS n",
        "Povos": "MATCH (n:Povo) RETURN count(n) AS n",
        "Elementos": "MATCH (n:Elemento) RETURN count(n) AS n",
        "Fontes": "MATCH (n:Fonte) RETURN count(n) AS n",
        "Citações": "MATCH (n:Citacao) RETURN count(n) AS n",
        "Variações": "MATCH (n:Variacao) RETURN count(n) AS n",
        "Relações entre entidades":
            "MATCH (:Entidade)-[r:COMPANHEIRA_DE|PARENTE_ELEMENTAL_DE|VARIANTE_DE|RIVAL_DE]->(:Entidade) "
            "RETURN count(r) AS n",
    }
    ok = True
    print(f"\n{'Item':<28}{'JSON':>7}{'Memgraph':>10}")
    for nome, cypher in consultas.items():
        no_banco = sessao.run(cypher).single()["n"]
        marca = "" if no_banco == esperado[nome] else "  <-- DIFERENTE"
        ok = ok and no_banco == esperado[nome]
        print(f"{nome:<28}{esperado[nome]:>7}{no_banco:>10}{marca}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="só valida o JSON e mostra as contagens esperadas")
    args = ap.parse_args()

    entidades = json.loads(ARQUIVO_JSON.read_text(encoding="utf-8"))
    dados = preparar(entidades)
    esperado = contagens_esperadas(dados)

    if args.dry_run:
        print("Contagens esperadas (a partir do JSON):")
        for nome, valor in esperado.items():
            print(f"  {nome:<28}{valor:>5}")
        return

    from neo4j import GraphDatabase

    with GraphDatabase.driver(URI, auth=("", "")) as driver:
        driver.verify_connectivity()
        with driver.session() as sessao:
            carregar(sessao, dados)
            ok = conferir(sessao, esperado)
            total = sessao.run("MATCH (n) RETURN count(n) AS n").single()["n"]
            print(f"\nTotal de nós no grafo: {total}")

    print("\nCarga concluída com sucesso." if ok else
          "\nATENÇÃO: há diferenças entre o JSON e o grafo.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
