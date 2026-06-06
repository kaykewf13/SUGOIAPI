# Consumet API — Dockerfile para Railway / Render
FROM node:20-alpine

WORKDIR /app

# Clona um fork acessível do Consumet API na build
RUN apk add --no-cache git && \
    git clone https://github.com/riimuru/consumet-api.git . && \
    npm install

# Variáveis de ambiente de produção
ENV NODE_ENV=PROD
ENV PORT=3000

# Porta exposta (Railway injeta $PORT automaticamente)
EXPOSE 3000

# Inicia o servidor
CMD ["npm", "start"]
