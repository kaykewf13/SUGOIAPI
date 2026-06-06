# Consumet API — Dockerfile para Railway / Render
# Base no fork oficial: https://github.com/consumet/api.consumet.org
FROM node:20-alpine

WORKDIR /app

# Clona o repositório oficial do Consumet na build
RUN apk add --no-cache git && \
    git clone https://github.com/consumet/api.consumet.org.git . && \
    npm install

# Variáveis de ambiente de produção
ENV NODE_ENV=PROD
ENV PORT=3000

# Porta exposta (Railway injeta $PORT automaticamente)
EXPOSE 3000

# Inicia o servidor
CMD ["npm", "start"]
