<template>
  <div class="wrap">
    <h2>WebSocket 实时进度演示</h2>

    <div class="row">
      <label>进度：</label>
      <input type="range" min="0" max="100" v-model.number="percent" @input="sendPercent" />
      <span class="label">{{ percent }}%</span>
      <button @click="togglePlay">{{ playing ? "暂停" : "播放" }}</button>
    </div>

    <div class="row">
      <label>窗口（秒）</label>
      <input type="number" v-model.number="windowSec" min="1" max="120" @change="sendPercent" />
      <span class="status" :class="{ on: connected }">{{ connected ? "WS已连接" : "WS未连接" }}</span>
    </div>

    <div class="panel">
      <h3>当前点</h3>
      <pre>{{ point | pretty }}</pre>
    </div>

    <div class="panel">
      <h3>窗口数据（{{windowSec}}s）</h3>
      <pre>{{ series | pretty }}</pre>
    </div>

      <div slot="header" class="header">
        <div class="icon" />
        <span class="word">方案列表</span>
      </div>
      <div>
    <el-table
    :data="tableData"
    style="width: 100%"
    :row-style="setFirstRowStyle">
    <el-table-column
      label="ID"
      prop="id">
    </el-table-column>
    <el-table-column
      label="方案名称"
      prop="name">
    </el-table-column>

    <el-table-column
      label="涉及行业"
      prop="industry"

      >
    </el-table-column>
     <el-table-column
      label="致效程度"
      prop="parameter"
      >
    </el-table-column>




  </el-table>
      </div>


  </div>

</template>

<script>
import { connectWS } from "./ws";

export default {
  data() {
    return {
      ws: null,
      connected: false,
      percent: 0,
      windowSec: 10,
      playing: false,
      tick: null,
      point: null,
      series: [],
      wsError: null, // 添加错误信息字段
           /*sse-start*/
    eventSource: null,
    tableData: [],
    retryCount: 0,
    maxRetries: 5,
    reconnectTimer: null,
    loading: false,
    };
  },
  filters: {
    pretty(v){ return JSON.stringify(v, null, 2); }
  },
  created() {
    // 在 K8s/Ingress 下：ws(s)://<host>/ws/data/
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    // 修改为使用当前主机和Ingress配置的路径
    const url = `${proto}://${window.location.host}/ws/data/`;
    console.log(`[Frontend] 尝试连接 WebSocket: ${url}`);
    this.ws = connectWS(url, {
      onOpen: () => { 
        console.log(`[Frontend] WebSocket 连接已建立`);
        this.connected = true; 
        this.wsError = null; // 连接成功时清空错误
        this.sendPercent(); 
      },
      onClose: () => { 
        console.log(`[Frontend] WebSocket 连接已关闭`);
        this.connected = false; 
        // 如果有错误信息，保留显示；否则显示连接关闭
        if (!this.wsError) {
          this.wsError = "WebSocket 连接已关闭";
        }
      },
      onMessage: (msg) => {
        console.log(`[Frontend] 收到服务器消息:`, msg);
        
        // 修改消息处理逻辑，适配后端返回的数据格式
        if (typeof msg === 'object') {
          // 检查是否是后端返回的错误消息
          if (msg.error) {
            console.error("[Frontend] 服务器错误:", msg.error);
            this.wsError = `服务器错误: ${msg.error}`;
            return;
          }
          
          // 处理后端返回的数据格式
          if (msg.data && Array.isArray(msg.data)) {
            // 从data数组中提取当前点和窗口数据
            this.series = msg.data;
            // 取最后一个数据点作为当前点
            this.point = msg.data.length > 0 ? msg.data[msg.data.length - 1] : null;
            console.log(`[Frontend] 更新数据 - 当前点:`, this.point, `窗口数据点数:`, this.series.length);
          } else {
            console.warn(`[Frontend] 未找到有效的数据字段:`, msg);
          }
        } else {
          console.error(`[Frontend] 接收到非对象格式的消息:`, msg);
        }
      },
      onError: (error) => { // 添加错误处理回调
        console.error("[Frontend] WebSocket 连接错误:", error);
        // 根据错误事件类型提供更具体的错误信息
        let errorMsg = "WebSocket 连接失败";
        if (error.code === 1006) {
          errorMsg = "连接被意外关闭，请检查网络或服务器状态";
        } else if (error.message) {
          errorMsg = `连接错误: ${error.message}`;
        }
        this.wsError = errorMsg;
      }
    });
  },
  mounted() {
  this.initSSE();
},

  beforeDestroy() {
    console.log(`[Frontend] 组件即将销毁，清理资源`);
    if (this.tick) clearInterval(this.tick);
    if (this.ws) this.ws.close();
     /*sse-start*/
     this.closeSSE();
  if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
  /*sse-end*/

  },
  methods: {
    sendPercent() {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        console.log(`[Frontend] WebSocket 未连接，无法发送数据`);
        return;
      }
      const data = {
        progress: this.percent,
        window_sec: this.windowSec
      };
      console.log(`[Frontend] 发送进度数据:`, data);
      this.ws.send(JSON.stringify(data));
    },
    togglePlay() {
      this.playing = !this.playing;
      console.log(`[Frontend] 切换播放状态: ${this.playing ? '播放' : '暂停'}`);
      if (this.playing) {
        this.tick = setInterval(() => {
          this.percent = (this.percent + 1) % 101;
          this.sendPercent();
        }, 1000);
      } else {
        if (this.tick) clearInterval(this.tick);
        this.tick = null;
      }
    },
     // 初始化SSE连接

/*SSE--start*/
  normalizeIndustry(ind) {
    if (Array.isArray(ind)) return ind.join(','); //// “电力、交通”
    return ind || '';
  },
    //统一行合并：把 industry/efficiencylevels 规范化，避免显示异常
  normalizeRow(row) {
    const r = { ...row };
    r.industry = this.normalizeIndustry(r.industry);
    // 可选：数字转百分比/保留小数
    // if (typeof r.efficiencylevels === 'number') r.efficiencylevels = (r.efficiencylevels * 100).toFixed(1) + '%';
    return r;
  },
 initSSE() {
    try {
      if (this.eventSource) this.closeSSE();
      this.loading = true;

      this.eventSource = new EventSource('http://127.0.0.1:8000/api/solutions/sse');

      this.eventSource.onopen = () => {
        this.retryCount = 0;
        this.loading = false;
      };

      // 默认消息（如果后端用默认 event）
      this.eventSource.onmessage = (event) => {
        // 可按需：把默认消息当作全量快照
        try {
          const data = JSON.parse(event.data);
          if (Array.isArray(data)) {
            this.tableData = data.map(this.normalizeRow);
          }
        } catch (_) {}
      };

      // 全量快照
      this.eventSource.addEventListener('solutions', (event) => {
        try {
          const list = JSON.parse(event.data);
          if (Array.isArray(list)) {
            this.tableData = list.map(this.normalizeRow);
          }
        } catch (_) {}
      });

      // 增量变化
      // this.eventSource.addEventListener('solution', (event) => {
      //   try {
      //     const { type, payload } = JSON.parse(event.data) || {};
      //     if (!type) return;

      //     if (type === 'add' && payload) {
      //       this.tableData.unshift(this.normalizeRow(payload));
      //     } else if (type === 'update' && payload && payload.id != null) {
      //       const idx = this.tableData.findIndex(r => r.id === payload.id);
      //       if (idx !== -1) {
      //         const merged = this.normalizeRow({ ...this.tableData[idx], ...payload });
      //         this.$set(this.tableData, idx, merged);
      //       }
      //     } else if (type === 'delete' && payload && payload.id != null) {
      //       this.tableData = this.tableData.filter(r => r.id !== payload.id);
      //     }
      //   } catch (_) {}
      // });

      // 心跳可忽略
      this.eventSource.addEventListener('ping', () => {});

      this.eventSource.onerror = () => {
        this.loading = false;
        if (!this.eventSource) return;
        const state = this.eventSource.readyState; // 0 CONNECTING, 1 OPEN, 2 CLOSED
        if (state === 2 || state === 0) {
          if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            const delay = 3000 * this.retryCount + Math.floor(Math.random() * 800);
            if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
            this.reconnectTimer = setTimeout(() => {
              this.closeSSE();
              this.initSSE();
            }, delay);
          } else {
            this.closeSSE();
            // 这里可提示用户或降级到轮询
          }
        }
      };
    } catch (e) {
      this.loading = false;
    }
  },

 closeSSE() {
    if (this.eventSource) {
      try { this.eventSource.close(); } catch (_) {}
      this.eventSource = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  },

  reconnectSSE() {
    this.closeSSE();
    this.retryCount = 0;
    this.initSSE();
  },
  }
};
</script>


<style>
.wrap { max-width: 900px; margin: 24px auto; font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial; }
.row { display:flex; align-items:center; gap:12px; margin:12px 0; }
.label { width:60px; text-align:right; }
.panel { background:#f7f7f8; border:1px solid #e5e7eb; padding:12px; border-radius:8px; margin-top:12px; }
.status { padding:2px 8px; border-radius:12px; background:#eee; }
.status.on { background:#d1fae5; }
button { padding:6px 12px; cursor:pointer; }
.error-message { color:#dc2626; background:#fee2e2; padding:8px 12px; border-radius:4px; margin:8px 0; font-size:14px; }

.el-card {
  background-color: rgba(0,0,0,0);
  margin-bottom: 24px;
  border: 0px;
  background-repeat: no-repeat;
  background-size: 100%,100%;
  .el-card__header {
    padding: 0px;
    height:35px;
    border: 0px;
    text-align: left; /* Added to align header content left */
  }
  .el-card__body {
    padding: 0px;
  }
}
.header {
  position: relative;
  height: 100%;
  margin: 0;
  padding: 0px;
  border: 0px;
  font-family: "youshebiaotihei";
  color: #fff;
  text-align: left; /* Added to align header content left */
  .icon {
    position: relative;
    top: 4px;
    margin-left: 0; /* Changed from 24px to 0 */
    margin-right: 8px;
    width: 10px;
    float: left;
    height:100%;
    background-position: center;
    background-repeat: no-repeat;
  }
  .word {
    position: relative;
    top: 7px;
    float: left; /* Added to keep text aligned with icon */
  }
}
.el-table {
  background-color: transparent !important;
  color: #fff
}
.el-table th,
.el-table tr {
  background-color: transparent !important;
}

.el-table--enable-row-hover .el-table__body tr:hover>td {
  background-color: rgba(255, 255, 255, 0.1) !important;
}
</style>
