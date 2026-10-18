import os
import sys
import requests
import folium
from folium.plugins import Fullscreen

BASE_URL = "https://api.olhovivo.sptrans.com.br/v2.1"

TOKEN = os.getenv("SPTRANS_TOKEN", "").strip()

if not TOKEN:
    TOKEN = input("Digite seu token da API SPTrans: ").strip()

session = requests.Session()
session.headers.update({"Accept": "application/json"})


def chamar_api(endpoint, params=None, method="GET"):
    url = f"{BASE_URL}/{endpoint}"

    try:
        if method == "POST":
            resposta = session.post(
                url,
                params=params,
                timeout=30
            )
        else:
            resposta = session.get(
                url,
                params=params,
                timeout=30
            )

        resposta.raise_for_status()

        if not resposta.text.strip():
            return None

        return resposta.json()

    except requests.RequestException as erro:
        print(f"Erro na API ({endpoint}): {erro}")
        return None


def autenticar():
    resposta = session.post(
        f"{BASE_URL}/Login/Autenticar",
        params={"token": TOKEN},
        timeout=30
    )

    resposta.raise_for_status()

    if resposta.text.strip().lower() != "true":
        raise RuntimeError(
            "Autenticacao recusada. Verifique seu token SPTrans."
        )

    print("Autenticacao realizada com sucesso!")


def buscar_linhas(termo):
    dados = chamar_api(
        "Linha/Buscar",
        params={"termosBusca": termo}
    )

    return dados if isinstance(dados, list) else []


def buscar_paradas(termo):
    dados = chamar_api(
        "Parada/Buscar",
        params={"termosBusca": termo}
    )

    return dados if isinstance(dados, list) else []


def buscar_posicoes(codigo_linha):
    dados = chamar_api(
        "Posicao/Linha",
        params={"codigoLinha": codigo_linha}
    )

    if not isinstance(dados, dict):
        return []

    onibus = []

    for linha in dados.get("vs", []):
        latitude = linha.get("py")
        longitude = linha.get("px")

        if latitude is None or longitude is None:
            continue

        onibus.append({
            "prefixo": linha.get("p", "Não informado"),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "acessivel": linha.get("a", False),
            "horario": linha.get("ta", "")
        })

    return onibus


def criar_mapa(paradas, onibus, nome_arquivo="mapa_onibus.html"):
    coordenadas = []

    for parada in paradas:
        if parada.get("py") is not None and parada.get("px") is not None:
            coordenadas.append((
                float(parada["py"]),
                float(parada["px"])
            ))

    for veiculo in onibus:
        coordenadas.append((
            veiculo["latitude"],
            veiculo["longitude"]
        ))

    if not coordenadas:
        print("Nenhuma coordenada encontrada para criar o mapa.")
        return

    centro_lat = sum(p[0] for p in coordenadas) / len(coordenadas)
    centro_lon = sum(p[1] for p in coordenadas) / len(coordenadas)

    mapa = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=13,
        control_scale=True
    )

    grupo_paradas = folium.FeatureGroup(
        name="Paradas de ônibus",
        show=True
    )

    grupo_onibus = folium.FeatureGroup(
        name="Ônibus em tempo real",
        show=True
    )

    for parada in paradas:
        latitude = parada.get("py")
        longitude = parada.get("px")

        if latitude is None or longitude is None:
            continue

        nome = parada.get("np", "Parada sem nome")
        codigo = parada.get("cp", "N/A")
        endereco = parada.get("ed", "Endereço não informado")

        folium.Marker(
            location=[float(latitude), float(longitude)],
            tooltip=f"Parada: {nome}",
            popup=(
                f"<b>Parada:</b> {nome}<br>"
                f"<b>Código:</b> {codigo}<br>"
                f"<b>Endereço:</b> {endereco}"
            ),
            icon=folium.Icon(
                color="blue",
                icon="info-sign"
            )
        ).add_to(grupo_paradas)

    for veiculo in onibus:
        acessivel = (
            "Sim" if veiculo["acessivel"] else "Não"
        )

        folium.Marker(
            location=[
                veiculo["latitude"],
                veiculo["longitude"]
            ],
            tooltip=f"Ônibus {veiculo['prefixo']}",
            popup=(
                f"<b>Prefixo:</b> {veiculo['prefixo']}<br>"
                f"<b>Horário:</b> {veiculo['horario']}<br>"
                f"<b>Acessível:</b> {acessivel}"
            ),
            icon=folium.Icon(
                color="red",
                icon="bus",
                prefix="fa"
            )
        ).add_to(grupo_onibus)

    grupo_paradas.add_to(mapa)
    grupo_onibus.add_to(mapa)

    folium.LayerControl().add_to(mapa)
    Fullscreen().add_to(mapa)

    mapa.fit_bounds(coordenadas)
    mapa.save(nome_arquivo)

    print(f"\nMapa salvo em: {nome_arquivo}")
    print(f"Total de paradas: {len(paradas)}")
    print(f"Total de ônibus encontrados: {len(onibus)}")


def main():
    if not TOKEN:
        print("Token não informado.")
        sys.exit(1)

    try:
        autenticar()
    except (requests.RequestException, RuntimeError) as erro:
        print(f"Falha na autenticação: {erro}")
        sys.exit(1)

    termo_linha = input(
        "\nDigite o número ou nome da linha de ônibus: "
    ).strip()

    linhas = buscar_linhas(termo_linha)

    if not linhas:
        print("Nenhuma linha encontrada.")
        sys.exit(1)

    print("\nLinhas encontradas:")

    for indice, linha in enumerate(linhas):
        print(
            f"{indice + 1}. {linha.get('lt', '?')} - "
            f"{linha.get('tp', '')} / {linha.get('ts', '')} "
            f"(código: {linha.get('cl')})"
        )

    try:
        escolha = int(input("\nEscolha o número da linha: "))

        if escolha < 1 or escolha > len(linhas):
            raise ValueError

    except ValueError:
        print("Escolha inválida.")
        sys.exit(1)

    linha = linhas[escolha - 1]
    codigo_linha = linha["cl"]

    print(
        f"\nLinha selecionada: {linha.get('lt', '')} "
        f"(código {codigo_linha})"
    )

    termo_parada = input(
        "Digite um bairro, rua ou local para buscar paradas: "
    ).strip()

    paradas = buscar_paradas(termo_parada)

    print(f"Paradas encontradas: {len(paradas)}")

    onibus = buscar_posicoes(codigo_linha)

    print(f"Ônibus em circulação encontrados: {len(onibus)}")

    criar_mapa(paradas, onibus)


if __name__ == "__main__":
    main()