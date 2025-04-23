// 代理配置：国内环境需要配置
const PROXY_ENABLE = false; // 是否启用代理
const PROXY_HOST = "127.0.0.1";
const PROXY_PROTOCOL = "http";
const PROXY_PORT =  "1087";

export const PROXY_CONFIG = {
    enable: PROXY_ENABLE,
    protocol: PROXY_PROTOCOL,
    host: PROXY_HOST,
    port: PROXY_PORT,
}
