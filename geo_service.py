"""
Cruzamento geoespacial contra as bases públicas do INPE (TerraBrasilis).

Fonte: WFS público do INPE — https://terrabrasilis.dpi.inpe.br/geoserver/ows
Camadas usadas:
  - DETER  (alertas quase em tempo real, satélites CBERS/Sentinel/Landsat/AWFI) — só existe para Amazônia e Cerrado.
  - PRODES (desmatamento anual consolidado, todos os 6 biomas do formulário do ATLAS-IA).

Nenhum dado aqui é inventado ou estimado: os nomes de camada e o formato dos
campos abaixo foram confirmados em ago/2026 fazendo requisições reais contra
o servidor WFS público do INPE (GetCapabilities + GetFeature), a mesma base
que alimenta o painel oficial TerraBrasilis. Não requer chave de API.

Detalhe técnico importante (e não documentado com clareza pelo INPE): o
filtro espacial CQL deste servidor WFS 2.0.0 usa ordem de eixo (latitude,
longitude) — o inverso do GeoJSON de saída, que continua (longitude,
latitude) como de costume. Isso foi confirmado empiricamente: uma consulta
com a ordem errada não dá erro, ela silenciosamente devolve zero
resultados — por isso a ordem certa está fixada nas funções abaixo.
"""
from datetime import date
from typing import Optional
import unicodedata
import httpx

WFS_BASE = "https://terrabrasilis.dpi.inpe.br/geoserver/ows"

# bioma (igual ao valor salvo em formData.bioma no IntakeTab.jsx) -> camadas WFS
BIOME_LAYERS = {
    "Amazônia":       {"deter": "deter-amz:deter_amz",            "prodes": "prodes-legal-amz:yearly_deforestation"},
    "Cerrado":        {"deter": "deter-cerrado-nb:deter_cerrado",  "prodes": "prodes-cerrado-nb:yearly_deforestation"},
    "Caatinga":       {"deter": None,                              "prodes": "prodes-caatinga-nb:yearly_deforestation"},
    "Mata Atlântica": {"deter": None,                              "prodes": "prodes-mata-atlantica-nb:yearly_deforestation"},
    "Pampa":          {"deter": None,                              "prodes": "prodes-pampa-nb:yearly_deforestation"},
    "Pantanal":       {"deter": None,                              "prodes": "prodes-pantanal-nb:yearly_deforestation"},
}

# ~0.01 grau ≈ 1,1 km no equador — tolerância para RVs com GPS impreciso.
RAIO_GRAUS_PADRAO = 0.01


def _achatar(texto: str) -> str:
    """Minúsculas, sem acento, sem espaço duplicado — só para comparar."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _chave_bioma(bruto: Optional[str]) -> Optional[str]:
    """
    Casa o nome do bioma, escrito de qualquer forma, com a chave de BIOME_LAYERS.

    Isto existe porque as duas pontas do sistema grafam o mesmo bioma de modos
    diferentes: o formulário do ATLAS-IA grava "Amazônia" com acento, enquanto a
    coluna BIOMA do CSV do IBAMA devolve "Amazonia" sem acento. Com comparação
    literal, todo caso vindo da mineração era recusado com "bioma não
    reconhecido" — ou seja, o cruzamento com satélite falhava em 100% das vezes
    justamente no fluxo automático, e o erro parecia problema de dado do IBAMA.
    """
    if not bruto:
        return None
    alvo = _achatar(bruto)
    for chave in BIOME_LAYERS:
        if _achatar(chave) == alvo:
            return chave
    return None


async def _wfs_get_features(type_name: str, lat: float, lon: float, raio_graus: float) -> list[dict]:
    bbox = f"{lat - raio_graus},{lon - raio_graus},{lat + raio_graus},{lon + raio_graus}"
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "application/json",
        "cql_filter": f"BBOX(geom,{bbox})",
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.get(WFS_BASE, params=params)
        resp.raise_for_status()
        return resp.json().get("features", [])


def _normalize_deter(feature: dict) -> dict:
    p = feature.get("properties", {})
    return {
        "fonte": "DETER",
        "classe": p.get("classname"),
        "data_imagem": p.get("view_date"),
        "satelite": p.get("satellite"),
        "sensor": p.get("sensor"),
        "municipio": p.get("municipality"),
        "uf": p.get("uf"),
        "area_km2": p.get("areamunkm") or p.get("areatotalkm"),
        "id_alerta": p.get("gid"),
    }


def _normalize_prodes(feature: dict) -> dict:
    p = feature.get("properties", {})
    return {
        "fonte": "PRODES",
        "classe": p.get("main_class"),
        "subclasse": p.get("sub_class"),
        "ano_referencia": p.get("year"),
        "data_imagem": p.get("image_date"),
        "satelite": p.get("satellite"),
        "sensor": p.get("sensor"),
        "uf": p.get("state"),
        "area_km2": p.get("area_km"),
        "id_alerta": p.get("uuid") or p.get("fid"),
    }


async def verificar_coordenada(
    lat: float,
    lon: float,
    bioma: str,
    data_fato: Optional[date] = None,
    raio_graus: float = RAIO_GRAUS_PADRAO,
) -> dict:
    """
    Consulta DETER + PRODES para uma coordenada e devolve todos os alertas de
    desmatamento oficiais que caem dentro do raio de tolerância informado.

    Não emite parecer jurídico nem conclusão de "nulidade confirmada" — só
    devolve o dado bruto e oficial, com uma nota factual de compatibilidade
    de data. A leitura jurídica continua sendo do advogado responsável pelo
    caso (mesma fronteira já adotada no restante do ATLAS-IA e do AGROTAX).
    """
    bioma = _chave_bioma(bioma)
    if not bioma:
        return {
            "ok": False,
            "erro": f"Bioma não reconhecido. Valores aceitos: {list(BIOME_LAYERS.keys())}",
        }
    layers = BIOME_LAYERS[bioma]

    alertas: list[dict] = []
    avisos: list[str] = []

    if layers["deter"]:
        try:
            feats = await _wfs_get_features(layers["deter"], lat, lon, raio_graus)
            alertas += [_normalize_deter(f) for f in feats]
        except httpx.HTTPError as e:
            avisos.append(f"DETER indisponível no momento da consulta: {e}")
    else:
        avisos.append(f"DETER (tempo quase real) não existe para o bioma {bioma} — só PRODES anual está disponível.")

    try:
        feats = await _wfs_get_features(layers["prodes"], lat, lon, raio_graus)
        alertas += [_normalize_prodes(f) for f in feats]
    except httpx.HTTPError as e:
        avisos.append(f"PRODES indisponível no momento da consulta: {e}")

    alertas.sort(key=lambda a: a.get("data_imagem") or a.get("ano_referencia") or "", reverse=True)

    nota_data = None
    if data_fato and alertas:
        datas_alerta = [a["data_imagem"] for a in alertas if a.get("data_imagem")]
        if datas_alerta:
            compativel = any(
                abs((date.fromisoformat(d) - data_fato).days) <= 60
                for d in datas_alerta
                if d
            )
            nota_data = (
                "Há alerta oficial de satélite dentro de 60 dias da data do fato informada."
                if compativel else
                "Nenhum alerta oficial cai dentro de 60 dias da data do fato informada — "
                "vale conferir se a autuação tem lastro em imagem da própria data alegada."
            )

    return {
        "ok": True,
        "coordenada_consultada": {"lat": lat, "lon": lon},
        "raio_graus": raio_graus,
        "bioma": bioma,
        "total_alertas": len(alertas),
        "alertas": alertas,
        "nota_compatibilidade_data": nota_data,
        "avisos": avisos,
        "fonte": "INPE TerraBrasilis (DETER + PRODES) — https://terrabrasilis.dpi.inpe.br",
    }
