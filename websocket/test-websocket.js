// Node.js环境的WebSocket测试脚本
const WebSocket = require('ws');

// 连接到后端WebSocket服务
const wsUrl = 'ws://localhost:8000/ws/data/';
const ws = new WebSocket(wsUrl);

// 连接成功处理
ws.on('open', function() {
  console.log('WebSocket连接已建立');
  
  // 发送测试请求数据
  const testData = JSON.stringify({
    progress: 45,
    window_sec: 15
  });
  
  ws.send(testData);
  console.log('测试数据已发送:', testData);
});

// 接收后端响应
ws.on('message', function(data) {
  try {
    const response = JSON.parse(data);
    console.log('收到后端响应:', response);
    
    if (response.type === 'data') {
      console.log('当前点数据:', response.payload.point);
      console.log('窗口数据:', response.payload.series);
    }
  } catch (e) {
    console.error('解析响应失败:', e);
  }
});

// 连接关闭处理
ws.on('close', function() {
  console.log('WebSocket连接已关闭');
});

// 连接错误处理
ws.on('error', function(error) {
  console.error('WebSocket连接错误:', error);
});