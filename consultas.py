"""
Aplicação de consultas Cypher sobre o grafo "Folclore Paraibano" (Memgraph).

Executa, em ordem, todas as consultas do Mini-Projeto 3 reescritas em Cypher
(as 7 do rdflib e as 11 de SPARQL) e mais 6 consultas de travessia
(a consulta 6 do rdflib é impressa em dois blocos).
Cada consulta é impressa com número, origem no MP3 e propósito.

Uso:  python consultas.py
"""
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("", "")

contador = 0


def cortar(valor, limite=70):
    texto = str(valor)
    return texto if len(texto) <= limite else texto[:limite] + "..."


def consulta(sessao, origem, proposito, cypher, params=None, mostrar=None):
    """Executa uma consulta e imprime o resultado identificado."""
    global contador
    contador += 1
    print("\n" + "=" * 70)
    print(f"CONSULTA {contador}  [{origem}]")
    print(f"Propósito: {proposito}")
    print("=" * 70)
    linhas = sessao.run(cypher, **(params or {})).data()
    if mostrar:
        mostrar(linhas)
    else:
        for linha in linhas:
            print(" | ".join(cortar(v) if v is not None else "Não informado"
                             for v in linha.values()))
    print(f"({len(linhas)} linha(s))")
    return linhas


def total_nos(sessao):
    return sessao.run("MATCH (n) RETURN count(n) AS n").single()["n"]


def resposta_ask(linhas):
    print(linhas[0]["resposta"])


def main():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()
        with driver.session() as s:
            print("=" * 70)
            print("GRAFO CARREGADO")
            print("=" * 70)
            print("Total de nós:", total_nos(s))
            print("Total de relacionamentos:",
                  s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"])

            # ==================================================
            # PARTE A - consultas do rdflib (MP3) em Cypher
            # ==================================================
            consulta(s, "rdflib 1",
                "Listar as 32 entidades completas (ficam de fora as 46 referências)",
                """
                MATCH (e:Entidade)
                WHERE e.referencia = false
                RETURN e.nome AS nome,
                       [l IN labels(e) WHERE l <> 'Entidade'][0] AS tipo
                ORDER BY e.slug
                """)

            consulta(s, "rdflib 2",
                "Entidades associadas à Paraíba",
                """
                MATCH (e:Entidade)-[:POSSUI_ESTADO]->(:Estado {sigla: 'PB'})
                RETURN e.nome AS nome
                ORDER BY e.nome
                """)

            consulta(s, "rdflib 3",
                "Entidades associadas ao bioma Caatinga",
                """
                MATCH (e:Entidade)-[:ASSOCIADA_A_BIOMA]->(:Bioma {id: 'caatinga'})
                RETURN e.nome AS nome
                ORDER BY e.nome
                """)

            consulta(s, "rdflib 4",
                "Relações do tipo rival, com origem, destino e motivo",
                """
                MATCH (a:Entidade)-[r:RIVAL_DE]->(b:Entidade)
                RETURN a.nome AS origem, b.nome AS destino, r.motivo AS motivo
                ORDER BY origem
                """)

            consulta(s, "rdflib 5",
                "Citações com autor, obra e texto",
                """
                MATCH (:Entidade)-[:TEM_CITACAO]->(c:Citacao)
                RETURN coalesce(c.autor, 'Não informado') AS autor,
                       coalesce(c.obra, 'Não informado') AS obra,
                       coalesce(c.texto, 'Não informado') AS texto
                """)

            # Consulta 6: tudo sobre uma entidade (sujeito fixo).
            def mostrar_mula(linhas):
                propriedades = linhas[0]["props"]
                print("-- Propriedades do nó --")
                for chave in sorted(propriedades):
                    print(f"{chave}: {cortar(propriedades[chave])}")
            consulta(s, "rdflib 6 (propriedades)",
                "Tudo sobre a Mula Sem Cabeça: propriedades do nó",
                "MATCH (e:Entidade {slug: 'mula-sem-cabeca'}) RETURN properties(e) AS props",
                mostrar=mostrar_mula)

            def mostrar_ligacoes(linhas):
                print("-- Relacionamentos de saída --")
                for l in linhas:
                    print(f"{l['relacionamento']} -> ({l['tipo']}) {cortar(l['destino'])}")
            consulta(s, "rdflib 6 (relacionamentos)",
                "Tudo sobre a Mula Sem Cabeça: para onde ela aponta",
                """
                MATCH (e:Entidade {slug: 'mula-sem-cabeca'})-[r]->(x)
                RETURN type(r) AS relacionamento,
                       [l IN labels(x) WHERE l <> 'Entidade'][0] AS tipo,
                       coalesce(x.nome, x.id, x.sigla, x.ref, x.texto) AS destino
                ORDER BY relacionamento, destino
                """,
                mostrar=mostrar_ligacoes)

            consulta(s, "rdflib 7",
                "Tudo que aponta para a Caatinga, contado por tipo de relacionamento",
                """
                MATCH (n)-[r]->(:Bioma {id: 'caatinga'})
                RETURN type(r) AS relacionamento,
                       r.principal AS bioma_principal,
                       count(*) AS quantidade
                ORDER BY quantidade DESC
                """)

            # ==================================================
            # PARTE B - consultas SPARQL (MP3) em Cypher
            # ==================================================
            consulta(s, "SPARQL 1",
                "Entidades e suas classificações, em ordem alfabética",
                """
                MATCH (e:Entidade)
                WHERE e.classificacao IS NOT NULL
                RETURN e.nome AS nome, e.classificacao AS classificacao
                ORDER BY nome
                """)

            consulta(s, "SPARQL 2",
                "Filtro: entidades com nível de ameaça baixo",
                """
                MATCH (e:Entidade)
                WHERE e.nivelAmeaca = 'baixo'
                RETURN e.nome AS nome, e.nivelAmeaca AS ameaca
                """)

            consulta(s, "SPARQL 3",
                "Entidades em ordem alfabética decrescente",
                """
                MATCH (e:Entidade)
                WHERE e.classificacao IS NOT NULL
                RETURN e.nome AS nome
                ORDER BY nome DESC
                """)

            consulta(s, "SPARQL 4",
                "Quantidade de entidades por classificação",
                """
                MATCH (e:Entidade)
                WHERE e.classificacao IS NOT NULL
                RETURN e.classificacao AS classificacao, count(e) AS quantidade
                ORDER BY quantidade DESC
                """)

            consulta(s, "SPARQL 5 (ASK)",
                "Aipó e Tambiá está associada à Paraíba?",
                """
                MATCH (:Entidade {slug: 'aipo-e-tambia'})-[:POSSUI_ESTADO]->(:Estado {sigla: 'PB'})
                RETURN count(*) > 0 AS resposta
                """, mostrar=resposta_ask)

            consulta(s, "SPARQL 6 (ASK)",
                "Existe alguma entidade associada à Caatinga?",
                """
                MATCH (:Entidade)-[:ASSOCIADA_A_BIOMA]->(:Bioma {id: 'caatinga'})
                RETURN count(*) > 0 AS resposta
                """, mostrar=resposta_ask)

            consulta(s, "SPARQL 7 (CONSTRUCT)",
                "Subgrafo reduzido: nome e estado das entidades da Paraíba",
                """
                MATCH (e:Entidade)-[r:POSSUI_ESTADO]->(x:Estado {sigla: 'PB'})
                RETURN e.nome AS entidade, type(r) AS relacionamento, x.sigla AS estado
                ORDER BY entidade
                """)

            # --- Atualizações: o efeito aparece na contagem de nós ---
            antes = total_nos(s)
            print(f"\n[Antes das atualizações] Total de nós: {antes}")

            consulta(s, "SPARQL 8 (INSERT DATA)",
                "Inserir uma entidade temporária 'teste-sparql'",
                """
                MERGE (t:Entidade {slug: 'teste-sparql'})
                ON CREATE SET t.confianca = 'baixa', t.referencia = false
                RETURN t.slug AS slug, t.confianca AS confianca
                """)
            print("Total de nós após a inserção:", total_nos(s),
                  f"(antes: {antes})")

            consulta(s, "SPARQL 9 (DELETE/INSERT WHERE)",
                "Alterar a confiança da entidade temporária de 'baixa' para 'media'",
                """
                MATCH (t:Entidade {slug: 'teste-sparql'})
                WHERE t.confianca = 'baixa'
                SET t.confianca = 'media'
                RETURN t.slug AS slug, t.confianca AS confianca_atual
                """)

            consulta(s, "SPARQL 10 (DELETE DATA)",
                "Remover a entidade temporária",
                """
                MATCH (t:Entidade {slug: 'teste-sparql'})
                DETACH DELETE t
                """)
            restantes = s.run(
                "MATCH (t {slug: 'teste-sparql'}) RETURN count(t) AS n").single()["n"]
            print("Nós restantes da entidade temporária:", restantes)
            print("Total de nós após a remoção:", total_nos(s),
                  f"(igual ao inicial: {total_nos(s) == antes})")

            consulta(s, "SPARQL 11 (ASK)",
                "Aipó e Tambiá está associada ao Rio Grande do Sul? (resposta esperada: False)",
                """
                MATCH (:Entidade {slug: 'aipo-e-tambia'})-[:POSSUI_ESTADO]->(:Estado {sigla: 'RS'})
                RETURN count(*) > 0 AS resposta
                """, mostrar=resposta_ask)

            # ==================================================
            # PARTE C - consultas com travessia (2+ relacionamentos)
            # ==================================================
            consulta(s, "Travessia 1",
                "Pares de entidades companheiras da mesma referência externa "
                "(a)-[COMPANHEIRA_DE]->(ref)<-[COMPANHEIRA_DE]-(b)",
                """
                MATCH (a:Entidade)-[:COMPANHEIRA_DE]->(ref:Referencia)<-[:COMPANHEIRA_DE]-(b:Entidade)
                WHERE a.slug < b.slug
                RETURN a.nome AS entidade_a, ref.nome AS em_comum, b.nome AS entidade_b
                ORDER BY em_comum, entidade_a
                """)

            consulta(s, "Travessia 2",
                "Companheira de companheira (dois saltos de COMPANHEIRA_DE)",
                """
                MATCH (a:Entidade)-[:COMPANHEIRA_DE]->(b:Entidade)-[:COMPANHEIRA_DE]->(c:Entidade)
                WHERE a <> c
                RETURN a.nome AS origem, b.nome AS intermediaria, c.nome AS destino
                ORDER BY origem, intermediaria, destino
                """)

            consulta(s, "Travessia 3",
                "De onde vêm as fontes das companheiras de cada entidade? "
                "(entidade -> companheira -> fonte)",
                """
                MATCH (a:Entidade)-[:COMPANHEIRA_DE]->(b:Entidade)-[:TEM_FONTE]->(f:Fonte)
                RETURN a.nome AS entidade, b.nome AS companheira,
                       count(f) AS qtd_fontes, collect(DISTINCT f.tipo) AS tipos_de_fonte
                ORDER BY entidade, companheira
                """)

            consulta(s, "Travessia 4",
                "Rivais que vivem no mesmo bioma "
                "(RIVAL_DE + dois ASSOCIADA_A_BIOMA para o mesmo bioma)",
                """
                MATCH (a:Entidade)-[:RIVAL_DE]->(b:Entidade),
                      (a)-[:ASSOCIADA_A_BIOMA]->(bi:Bioma)<-[:ASSOCIADA_A_BIOMA]-(b)
                RETURN a.nome AS entidade_a, b.nome AS rival,
                       collect(bi.id) AS biomas_em_comum
                ORDER BY entidade_a
                """)

            consulta(s, "Travessia 5",
                "Entidades do mesmo povo e com o mesmo elemento "
                "(ASSOCIADA_AO_POVO e TEM_ELEMENTO compartilhados)",
                """
                MATCH (a:Entidade)-[:ASSOCIADA_AO_POVO]->(p:Povo)<-[:ASSOCIADA_AO_POVO]-(b:Entidade),
                      (a)-[:TEM_ELEMENTO]->(el:Elemento)<-[:TEM_ELEMENTO]-(b)
                WHERE a.slug < b.slug
                RETURN a.nome AS entidade_a, b.nome AS entidade_b,
                       p.id AS povo, collect(DISTINCT el.id) AS elementos
                ORDER BY povo, entidade_a, entidade_b
                """)

            def mostrar_caminho(linhas):
                if not linhas:
                    print("Nenhum caminho encontrado.")
                for l in linhas:
                    print(" -> ".join(l["caminho"]))
                    print("Tipos de relacionamento:", ", ".join(l["tipos"]))
                    print("Saltos:", l["saltos"])
            consulta(s, "Travessia 6",
                "Caminho mais curto entre Mula-sem-cabeça e Bicho-sete-cabeças, "
                "seguindo relações entre entidades (qualquer direção, até 6 saltos)",
                """
                MATCH p = (a:Entidade {slug: $origem})
                          -[:COMPANHEIRA_DE|PARENTE_ELEMENTAL_DE|VARIANTE_DE|RIVAL_DE*1..6]-
                          (b:Entidade {slug: $destino})
                RETURN [n IN nodes(p) | n.nome] AS caminho,
                       [r IN relationships(p) | type(r)] AS tipos,
                       size(relationships(p)) AS saltos
                ORDER BY saltos
                LIMIT 1
                """,
                params={"origem": "mula-sem-cabeca", "destino": "bicho-sete-cabecas"},
                mostrar=mostrar_caminho)

    print("\n" + "=" * 70)
    print("CONSULTAS CYPHER FINALIZADAS")
    print("=" * 70)


if __name__ == "__main__":
    main()
