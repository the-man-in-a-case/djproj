# FROM node:alpine3.22 AS build
# WORKDIR /app
# # COPY package.json package-lock.json* ./
# # RUN npm ci --no-audit --no-fund
# COPY package.json ./
# # 将 npm ci 改为 npm install
# RUN npm install --no-audit --no-fund
# COPY . .
# RUN npm run build

# FROM nginx:alpine
# COPY nginx.conf /etc/nginx/nginx.conf
# COPY --from=build /app/dist/ /usr/share/nginx/html/
# EXPOSE 80
# 使用 node 构建和运行
FROM node:alpine3.22

# 工作目录
WORKDIR /app

# 复制 package.json 和 lock 文件
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制源码
COPY . .

# 运行开发服务
EXPOSE 8080
# CMD ["npm", "run", "serve"]
CMD ["tail", "-f", "/dev/null"]
