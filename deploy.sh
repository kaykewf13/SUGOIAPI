#!/usr/bin/env bash
# deploy.sh — Deploy completo do SUGOIAPI
# Uso: bash deploy.sh

set -euo pipefail

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
sep()  { echo -e "\n────────────────────────────────────────"; }

# ── Verifica pré-requisitos ───────────────────────────────────────
sep
echo "🔍 Verificando pré-requisitos..."

command -v docker   &>/dev/null || fail "Docker não encontrado"
command -v git      &>/dev/null || fail "Git não encontrado"
command -v python3  &>/dev/null || fail "Python3 não encontrado"
log "Docker, Git e Python3 disponíveis"

# ── Carrega variáveis de ambiente ────────────────────────────────
sep
echo "🔧 Configurando ambiente..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn ".env criado a partir do .env.example — preencha as variáveis antes de continuar"
        echo ""
        echo "  Edite o arquivo .env e execute novamente:"
        echo "  nano .env && bash deploy.sh"
        exit 0
    else
        fail ".env não encontrado"
    fi
fi

export $(grep -v '^#' .env | xargs)
log ".env carregado"

# ── Verifica estrutura de arquivos ───────────────────────────────
sep
echo "📁 Verificando arquivos do projeto..."

REQUIRED=(pipeline.py register_streams.py requirements.txt
          docker-compose.yml Dockerfile.pipeline)

for f in "${REQUIRED[@]}"; do
    [ -f "$f" ] || fail "Arquivo ausente: $f"
done
log "Todos os arquivos presentes"

# ── Cria pasta de output ─────────────────────────────────────────
mkdir -p output
log "Diretório output/ pronto"

# ── Instala dependências Python ──────────────────────────────────
sep
echo "📦 Instalando dependências Python..."
pip install -q -r requirements.txt
log "Dependências instaladas"

# ── Sobe o m3u-proxy ─────────────────────────────────────────────
sep
echo "🚀 Iniciando m3u-proxy..."
docker compose up -d m3u-proxy
log "m3u-proxy iniciado"

# ── Aguarda proxy ficar saudável ─────────────────────────────────
echo "⏳ Aguardando proxy ficar disponível..."
TRIES=0
MAX=20
until curl -sf "http://localhost:8085/health" &>/dev/null; do
    TRIES=$((TRIES + 1))
    [ $TRIES -ge $MAX ] && fail "Proxy não respondeu em ${MAX}s"
    sleep 3
done
log "Proxy saudável em http://localhost:8085"

# ── Executa pipeline ─────────────────────────────────────────────
sep
echo "⚡ Executando pipeline (pode levar alguns minutos)..."
SENTRY_DSN="${SENTRY_DSN:-}" python3 pipeline.py
log "Pipeline concluído"

# ── Verifica playlist gerada ─────────────────────────────────────
if [ ! -f "output/playlist_validada.m3u" ]; then
    fail "Playlist não gerada — verifique os logs do pipeline"
fi

TOTAL=$(grep -c "^#EXTINF" output/playlist_validada.m3u || echo 0)
[ "$TOTAL" -lt 10 ] && warn "Playlist com apenas $TOTAL entradas — verifique as fontes"

log "Playlist gerada: $TOTAL links validados"

# ── Registra streams no proxy ─────────────────────────────────────
sep
echo "📡 Registrando streams no proxy..."
PROXY_URL="${PROXY_URL:-http://localhost:8085}" \
PROXY_API_TOKEN="${PROXY_API_TOKEN:-}" \
python3 register_streams.py
log "Streams registrados"

# ── Configura GitHub Actions (se dentro de um repo) ──────────────
sep
echo "⚙️  Configurando GitHub Actions..."

if [ -d ".git" ]; then
    mkdir -p .github/workflows
    if [ -f "pipeline.yml" ] && [ ! -f ".github/workflows/pipeline.yml" ]; then
        cp pipeline.yml .github/workflows/pipeline.yml
        log "Workflow copiado para .github/workflows/"
    else
        log "Workflow já configurado"
    fi
else
    warn "Não é um repositório Git — GitHub Actions não configurado"
fi

# ── Relatório final ───────────────────────────────────────────────
sep
echo ""
echo "  ✅ Deploy concluído com sucesso!"
echo ""

CANAIS=$(grep -c 'group-title="Canais' output/playlist_validada.m3u 2>/dev/null || echo 0)
SERIES=$(grep -c 'group-title="Series' output/playlist_validada.m3u 2>/dev/null || echo 0)
FILMES=$(grep -c 'group-title="Filmes' output/playlist_validada.m3u 2>/dev/null || echo 0)

echo "  📋 Playlist:"
echo "     Canais  → $CANAIS"
echo "     Séries  → $SERIES"
echo "     Filmes  → $FILMES"
echo "     Total   → $TOTAL"
echo ""
echo "  🌐 Endpoints:"
echo "     Proxy       → http://localhost:8085"
echo "     Streams     → http://localhost:8085/streams"
echo "     Health      → http://localhost:8085/health"
echo "     Stats       → http://localhost:8085/stats"
echo "     M3U direta  → output/playlist_validada.m3u"
echo "     M3U proxy   → output/playlist_proxy.m3u"
echo ""
echo "  📅 Agendamento:"
echo "     GitHub Actions → diariamente às 03h UTC"
echo "     Manual         → gh workflow run pipeline.yml"
echo ""

if [ -f "output/health.json" ]; then
    echo "  📊 Health report:"
    cat output/health.json | python3 -m json.tool 2>/dev/null || cat output/health.json
    echo ""
fi

sep
