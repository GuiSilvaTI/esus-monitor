#!/usr/bin/env python3
"""
Monitor de atualizações e-SUS PEC
Verifica se saiu versão nova e envia notificação via ntfy.sh
"""

import re
import sys
import os
import urllib.request
import urllib.error

URL_ESUS = "https://sisaps.saude.gov.br/sistemas/esusaps/"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "esus-pec-monitor")  # mude para o seu tópico
VERSION_FILE = "ultima_versao.txt"


def versao_valida(v):
    """Verifica se o número de versão é plausível para o e-SUS PEC."""
    partes = v.split(".")
    if len(partes) < 2:
        return False
    try:
        maior = int(partes[0])
        menor = int(partes[1])
        # e-SUS PEC: versão maior entre 3 e 15, menor entre 0 e 99
        return 3 <= maior <= 15 and 0 <= menor <= 99
    except ValueError:
        return False


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

    # Prioridade 1: botão de download (mais confiável)
    # Ex: "Download Versão 5.4.36"
    padrao1 = r"Download\s+Vers[aã]o\s+(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)"
    match = re.search(padrao1, html, re.IGNORECASE)
    if match and versao_valida(match.group(1)):
        print(f"  → versão encontrada no botão de download")
        return match.group(1)

    # Prioridade 2: texto "Versão X.X.X" próximo de palavras-chave do e-SUS
    # Busca dentro de um contexto relevante para evitar pegar JS de terceiros
    for trecho in re.finditer(r"(?:esus|pec|aps|sus).{0,200}", html, re.IGNORECASE):
        m = re.search(r"(\d+\.\d+\.\d+)", trecho.group())
        if m and versao_valida(m.group(1)):
            print(f"  → versão encontrada no contexto e-SUS")
            return m.group(1)

    # Prioridade 3: "Versão X.X.X" genérico, mas com validação estrita
    padrao3 = r"[Vv]ers[aã]o\s+(\d+\.\d+(?:\.\d+)?)"
    for m in re.finditer(padrao3, html):
        v = m.group(1)
        if versao_valida(v):
            print(f"  → versão encontrada via texto 'Versão'")
            return v

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
    """Envia push notification via ntfy.sh usando headers HTTP."""
    url = f"https://ntfy.sh/{NTFY_TOPIC}"

    if versao_anterior:
        titulo = "🏥 e-SUS PEC: nova versão disponível!"
        mensagem = f"🆕 Versão {versao_nova} disponível! (anterior: {versao_anterior})"
    else:
        titulo = "✅ e-SUS PEC monitorado"
        mensagem = f"Versão atual: {versao_nova}. Vou avisar quando sair novidade!"

    req = urllib.request.Request(
        url,
        data=mensagem.encode("utf-8"),
        headers={
            "Title": titulo.encode("utf-8"),
            "Priority": "4",
            "Tags": "hospital,white_check_mark",
            "Click": URL_ESUS,
        },
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
