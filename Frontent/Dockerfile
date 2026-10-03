# Build stage
FROM node:24-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
ARG VITE_CONTROL_LAYER_URL=http://localhost:8080
ARG VITE_AGENT_URL=http://localhost:8090
ARG VITE_ADMIN_TOKEN=admin-dev-token

ENV VITE_CONTROL_LAYER_URL=$VITE_CONTROL_LAYER_URL
ENV VITE_AGENT_URL=$VITE_AGENT_URL
ENV VITE_ADMIN_TOKEN=$VITE_ADMIN_TOKEN

RUN npm run build

# Nginx stage
FROM nginx:alpine

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built application
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
