# Frontend Dockerfile for Development
FROM node:18-alpine

WORKDIR /app

# Install dependencies first for caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy source
COPY . .

# Expose Vite default port
EXPOSE 5173

# Run dev server with --host to allow external access
CMD ["npm", "run", "dev", "--", "--host"]
