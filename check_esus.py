#!/usr/bin/env python3
"""
Monitor de atualizações e-SUS PEC
Verifica se saiu versão nova e envia notificação via ntfy.sh
"""

import re
import sys
import json
import os
import urllib.request
import urllib.error

URL_ESUS = "https://sisaps.saude.gov.br/sistemas/esusaps/"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "esus-mococa")  # mude para o seu tópico
VERSION_FILE = "ultima_versao.txt"


def buscar_versao_atual():
    """Acessa o site do e-SUS e extrai a versão atual."""
    req = urllib.request.Request(
        URL_ESUS,
        headers={"User-Agent": "Mozilla/5.0 (compatible; esus-monitor/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as e:
        print(f"Erro ao acessar o site: {e}")
        sys.exit(1)

    # Procura padrões como "Versão 5.4.36", "Version 5.4.36", "v5.4.36"
    padrao = r"[Vv]ers[aã]o\s+(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)"
    match = re.search(padrao, html)
    if match:
        return match.group(1)

    # Fallback: procura no botão de download
    padrao2 = r"Download\s+Vers[aã]o\s+(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)"
    match2 = re.search(padrao2, html)
    if match2:
        return match2.group(1)

    # Último fallback: qualquer número de versão no HTML
    padrao3 = r"(\d+\.\d+\.\d+)"
    matches = re.findall(padrao3, html)
    # Filtra versões plausíveis do e-SUS (começa com 4, 5, 6...)
    versoes = [v for v in matches if v.startswith(("4.", "5.", "6.", "7."))]
    if versoes:
        return versoes[0]

    return None


def ler_versao_salva():
    """Lê a última versão conhecida do arquivo."""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    return None


def salvar_versao(versao):
    """Salva a versão atual no arquivo."""
    with open(VERSION_FILE, "w") as f:
        f.write(versao)


def enviar_notificacao(versao_nova, versao_anterior):
    """Envia push notification via ntfy.sh."""
    url = f"https://ntfy.sh/{NTFY_TOPIC}"

    if versao_anterior:
        titulo = f"🏥 e-SUS PEC atualizado: v{versao_nova}"
        mensagem = f"Nova versão disponível: {versao_nova}\nAnterior: {versao_anterior}\n\nBaixe em: {URL_ESUS}"
    else:
        titulo = f"🏥 e-SUS PEC monitorado: v{versao_nova}"
        mensagem = f"Monitoramento iniciado. Versão atual: {versao_nova}"

    dados = json.dumps({
        "topic": NTFY_TOPIC,
        "title": titulo,
        "message": mensagem,
        "priority": 4,
        "tags": ["hospital", "update"],
        "actions": [{
            "action": "view",
            "label": "Abrir site e-SUS",
            "url": URL_ESUS
        }]
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=dados,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Notificação enviada! Status: {resp.status}")
    except urllib.error.URLError as e:
        print(f"Erro ao enviar notificação: {e}")
        sys.exit(1)


def main():
    print(f"Verificando atualizações em: {URL_ESUS}")

    versao_atual = "99.99.99"
    if not versao_atual:
        print("ERRO: Não foi possível encontrar a versão no site.")
        sys.exit(1)

    print(f"Versão encontrada no site: {versao_atual}")

    versao_salva = ler_versao_salva()
    print(f"Última versão conhecida: {versao_salva or 'nenhuma'}")

    if versao_salva is None:
        # Primeira execução — salva e notifica que começou a monitorar
        print("Primeira execução. Salvando versão e notificando...")
        salvar_versao(versao_atual)
        enviar_notificacao(versao_atual, None)

    elif versao_atual != versao_salva:
        # Nova versão detectada!
        print(f"NOVA VERSÃO DETECTADA: {versao_salva} → {versao_atual}")
        salvar_versao(versao_atual)
        enviar_notificacao(versao_atual, versao_salva)

    else:
        print(f"Sem novidades. Versão {versao_atual} já conhecida.")


if __name__ == "__main__":
    main()
