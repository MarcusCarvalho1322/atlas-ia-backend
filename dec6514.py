"""
Tabela de sanções pecuniárias do Decreto 6.514/2008, por artigo.

DE ONDE VEM. Extraída do texto compilado publicado pelo Planalto em
17/09/2026, e não digitada à mão. Cada valor passou por uma conferência
que o próprio decreto oferece: o texto escreve "R$ 5.000,00 (cinco mil reais)",
e só entrou aqui o valor cujo NUMERAL bate com o POR EXTENSO. A conferência
reprovou um: o art. 31 traz "R$ 5.000,00 (mil reais)" — numeral e palavra
divergem no texto oficial —, e por isso o art. 31 não está nesta tabela.

O QUE É `teto_rigido`. É a única coisa que autoriza uma conclusão. Vale True
só quando o artigo fixa faixa ou valor fechado e NÃO há, em nenhuma parte do
artigo, cláusula de acréscimo por unidade. Dos 70 artigos, 34 são assim.

Por que isso importa: a primeira versão desta leitura apontou 82 autos da
carteira "acima do teto legal". Todos os 82 eram artigos com acréscimo por
unidade — art. 35 (R$ 20,00 por quilo de pescado) e art. 82 (R$ 300,00 por
unidade) —, onde o valor da faixa não é teto coisa nenhuma. Com o critério
correto, o número de autos acima do teto na carteira é ZERO.

O QUE ESTA TABELA NÃO SABE. Não sabe de majoração legal: o dobro por vantagem
pecuniária, o dobro em unidade de conservação (art. 93), a triplicação por
reincidência da Lei 9.605/98. Multa acima do valor do artigo pode ser
perfeitamente legal por qualquer um desses caminhos. Por isso o que este
módulo produz é ARITMÉTICA — quantas vezes o valor do artigo — e nunca um
juízo sobre licitude, que é de advogado.
"""

# artigo -> sanção do CAPUT. Parágrafos ficam de fora de propósito: eles trazem
# regra subsidiária (pequeno porte, impossibilidade de contagem), não o preceito
# do tipo. Foi assim que o art. 24 deixou de ser lido como "faixa de R$ 500 a
# R$ 100.000" — essa faixa está no § 9º e vale só para animais de pequeno porte.
SANCOES = {
    "24": {"tipo":'unitaria',"valores":[{"valor":500.0,"unidade":'indivíduo'}, {"valor":5000.0,"unidade":'indivíduo'}],"teto_rigido":False, "texto": "Multa de: I - R$ 500,00 (quinhentos reais) por indivíduo de espécie não constante de listas oficiais de risco ou ameaça de extinção; II - R$ 5.000,00 (cinco mil reais), por indivíduo de espécie constante de listas oficiais de faun"},
    "25": {"tipo":'unitaria',"valores":[{"valor":200.0,"unidade":'indivíduo'}, {"valor":5000.0,"unidade":'indivíduo'}],"teto_rigido":False, "texto": "Multa de R$ 2.000,00 (dois mil reais), com acréscimo por exemplar excedente de: I - R$ 200,00 (duzentos reais), por indivíduo de espécie não constante em listas oficiais de espécies em risco ou ameaçadas de extinção; II - R$ 5.000"},
    "26": {"tipo":'unitaria',"valores":[{"valor":200.0,"unidade":'unidade'}, {"valor":5000.0,"unidade":'unidade'}],"teto_rigido":False, "texto": "Multa de R$ 2.000,00 (dois mil reais), com acréscimo de: I - R$ 200,00 (duzentos reais), por unidade não constante em listas oficiais de espécies em risco ou ameaçadas de extinção; ou II - R$ 5.000,00 (cinco mil reais), por unidad"},
    "27": {"tipo":'unitaria',"valores":[{"valor":500.0,"unidade":'indivíduo'}, {"valor":10000.0,"unidade":'indivíduo'}],"teto_rigido":False, "texto": "Multa de R$ 5.000,00 (cinco mil reais), com acréscimo de: I - R$ 500,00 (quinhentos reais), por indivíduo capturado; ou (Redação dada pelo Decreto nº 6.686, de 2008). II - R$ 10.000,00 (dez mil reais), por indivíduo de espécie con"},
    "28": {"tipo":'unitaria',"valores":[{"valor":200.0,"unidade":'unidade'}],"teto_rigido":False, "texto": "Multa de R$ 1.000,00 (mil reais), com acréscimo de R$ 200,00 (duzentos reais), por unidade excedente."},
    "29": {"tipo":"faixa","min":1500.0,"max":50000.0,"unidade":'indivíduo',"teto_rigido":False, "texto": "Multa de R$ 1.500,00 (mil e quinhentos reais) a R$ 50.000,00 (cinquenta mil reais) por indivíduo. (Redação dada pelo Decreto nº 12.877, de 2026)"},
    "30": {"tipo":"fixa","valor":2500.0,"teto_rigido":True, "texto": "Multa de R$ 2.500,00 (dois mil e quinhentos reais)."},
    "32": {"tipo":"faixa","min":200.0,"max":10000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 200,00 (duzentos reais) a R$ 10.000,00 (dez mil reais)."},
    "33": {"tipo":"faixa","min":5000.0,"max":500000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 500.000,00 (quinhentos mil reais)."},
    "34": {"tipo":"faixa","min":5000.0,"max":500000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 500.000,00 (quinhentos mil reais)."},
    "35": {"tipo":"faixa","min":700.0,"max":100000.0,"unidade":'quilo',"teto_rigido":False, "texto": "Multa de R$ 700,00 (setecentos reais) a R$ 100.000,00 (cem mil reais), com acréscimo de R$ 20,00 (vinte reais), por quilo ou fração do produto da pescaria, ou por espécime quando se tratar de produto de pesca para uso ornamental."},
    "36": {"tipo":"faixa","min":700.0,"max":100000.0,"unidade":'quilo',"teto_rigido":False, "texto": "Multa de R$ 700,00 (setecentos reais) a R$ 100.000,00 (cem mil reais), com acréscimo de R$ 20,00 (vinte reais), por quilo ou fração do produto da pescaria."},
    "37": {"tipo":"faixa","min":300.0,"max":10000.0,"unidade":'quilo',"teto_rigido":False, "texto": "Multa de R$ 300,00 (trezentos reais) a R$ 10.000,00 (dez mil reais), com acréscimo de R$ 20,00 (vinte reais) por quilo ou fração do produto da pesca, ou por espécime quando se tratar de produto de pesca para ornamentação."},
    "38": {"tipo":"faixa","min":3000.0,"max":50000.0,"unidade":'quilo',"teto_rigido":False, "texto": "Multa de R$ 3.000,00 (três mil reais) a R$ 50.000,00 (cinqüenta mil reais), com acréscimo de R$ 20,00 (vinte reais) por quilo ou fração do produto da pescaria , ou por espécime quando se tratar de espécies aquáticas, oriundas de p"},
    "39": {"tipo":"faixa","min":500.0,"max":50000.0,"unidade":'quilo',"teto_rigido":False, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 50.000,00 (cinqüenta mil reais), com acréscimo de R$ 20,00 (vinte reais) por quilo ou espécime do produto."},
    "41": {"tipo":"fixa","valor":1000.0,"teto_rigido":True, "texto": "Multa: R$ 1.000,00 (mil reais)."},
    "43": {"tipo":"faixa","min":5000.0,"max":50000.0,"unidade":'hectare',"teto_rigido":False, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 50.000,00 (cinqüenta mil reais), por hectare ou fração."},
    "44": {"tipo":"faixa","min":5000.0,"max":20000.0,"unidade":'hectare',"teto_rigido":False, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 20.000,00 (vinte mil reais) por hectare ou fração, ou R$ 500,00 (quinhentos reais) por árvore, metro cúbico ou fração."},
    "45": {"tipo":"faixa","min":5000.0,"max":50000.0,"unidade":'hectare',"teto_rigido":False, "texto": "Multa simples de R$ 5.000,00 (cinco mil reais) a R$ 50.000,00 (cinqüenta mil reais) por hectare ou fração."},
    "46": {"tipo":'unitaria',"valores":[{"valor":500.0,"unidade":'metro cúbico'}],"teto_rigido":False, "texto": "Multa de R$ 500,00 (quinhentos reais), por metro cúbico de carvão-mdc."},
    "47": {"tipo":'unitaria',"valores":[{"valor":300.0,"unidade":'unidade'}],"teto_rigido":False, "texto": "Multa de R$ 300,00 (trezentos reais) por unidade, estéreo, quilo, mdc ou metro cúbico aferido pelo método geométrico."},
    "48": {"tipo":'unitaria',"valores":[{"valor":5000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 5.000,00 (cinco mil reais), por hectare ou fração. (Redação dada pelo Decreto nº 6.686, de 2008)."},
    "50": {"tipo":'unitaria',"valores":[{"valor":5000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 5.000,00 (cinco mil reais) por hectare ou fração."},
    "51": {"tipo":'unitaria',"valores":[{"valor":5000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 5.000,00 (cinco mil reais) por hectare ou fração."},
    "52": {"tipo":'unitaria',"valores":[{"valor":1000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 1.000,00 (mil reais) por hectare ou fração. (Redação dada pelo Decreto nº 6.686, de 2008)."},
    "53": {"tipo":'unitaria',"valores":[{"valor":300.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 300,00 (trezentos reais), por hectare ou fração, ou por unidade, estéreo, quilo, mdc ou metro cúbico."},
    "54": {"tipo":'unitaria',"valores":[{"valor":500.0,"unidade":'quilo'}],"teto_rigido":False, "texto": "Multa de R$ R$ 500,00 (quinhentos reais) por quilograma ou unidade."},
    "56": {"tipo":"faixa","min":100.0,"max":1000.0,"unidade":'unidade',"teto_rigido":False, "texto": "Multa de R$ 100,00 (cem reais) a R$1.000,00 (mil reais) por unidade ou metro quadrado."},
    "57": {"tipo":'unitaria',"valores":[{"valor":1000.0,"unidade":'unidade'}],"teto_rigido":False, "texto": "Multa de R$ 1.000,00 (mil reais), por unidade."},
    "58": {"tipo":'unitaria',"valores":[{"valor":3000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 3.000,00 (três mil reais) por hectare ou fração. (Redação dada pelo Decreto nº 12.189, de 2024)"},
    "59": {"tipo":"faixa","min":1000.0,"max":10000.0,"unidade":'unidade',"teto_rigido":False, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 10.000,00 (dez mil reais), por unidade."},
    "61": {"tipo":"faixa","min":5000.0,"max":50000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 50.000.000,00 (cinqüenta milhões de reais)."},
    "63": {"tipo":"faixa","min":1500.0,"max":3000.0,"unidade":'hectare',"teto_rigido":False, "texto": "Multa de R$ 1.500,00 (mil e quinhentos reais) a R$ 3.000,00 (três mil reais), por hectare ou fração."},
    "64": {"tipo":"faixa","min":500.0,"max":2000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 2.000.000,00 (dois milhões de reais)."},
    "65": {"tipo":"faixa","min":100000.0,"max":1000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 100.000,00 (cem mil reais) a R$ 1.000.000,00 (um milhão de reais)."},
    "66": {"tipo":"faixa","min":500.0,"max":10000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 10.000.000,00 (dez milhões de reais)."},
    "67": {"tipo":"faixa","min":5000.0,"max":5000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 5.000.000,00 (cinco milhões de reais)."},
    "68": {"tipo":"faixa","min":1000.0,"max":10000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 10.000,00 (dez mil reais)."},
    "69": {"tipo":"faixa","min":1000.0,"max":10000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 10.000.000,00 (dez milhões de reais) e correção de todas as unidades de veículo ou motor que sofrerem alterações."},
    "70": {"tipo":'unitaria',"valores":[{"valor":400.0,"unidade":'unidade'}],"teto_rigido":False, "texto": "Multa de R$ 400,00 (quatrocentos reais), por unidade."},
    "71": {"tipo":"faixa","min":500.0,"max":10000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 10.000,00 (dez mil reais), por veículo, e correção da irregularidade."},
    "72": {"tipo":"faixa","min":10000.0,"max":500000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 10.000,00 (dez mil reais) a R$ 500.000,00 (quinhentos mil reais)."},
    "73": {"tipo":"faixa","min":10000.0,"max":200000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 10.000,00 (dez mil reais) a R$ 200.000,00 (duzentos mil reais)."},
    "74": {"tipo":"faixa","min":10000.0,"max":100000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 10.000,00 (dez mil reais) a R$ 100.000,00 (cem mil reais)."},
    "75": {"tipo":"faixa","min":1000.0,"max":50000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 50.000,00 (cinqüenta mil reais)."},
    "76": {"tipo":'escalonada',"valores":[{"valor":50.0,"unidade":None}, {"valor":150.0,"unidade":None}, {"valor":900.0,"unidade":None}, {"valor":1800.0,"unidade":None}, {"valor":9000.0,"unidade":None}],"teto_rigido":False, "texto": "Multa de: I - R$ 50,00 (cinqüenta reais), se pessoa física; II - R$ 150,00 (cento e cinqüenta reais), se microempresa; III - R$ 900,00 (novecentos reais), se empresa de pequeno porte; IV - R$ 1.800,00 (mil e oitocentos reais), se "},
    "77": {"tipo":"faixa","min":500.0,"max":100000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 100.000,00 (cem mil reais)."},
    "78": {"tipo":"faixa","min":100.0,"max":300.0,"unidade":'hectare',"teto_rigido":False, "texto": "Multa de R$ 100,00 (cem reais) a R$ 300,00 (trezentos reais) por hectare do imóvel."},
    "79": {"tipo":"faixa","min":10000.0,"max":10000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 10.000,00 (dez mil reais) a R$ 10.000.000,00 (dez milhões de reais). (Redação dada pelo Decreto nº 12.189, de 2024)"},
    "80": {"tipo":"faixa","min":1000.0,"max":1000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 1.000.000,00 (um milhão de reais)."},
    "81": {"tipo":"faixa","min":1000.0,"max":100000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 100.000,00 (cem mil reais)."},
    "82": {"tipo":"faixa","min":1500.0,"max":1000000.0,"unidade":None,"teto_rigido":False, "texto": "Multa de R$ 1.500,00 (mil e quinhentos reais) a R$ 1.000.000,00 (um milhão de reais)."},
    "83": {"tipo":"faixa","min":10000.0,"max":1000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 10.000,00 (dez mil reais) a R$ 1.000.000,00 (um milhão de reais)."},
    "84": {"tipo":"faixa","min":2000.0,"max":100000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 2.000,00 (dois mil reais) a R$ 100.000,00 (cem mil reais)."},
    "85": {"tipo":"faixa","min":1500.0,"max":1000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.500,00 (mil e quinhentos reais) a R$ 1.000.000,00 (um milhão de reais)."},
    "86": {"tipo":"faixa","min":500.0,"max":10000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 10.000,00 (dez mil reais)."},
    "87": {"tipo":"faixa","min":1500.0,"max":100000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.500,00 (mil e quinhentos reais) a R$ 100.000,00 (cem mil reais)."},
    "88": {"tipo":"faixa","min":5000.0,"max":2000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 5.000,00 (cinco mil reais) a R$ 2.000.000,00 (dois milhões de reais)."},
    "89": {"tipo":"faixa","min":1500.0,"max":1000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.500,00 (mil e quinhentos reais) a R$ 1.000.000,00 (um milhão de reais)."},
    "90": {"tipo":"faixa","min":500.0,"max":10000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 10.000,00 (dez mil reais)."},
    "91": {"tipo":"faixa","min":200.0,"max":100000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 200,00 (duzentos reais) a R$ 100.000,00 (cem mil reais)."},
    "92": {"tipo":"faixa","min":1000.0,"max":10000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 1.000,00 (mil reais) a R$ 10.000,00 (dez mil reais)."},
    "51-A": {"tipo":'unitaria',"valores":[{"valor":1000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$ 1.000,00 (mil reais) por hectare ou fração. (Incluído pelo Decreto nº 6.686, de 2008)."},
    "54-A": {"tipo":'unitaria',"valores":[{"valor":500.0,"unidade":'quilo'}],"teto_rigido":False, "texto": "Multa de R$ 500,00 (quinhentos reais) por quilograma ou unidade. (Incluído pelo Decreto nº 11.080, de 2022)"},
    "58-A": {"tipo":'unitaria',"valores":[{"valor":10000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$10.000,00 (dez mil reais) por hectare ou fração. (Incluído pelo Decreto nº 12.189, de 2024)"},
    "58-B": {"tipo":'unitaria',"valores":[{"valor":5000.0,"unidade":'hectare'}],"teto_rigido":False, "texto": "Multa de R$5.000,00 (cinco mil reais) por hectare ou fração. (Incluído pelo Decreto nº 12.189, de 2024)"},
    "58-C": {"tipo":"faixa","min":5000.0,"max":10000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$5.000,00 (cinco mil reais) a R$10.000.000,00 (dez milhões de reais). (Incluído pelo Decreto nº 12.189, de 2024)"},
    "71-A": {"tipo":"faixa","min":500.0,"max":10000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 500,00 (quinhentos reais) a R$ 10.000.000,00 (dez milhões de reais). (Redação dada pelo Decreto nº 10.936, de 2022) Subseção IV Das Infrações Contra o Ordenamento Urbano e o Patrimônio Cultural"},
    "83-A": {"tipo":"faixa","min":100.0,"max":1000.0,"unidade":'quilo',"teto_rigido":False, "texto": "Multa de R$ 100,00 (cem reais) a R$ 1.000,00 (mil reais) por quilograma, hectare ou unidade de medida compatível com a mensuração do objeto da infração. (Incluído pelo Decreto nº 12.189, de 2024)"},
    "83-B": {"tipo":"faixa","min":10000.0,"max":50000000.0,"unidade":None,"teto_rigido":True, "texto": "Multa de R$ 10.000,00 (dez mil reais) a R$ 50.000.000,00 (cinquenta milhões de reais). (Incluído pelo Decreto nº 12.189, de 2024)"},
}

FONTE = ("Decreto 6.514/2008, texto compilado — Presidência da República, "
         "Casa Civil. Conferido em 17/09/2026.")


def sancao_do_artigo(artigo):
    """Devolve a sanção do artigo, ou None se ele não está na tabela."""
    return SANCOES.get(str(artigo).strip())


def teto_conclusivo(artigo):
    """
    Devolve o teto em reais SÓ quando ele é rígido; caso contrário, None.

    None aqui não quer dizer "sem limite": quer dizer que esta tabela não
    autoriza conclusão, e o assunto vira evidência para a pessoa ler.
    """
    d = SANCOES.get(str(artigo).strip())
    if not d or not d.get("teto_rigido"):
        return None
    return d.get("valor") if d["tipo"] == "fixa" else d.get("max")
