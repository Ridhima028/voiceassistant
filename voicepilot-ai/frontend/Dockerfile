FROM node:20-alpine

WORKDIR /app

# Install dependencies first so this layer is cached between code changes.
COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
