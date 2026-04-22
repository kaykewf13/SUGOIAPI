# SUGOIAPI

Pipeline automatizado de geração de playlists IPTV com validação de links reais,
classificação por categoria e entrega via proxy com failover.

---

## Estrutura

```
SUGOIAPI/
├── .github/
│   └── workflows/
│       └── pipeline.yml        # GitHub Actions — execução diária
├── output/                     # Gerado automaticamente
│   ├── playlist_validada.m3u   # Playlist com links reais validados
│   ├── playlist_proxy.m3u      # Playlist servida via proxy
│   └── health.json             # Relatório de saúde
├── pipeline.py                 # Varredura + validação + classificação
├── register_streams.py         # Integração com m3u-proxy
├── docker-compose.yml          # Stack completa
├── Dockerfile.pipeline         # Container do pipeline
├── requirements.txt            # Dependências Python
├── deploy.sh                   # Script de deploy automatizado
├── .env.example                # Variáveis de ambiente
└── fontes_manuais.txt          # Fontes adicionais
```

---

## Fontes

| Fonte | Grupo |
|---|---|
| `Free-TV/IPTV` (filtro BR) | Canais Brasil |
| `DrewLive-1/JapanTV.m3u8` | Canais JP |
| `DrewLive-1/DrewLiveVOD.m3u8` | Séries + Filmes |
| `DrewLive-1/PlutoTV.m3u8` | Canais + VOD |
| `DrewLive-1/TubiTV.m3u8` | Séries + Filmes |
| `L3uS-IPTV/Animes` | Séries anime |
| `Iptv-Animes/AutoUpdate` | Séries anime |
| `HerbertHe/jp.m3u` | Canais JP |
| Varredura `kaykewf13/SUGOIAPI` | Todos |

Filtro: apenas conteúdo com áudio ou legenda em **português (PT-BR / PT-PT)**.

---

## Classificação

```
Canais
  └── Brasil | Geral

Séries
  └── Shounen | Shoujo | Seinen | Josei | Isekai | Mecha
      Terror e Suspense | Psicologico | Romance | Slice of Life
      Acao e Aventura | Esportes | Fantasia | Sci-Fi | Sobrenatural
      Historico | Musica e Idols | Comedia | Clasicos
      Ecchi e Harem | Dublado | Legendado

Filmes
  └── Acao | Aventura | Romance | Terror | Sci-Fi
      Fantasia | Comedia | Ghibli | Geral
```

---

## Deploy rápido

```bash
# 1. Clone
git clone https://github.com/kaykewf13/SUGOIAPI.git
cd SUGOIAPI

# 2. Configure variáveis
cp .env.example .env
nano .env

# 3. Deploy completo
bash deploy.sh
```

---

## Deploy manual

```bash
# Dependências
pip install -r requirements.txt

# Proxy
docker compose up -d m3u-proxy

# Pipeline
python pipeline.py

# Integração
python register_streams.py
```

---

## Endpoints após deploy

| Endpoint | Descrição |
|---|---|
| `http://localhost:8085/health` | Status do proxy |
| `http://localhost:8085/streams` | Streams registrados |
| `http://localhost:8085/stats` | Estatísticas em tempo real |
| `output/playlist_validada.m3u` | Playlist com links diretos |
| `output/playlist_proxy.m3u` | Playlist via proxy com failover |

---

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `SENTRY_DSN` | DSN do Sentry para monitoramento |
| `PROXY_URL` | URL do m3u-proxy |
| `PROXY_API_TOKEN` | Token de autenticação do proxy |

---

## GitHub Actions Secrets

Configure em `Settings → Secrets → Actions`:

- `SENTRY_DSN`
- `PROXY_URL`
- `PROXY_API_TOKEN`

O pipeline executa automaticamente todos os dias às **03h UTC**.

---

## Fluxo

```
GitHub Actions (03h UTC)
        ↓
  pipeline.py
  ├── Varre repositório completo
  ├── Puxa fontes externas
  ├── Filtra PT-BR / PT-PT
  ├── Valida links reais em paralelo
  └── Gera playlist_validada.m3u
        ↓
  register_streams.py
  ├── Limpa streams anteriores
  ├── Agrupa por título → failover
  ├── Registra no m3u-proxy
  └── Gera playlist_proxy.m3u
        ↓
  m3u-proxy :8085
  ├── Failover < 100ms
  ├── Health check contínuo
  └── EPG integrado
        ↓
  m3u-tv / VLC / IPTV Smarters
```

---

## Disclaimer

Este projeto não hospeda nenhum conteúdo. Apenas agrega e organiza links
de fontes públicas disponíveis na internet. Se algum link for de sua propriedade
e desejar removê-lo, entre em contato.
