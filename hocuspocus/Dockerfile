FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install --production

COPY server.js ./

EXPOSE 1234

CMD ["node", "server.js"]
