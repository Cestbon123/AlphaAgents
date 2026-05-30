window.AlphaAgentsApi = {
  baseUrl: "http://127.0.0.1:8000/api/v1",

  async runWorkflow(name) {
    const response = await fetch(`${this.baseUrl}/workflows/${name}/run`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`流程执行失败：${response.status}`);
    }
    return response.json();
  },

  async getDashboard() {
    const response = await fetch(`${this.baseUrl}/dashboard`);
    if (!response.ok) {
      throw new Error(`仪表盘读取失败：${response.status}`);
    }
    return response.json();
  },

  async getDataSyncStatus() {
    const response = await fetch(`${this.baseUrl}/data-sync/status`);
    if (!response.ok) {
      throw new Error(`数据同步状态读取失败：${response.status}`);
    }
    return response.json();
  },

  async runDataSync() {
    const response = await fetch(`${this.baseUrl}/data-sync/run`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`数据同步失败：${response.status}`);
    }
    return response.json();
  },

  async getLatestSelectionRun() {
    const response = await fetch(`${this.baseUrl}/workflows/selection/runs/latest`);
    if (!response.ok) {
      throw new Error(`最新选股结果读取失败：${response.status}`);
    }
    return response.json();
  },

  async listResearchReports(options = {}) {
    const params = new URLSearchParams();
    if (options.symbol) {
      params.set("symbol", options.symbol);
    }
    if (options.limit) {
      params.set("limit", options.limit);
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/reports/research${query}`);
    if (!response.ok) {
      throw new Error(`研究报告列表读取失败：${response.status}`);
    }
    return response.json();
  },

  async getStockWorkspace(symbol) {
    const response = await fetch(`${this.baseUrl}/stocks/${encodeURIComponent(symbol)}/workspace`);
    if (!response.ok) {
      throw new Error(`个股工作台读取失败：${response.status}`);
    }
    return response.json();
  },

  async listStockCases(options = {}) {
    const params = new URLSearchParams();
    ["symbol", "query", "kind", "status"].forEach((key) => {
      if (options[key]) {
        params.set(key, options[key]);
      }
    });
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/stocks/cases/list${query}`);
    if (!response.ok) {
      throw new Error(`案例库读取失败：${response.status}`);
    }
    return response.json();
  },

  async runStockResearch(symbol) {
    const response = await fetch(`${this.baseUrl}/stocks/${encodeURIComponent(symbol)}/research/run`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`个股研究报告生成失败：${response.status}`);
    }
    return response.json();
  },

  async saveStockOperation(symbol, operation) {
    const response = await fetch(`${this.baseUrl}/stocks/${encodeURIComponent(symbol)}/operations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(operation),
    });
    if (!response.ok) {
      throw new Error(`个股操作记录保存失败：${response.status}`);
    }
    return response.json();
  },

  async saveStockReview(symbol, review) {
    const response = await fetch(`${this.baseUrl}/stocks/${encodeURIComponent(symbol)}/reviews`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(review),
    });
    if (!response.ok) {
      throw new Error(`个股复盘保存失败：${response.status}`);
    }
    return response.json();
  },

  async saveStockDeposition(symbol, deposition) {
    const response = await fetch(`${this.baseUrl}/stocks/${encodeURIComponent(symbol)}/depositions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(deposition),
    });
    if (!response.ok) {
      throw new Error(`个股沉淀保存失败：${response.status}`);
    }
    return response.json();
  },

  async updateStockTracking(symbol, tracking) {
    const response = await fetch(`${this.baseUrl}/stocks/${encodeURIComponent(symbol)}/tracking`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(tracking),
    });
    if (!response.ok) {
      throw new Error(`个股跟踪状态保存失败：${response.status}`);
    }
    return response.json();
  },

  async getDailyBars(symbol, limit = 120) {
    const query = `symbol=${encodeURIComponent(symbol)}&limit=${encodeURIComponent(limit)}`;
    const response = await fetch(`${this.baseUrl}/market/daily-bars?${query}`);
    if (!response.ok) {
      throw new Error(`日线数据读取失败：${response.status}`);
    }
    return response.json();
  },
  async listMarketSectors(options = {}) {
    const params = new URLSearchParams();
    if (options.sector_type) {
      params.set("sector_type", options.sector_type);
    }
    if (options.query) {
      params.set("query", options.query);
    }
    if (options.limit) {
      params.set("limit", options.limit);
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/market/sectors${query}`);
    if (!response.ok) {
      throw new Error(`sector list read failed: ${response.status}`);
    }
    return response.json();
  },

  async listMarketStocks(options = {}) {
    const params = new URLSearchParams();
    if (options.sector_code) {
      params.set("sector_code", options.sector_code);
    }
    if (options.limit) {
      params.set("limit", options.limit);
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/market/stocks${query}`);
    if (!response.ok) {
      throw new Error(`stock list read failed: ${response.status}`);
    }
    return response.json();
  },

  async listStrategies() {
    const response = await fetch(`${this.baseUrl}/strategies`);
    if (!response.ok) {
      throw new Error(`strategy list read failed: ${response.status}`);
    }
    return response.json();
  },

  async updateStrategy(strategyId, strategy) {
    const response = await fetch(`${this.baseUrl}/strategies/${encodeURIComponent(strategyId)}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(strategy),
    });
    if (!response.ok) {
      throw new Error(`strategy save failed: ${response.status}`);
    }
    return response.json();
  },

  async draftStrategy(prompt) {
    const response = await fetch(`${this.baseUrl}/strategies/draft`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt }),
    });
    if (!response.ok) {
      throw new Error(`AI strategy draft failed: ${response.status}`);
    }
    return response.json();
  },
};
