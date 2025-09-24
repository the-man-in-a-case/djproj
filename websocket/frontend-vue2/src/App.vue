<template>
  <div class="wrap">
    <h2>WebSocket 实时进度演示</h2>

    <section class="api-section">
      <h3>接口1：创建 Project</h3>
      <form class="form-block" @submit.prevent="createProject">
        <div class="row">
          <label>项目名称</label>
          <input v-model="projectForm.name" placeholder="示例：Demo Project" required />
        </div>
        <div class="row">
          <label>涉及行业</label>
          <input
            v-model="projectForm.industryInput"
            placeholder="多个行业使用逗号分隔，如 power,telecom"
          />
        </div>
        <div class="row">
          <label>行业版本</label>
          <input v-model="projectForm.industryVersion" placeholder="示例：v1" required />
        </div>
        <div class="row">
          <label>描述</label>
          <input v-model="projectForm.describe" placeholder="可选" />
        </div>
        <button type="submit" :disabled="creatingProject">
          {{ creatingProject ? "创建中..." : "创建项目" }}
        </button>
      </form>
      <p v-if="projectId" class="info-line">当前 Project ID：{{ projectId }}</p>
      <p v-if="apiError.create" class="error-message">{{ apiError.create }}</p>
    </section>

    <section class="api-section">
      <h3>接口2：下发 Action</h3>
      <form class="form-block" @submit.prevent="dispatchAction">
        <div class="row">
          <label>Action 名称</label>
          <input v-model="actionForm.action_name" placeholder="示例：demo-action" required />
        </div>
        <div class="row">
          <label>所属 Project</label>
          <input
            v-model="actionForm.project_id"
            placeholder="自动带入创建后的 Project ID，可手动填写"
            required
          />
        </div>
        <div class="row">
          <label>目标节点 ID</label>
          <input v-model="actionForm.target[0].id" placeholder="示例：node-1" required />
        </div>
        <div class="row">
          <label>目标名称</label>
          <input v-model="actionForm.target[0].name" placeholder="示例：默认节点" required />
        </div>
        <div class="row">
          <label>行业</label>
          <input v-model="actionForm.target[0].industry" placeholder="示例：power" required />
        </div>
        <div class="row">
          <label>参数 (JSON)</label>
          <input v-model="actionForm.target[0].parameter" placeholder='示例：{"k":1}' />
        </div>
        <button type="submit" :disabled="dispatchingAction">
          {{ dispatchingAction ? "下发中..." : "下发 Action" }}
        </button>
      </form>
      <p v-if="actionId" class="info-line">当前 Action ID：{{ actionId }}</p>
      <p v-if="apiError.dispatch" class="error-message">{{ apiError.dispatch }}</p>
    </section>

    <div class="row controls">
      <label>百分比</label>
      <input type="range" min="0" max="100" v-model.number="percent" @input="sendPercent" />
      <span class="label">{{ percent }}%</span>
      <button type="button" @click="togglePlay">{{ playing ? "暂停" : "播放" }}</button>
      <span class="status" :class="{ on: connected }">{{ connected ? "WS已连接" : "WS未连接" }}</span>
    </div>

    <div class="row controls">
      <label>Measurement</label>
      <input v-model="measurement" placeholder="* 或容器名" @change="sendPercent" />
      <label>窗口</label>
      <input type="number" v-model.number="windowSize" min="0" max="50" @change="sendPercent" />
      <label>起始范围</label>
      <input v-model="startRange" @change="sendPercent" />
      <label>Limit</label>
      <input type="number" v-model.number="limit" min="0" @change="sendPercent" />
    </div>

    <div v-if="wsError" class="error-message">{{ wsError }}</div>

    <div class="panel">
      <h3>当前步骤</h3>
      <pre>{{ point | pretty }}</pre>
      <p class="meta-line" v-if="taskMeta.task_id">
        任务：{{ taskMeta.task_id }}（{{ taskMeta.percentage }}%）
      </p>
      <p class="meta-line" v-if="wsUrl">WebSocket：{{ wsUrl }}</p>
    </div>

    <div class="panel">
      <h3>Measurement 数据</h3>
      <pre>{{ series | pretty }}</pre>
    </div>

    <div class="panel">
      <h3>SSE 事件</h3>
      <p class="meta-line" v-if="sseUrl">SSE：{{ sseUrl }}</p>
      <el-table :data="tableData" style="width: 100%">
        <el-table-column label="Action ID" prop="id"></el-table-column>
        <el-table-column label="Action 名称" prop="name"></el-table-column>
        <el-table-column label="行业" prop="industry"></el-table-column>
        <el-table-column label="事件" prop="event"></el-table-column>
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
      windowSize: 0,
      measurement: "*",
      startRange: "-30d",
      limit: 0,
      playing: false,
      tick: null,
      point: [],
      series: {},
      wsError: null,
      eventSource: null,
      tableData: [],
      retryCount: 0,
      maxRetries: 5,
      reconnectTimer: null,
      loading: false,
      projectForm: {
        name: "Demo Project",
        industryInput: "power,telecom",
        industryVersion: "v1",
        describe: ""
      },
      actionForm: {
        project_id: "",
        action_name: "demo-action",
        target: [
          {
            id: "node-1",
            name: "默认节点",
            industry: "power",
            parameter: "{\"k\":1}"
          }
        ]
      },
      projectId: "",
      actionId: "",
      creatingProject: false,
      dispatchingAction: false,
      apiError: {
        create: null,
        dispatch: null
      },
      taskMeta: {},
      wsUrl: "",
      sseUrl: ""
    };
  },
  filters: {
    pretty(v) {
      return JSON.stringify(v, null, 2);
    }
  },
  computed: {
    httpBase() {
      return window.location.origin;
    },
    wsProtocol() {
      return window.location.protocol === "https:" ? "wss" : "ws";
    }
  },
  watch: {
    projectId(newVal) {
      if (this.actionForm.project_id !== newVal) {
        this.actionForm.project_id = newVal || "";
      }
    },
    "actionForm.project_id"(val) {
      if (this.projectId !== val) {
        this.projectId = val || "";
      }
    }
  },
  mounted() {
    if (this.projectId) {
      this.sseUrl = `${this.httpBase}/api/sse/events?project_id=${encodeURIComponent(this.projectId)}`;
      this.initSSE();
    }
  },
  beforeDestroy() {
    if (this.tick) clearInterval(this.tick);
    if (this.ws) {
      try {
        this.ws.close();
      } catch (_) {}
      this.ws = null;
    }
    this.closeSSE();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  },
  methods: {
    async createProject() {
      this.apiError.create = null;
      this.creatingProject = true;
      try {
        const industries = this.projectForm.industryInput
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        const payload = {
          name: this.projectForm.name,
          industry: industries,
          industry_version: this.projectForm.industryVersion,
          describe: this.projectForm.describe
        };
        const resp = await fetch(`${this.httpBase}/api/projects/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data.ok === false) {
          const err =
            data.errors ? JSON.stringify(data.errors) : data.error || data.detail || resp.statusText;
          throw new Error(err || "创建项目失败");
        }
        this.projectId = data.project_id || "";
        this.actionId = "";
        this.taskMeta = {};
        this.wsUrl = "";
        this.wsError = null;
        if (this.ws) {
          try {
            this.ws.close();
          } catch (_) {}
          this.ws = null;
        }
        this.connected = false;
        if (this.projectId) {
          this.sseUrl = `${this.httpBase}/api/sse/events?project_id=${encodeURIComponent(
            this.projectId
          )}`;
          this.tableData = [];
          this.reconnectSSE();
        }
      } catch (e) {
        this.apiError.create = e.message || "创建项目失败";
      } finally {
        this.creatingProject = false;
      }
    },
    async dispatchAction() {
      this.apiError.dispatch = null;
      const projectId = this.actionForm.project_id || this.projectId;
      if (!projectId) {
        this.apiError.dispatch = "请先创建或填写项目 ID";
        return;
      }
      this.dispatchingAction = true;
      try {
        const target = this.actionForm.target.map((item) => {
          let parameter = item.parameter;
          if (typeof parameter === "string") {
            const trimmed = parameter.trim();
            if (trimmed) {
              try {
                parameter = JSON.parse(trimmed);
              } catch (err) {
                console.warn("参数解析失败，将以字符串发送", err);
                parameter = trimmed;
              }
            } else {
              parameter = {};
            }
          }
          return {
            id: item.id,
            name: item.name,
            industry: item.industry,
            parameter
          };
        });
        const payload = {
          project_id: projectId,
          action_name: this.actionForm.action_name,
          target
        };
        const resp = await fetch(`${this.httpBase}/api/actions/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data.ok === false) {
          const err =
            data.errors ? JSON.stringify(data.errors) : data.error || data.detail || resp.statusText;
          throw new Error(err || "下发 Action 失败");
        }
        this.projectId = payload.project_id;
        this.actionId = data.action_id || "";
        this.taskMeta = {
          project_id: payload.project_id,
          action_id: this.actionId,
          task_id: this.actionId ? `${payload.project_id}.${this.actionId}` : "",
          percentage: this.percent
        };
        this.initWebSocket();
      } catch (e) {
        this.apiError.dispatch = e.message || "下发 Action 失败";
      } finally {
        this.dispatchingAction = false;
      }
    },
    initWebSocket() {
      if (!this.projectId || !this.actionId) {
        return;
      }
      const url = `${this.wsProtocol}://${window.location.host}/ws/metrics/${this.projectId}/${this.actionId}/`;
      this.wsUrl = url;
      if (this.ws) {
        try {
          this.ws.close();
        } catch (_) {}
        this.ws = null;
      }
      this.connected = false;
      this.wsError = null;
      this.ws = connectWS(url, {
        onOpen: () => {
          this.connected = true;
          this.wsError = null;
          this.sendPercent();
        },
        onClose: () => {
          this.connected = false;
        },
        onMessage: (msg) => {
          if (msg && msg.error) {
            this.wsError = `服务器错误: ${msg.error}`;
            return;
          }
          if (msg) {
            if (msg.selected_steps) {
              this.point = msg.selected_steps;
            }
            if (msg.measurements) {
              this.series = msg.measurements;
            }
            this.taskMeta = {
              project_id: msg.project_id,
              action_id: msg.action_id,
              task_id: msg.task_id,
              percentage: msg.percentage
            };
          }
        },
        onError: (error) => {
          let message = "WebSocket 连接失败";
          if (error && error.code === 1006) {
            message = "连接被意外关闭，请检查网络或服务器状态";
          } else if (error && error.message) {
            message = `连接错误: ${error.message}`;
          }
          this.wsError = message;
        }
      });
    },
    sendPercent() {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        return;
      }
      const payload = {
        percentage: this.percent,
        measurement: (this.measurement || "*").trim() || "*",
        window: this.windowSize,
        start: this.startRange,
        limit: this.limit
      };
      this.ws.send(JSON.stringify(payload));
    },
    togglePlay() {
      this.playing = !this.playing;
      if (this.playing) {
        this.tick = setInterval(() => {
          this.percent = (this.percent + 1) % 101;
          this.sendPercent();
        }, 1000);
      } else if (this.tick) {
        clearInterval(this.tick);
        this.tick = null;
      }
    },
    normalizeIndustry(ind) {
      if (Array.isArray(ind)) return ind.join(",");
      return ind || "";
    },
    normalizeRow(row) {
      const industry = this.normalizeIndustry(row.industry ?? row["industry"]);
      return {
        id: row.id ?? row["action id"] ?? row.action_id ?? "",
        name: row.name ?? row["action name"] ?? row.action_name ?? "",
        industry,
        event: row.event ?? row["event"] ?? ""
      };
    },
    initSSE() {
      if (!this.projectId) {
        return;
      }
      try {
        if (this.eventSource) {
          this.closeSSE();
        }
        this.loading = true;
        if (!this.sseUrl) {
          this.sseUrl = `${this.httpBase}/api/sse/events?project_id=${encodeURIComponent(
            this.projectId
          )}`;
        }
        this.eventSource = new EventSource(this.sseUrl);
        this.eventSource.onopen = () => {
          this.retryCount = 0;
          this.loading = false;
        };
        this.eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (Array.isArray(data)) {
              this.tableData = data.map(this.normalizeRow);
            }
          } catch (_) {}
        };
        this.eventSource.addEventListener("solutions", (event) => {
          try {
            const list = JSON.parse(event.data);
            if (Array.isArray(list)) {
              this.tableData = list.map(this.normalizeRow);
            }
          } catch (_) {}
        });
        this.eventSource.addEventListener("ping", () => {});
        this.eventSource.onerror = () => {
          this.loading = false;
          if (!this.eventSource) return;
          const state = this.eventSource.readyState;
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
            }
          }
        };
      } catch (e) {
        this.loading = false;
        this.apiError.create = e.message || "SSE 连接失败";
      }
    },
    closeSSE() {
      if (this.eventSource) {
        try {
          this.eventSource.close();
        } catch (_) {}
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
    }
  }
};
</script>

<style>
.wrap {
  max-width: 960px;
  margin: 24px auto;
  font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
  flex-wrap: wrap;
}
.controls {
  margin-top: 16px;
}
.label {
  width: 60px;
  text-align: right;
}
.panel {
  background: #f7f7f8;
  border: 1px solid #e5e7eb;
  padding: 12px;
  border-radius: 8px;
  margin-top: 12px;
}
.status {
  padding: 2px 8px;
  border-radius: 12px;
  background: #eee;
}
.status.on {
  background: #d1fae5;
}
button {
  padding: 6px 12px;
  cursor: pointer;
  border: none;
  border-radius: 4px;
  background: #2563eb;
  color: #fff;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error-message {
  color: #dc2626;
  background: #fee2e2;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 8px 0;
  font-size: 14px;
}
.api-section {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.api-section h3 {
  margin: 0 0 12px;
}
.form-block .row {
  justify-content: flex-start;
}
.form-block label {
  width: 120px;
  font-weight: 600;
  color: #374151;
}
.form-block input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
}
.info-line {
  margin-top: 8px;
  font-size: 14px;
  color: #2563eb;
}
.meta-line {
  margin: 4px 0;
  font-size: 13px;
  color: #6b7280;
}
.el-card {
  background-color: rgba(0, 0, 0, 0);
  margin-bottom: 24px;
  border: 0px;
  background-repeat: no-repeat;
  background-size: 100%, 100%;
}
.el-card .el-card__header {
  padding: 0px;
  height: 35px;
  border: 0px;
  text-align: left;
}
.el-card .el-card__body {
  padding: 0px;
}
.header {
  position: relative;
  height: 100%;
  margin: 0;
  padding: 0px;
  border: 0px;
  font-family: "youshebiaotihei";
  color: #fff;
  text-align: left;
}
.header .icon {
  position: relative;
  top: 4px;
  margin-left: 0;
  margin-right: 8px;
  width: 10px;
  float: left;
  height: 100%;
  background-position: center;
  background-repeat: no-repeat;
}
.header .word {
  position: relative;
  top: 7px;
  float: left;
}
.el-table {
  background-color: transparent !important;
  color: #fff;
}
.el-table th,
.el-table tr {
  background-color: transparent !important;
}
.el-table--enable-row-hover .el-table__body tr:hover > td {
  background-color: rgba(255, 255, 255, 0.1) !important;
}
</style>
