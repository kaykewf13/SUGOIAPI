#!/bin/bash

echo "🚀 Iniciando configuração da SUGOIAPI..."

echo "📂 Acessando diretório do projeto..."
cd /workspaces/SUGOIAPI || exit

echo "🔄 Atualizando repositório..."
git pull origin main

echo "🐳 Parando containers antigos..."
docker compose down

echo "🐳 Construindo e iniciando os containers..."
docker compose up -d --build

echo "🧹 Limpando cache do Symfony..."
docker compose exec app php bin/console cache:clear

echo "📡 Verificando rotas..."
docker compose exec app php bin/console debug:router

echo "🔎 Testando aplicação local..."
curl -i http://localhost:1010/ | head -n 5

echo ""
echo "✅ Configuração concluída com sucesso!"
echo "🌐 Acesse a API em:"
echo "🔗 https://urban-space-guide-pjxvjggw54pwcr6g6-1010.app.github.dev/"
echo ""
echo "📺 Teste um episódio em:"
echo "🔗 https://urban-space-guide-pjxvjggw54pwcr6g6-1010.app.github.dev/episode/naruto/1/1"