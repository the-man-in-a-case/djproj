// 创建WebSocket连接
const proto = window.location.protocol === "https:" ? "wss" : "ws";
const wsUrl = `${proto}://${window.location.host}/ws/data/`;
const ws = new WebSocket(wsUrl);

// 连接成功处理
ws.onopen = function() {
  console.log('WebSocket连接已建立');
  
  // 发送测试请求数据
  const testData = JSON.stringify({
    progress: 45,           // 进度百分比值(0-100)
    window_sec: 15          // 时间窗口大小(秒)
  });
  
  ws.send(testData);
  console.log('测试数据已发送:', testData);
};

// 接收后端响应
ws.onmessage = function(event) {
  try {
    const response = JSON.parse(event.data);
    console.log('收到后端响应:', response);
    
    // 这里可以根据实际的响应格式进行处理
    if (response.type === 'data') {
      console.log('当前点数据:', response.payload.point);
      console.log('窗口数据:', response.payload.series);
    }
  } catch (e) {
    console.error('解析响应失败:', e);
  }
};

// 连接关闭处理
ws.onclose = function() {
  console.log('WebSocket连接已关闭');
};

// 连接错误处理
ws.onerror = function(error) {
  console.error('WebSocket连接错误:', error);
};

// 如需手动断开连接
// ws.close();