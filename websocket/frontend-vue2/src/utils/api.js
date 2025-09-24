import axios from "axios";

// 自动切换后端 API 地址
// - 在容器 (K8s 内) 时，使用 Service DNS (backend:8000)
// - 在本地开发时，使用 localhost:8000
const baseURL =
  process.env.VUE_APP_BACKEND_URL || "http://localhost:8000"; 

// Axios 实例
const api = axios.create({
  baseURL,
  timeout: 5000,
});

// 统一拦截错误
api.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error("API 请求错误: ", err.message);
    return Promise.reject(err);
  }
);

export default api;
