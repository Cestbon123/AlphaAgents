const chartContainer = document.querySelector("#kline-chart");
const chartStatus = document.querySelector("#chart-status");
const chartQuoteStrip = document.querySelector("#chart-quote-strip");
const symbolButtons = document.querySelectorAll("[data-chart-symbol]");

const ZHIXING_TREND = "ZHIXING_TREND";
const SHORT_TERM_BRICK = "SHORT_TERM_BRICK";
const ZHIXING_WASH_SHORT = "ZHIXING_WASH_SHORT";
const KLINE_HISTORY_LIMIT = 5000;
const PANE_HEIGHTS = {
  candle: 500,
  volume: 150,
  macd: 150,
  kdj: 150,
  shortTermBrick: 150,
  zhixingWashShort: 180,
};
const DEFAULT_SYMBOL = "000001.SH";
const SUB_INDICATORS = [
  ["VOL", false, { id: "indicator_pane_vol", height: PANE_HEIGHTS.volume }],
  ["MACD", false, { id: "indicator_pane_macd", height: PANE_HEIGHTS.macd }],
  ["KDJ", false, { id: "indicator_pane_kdj", height: PANE_HEIGHTS.kdj }],
  [SHORT_TERM_BRICK, false, { id: "indicator_pane_short_term_brick", height: PANE_HEIGHTS.shortTermBrick }],
  [ZHIXING_WASH_SHORT, false, { id: "indicator_pane_zhixing_wash_short", height: PANE_HEIGHTS.zhixingWashShort }],
];

function setChartStatus(message) {
  if (chartStatus) {
    chartStatus.textContent = message;
  }
}

function activateSymbol(symbol) {
  symbolButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.chartSymbol === symbol);
  });
}

function toTimestamp(time) {
  return new Date(`${time}T00:00:00+08:00`).getTime();
}

function readNumber(source, keys, fallback = NaN) {
  for (const key of keys) {
    const value = source?.[key];
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric;
    }
  }
  return fallback;
}

function normalizeDailyBars(bars) {
  return bars.map((bar, index) => ({
    timestamp: toTimestamp(bar.time),
    open: readNumber(bar, ["open", "open_price", "o"]),
    high: readNumber(bar, ["high", "high_price", "h"]),
    low: readNumber(bar, ["low", "low_price", "l"]),
    close: readNumber(bar, ["close", "close_price", "price", "c"]),
    volume: Number(bar.volume || (index + 1) * 1000000),
    turnover: Number(bar.amount || 0),
  }));
}

function formatPrice(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return numeric.toFixed(numeric >= 100 ? 2 : 3).replace(/0+$/, "").replace(/\.$/, "");
}

function formatQuotePct(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

function setQuoteStripEmpty() {
  if (!chartQuoteStrip) return;
  chartQuoteStrip.querySelectorAll("strong").forEach((item) => {
    item.className = "";
    item.textContent = "--";
  });
}

function updateQuoteStrip(bars) {
  if (!chartQuoteStrip || !bars || !bars.length) {
    setQuoteStripEmpty();
    return;
  }
  const latest = bars[bars.length - 1];
  const previous = bars.length > 1 ? bars[bars.length - 2] : null;
  const previousClose = readNumber(previous, ["close"], latest.open);
  const { open, close, high, low } = latest;
  const changePct = Number.isFinite(previousClose) && previousClose !== 0
    ? ((close - previousClose) / previousClose) * 100
    : NaN;
  const amplitudePct = Number.isFinite(previousClose) && previousClose !== 0
    ? ((high - low) / previousClose) * 100
    : NaN;
  const values = [
    formatPrice(open),
    formatPrice(close),
    formatPrice(high),
    formatPrice(low),
    formatQuotePct(changePct),
    formatQuotePct(amplitudePct),
  ];
  chartQuoteStrip.querySelectorAll("strong").forEach((item, index) => {
    item.className = "";
    if (index === 4 && Number.isFinite(changePct)) {
      item.classList.add(changePct < 0 ? "price-down" : "price-up");
    }
    item.textContent = values[index] || "--";
  });
}

function movingAverage(values, period, index) {
  if (index + 1 < period) {
    return undefined;
  }
  let sum = 0;
  for (let cursor = index - period + 1; cursor <= index; cursor += 1) {
    sum += values[cursor];
  }
  return sum / period;
}

function ema(values, period) {
  const result = [];
  const alpha = 2 / (period + 1);
  values.forEach((value, index) => {
    if (index === 0) {
      result.push(value);
      return;
    }
    result.push(alpha * value + (1 - alpha) * result[index - 1]);
  });
  return result;
}

function windowExtreme(values, period, index, picker) {
  const start = Math.max(0, index - period + 1);
  let selected = values[start];
  for (let cursor = start + 1; cursor <= index; cursor += 1) {
    selected = picker(selected, values[cursor]);
  }
  return selected;
}

function safePercent(numerator, denominator) {
  if (!Number.isFinite(denominator) || denominator === 0) {
    return 0;
  }
  return (numerator / denominator) * 100;
}

function tdxSma(values, period, weight) {
  const result = [];
  values.forEach((value, index) => {
    if (index === 0 || !Number.isFinite(result[index - 1])) {
      result.push(value);
      return;
    }
    result.push((weight * value + (period - weight) * result[index - 1]) / period);
  });
  return result;
}

function crossedAbove(values, targets, index) {
  if (index <= 0) {
    return false;
  }
  const previousValue = values[index - 1];
  const previousTarget = targets[index - 1];
  const currentValue = values[index];
  const currentTarget = targets[index];
  return (
    Number.isFinite(previousValue) &&
    Number.isFinite(previousTarget) &&
    Number.isFinite(currentValue) &&
    Number.isFinite(currentTarget) &&
    previousValue <= previousTarget &&
    currentValue > currentTarget
  );
}

function drawShortTermBrick({ ctx, barSpace, visibleRange, indicator, xAxis, yAxis }) {
  const result = indicator.result || [];
  const { from, to } = visibleRange;
  const width = Math.max(2, (barSpace.gapBar || barSpace.bar * 0.8) * 0.92);

  ctx.save();
  for (let index = from; index < to; index += 1) {
    const data = result[index];
    if (
      !data ||
      !Number.isFinite(data.brickStart) ||
      !Number.isFinite(data.brickEnd) ||
      data.brickStart === data.brickEnd
    ) {
      continue;
    }

    const x = xAxis.convertToPixel(index) - width / 2;
    const startY = yAxis.convertToPixel(data.brickStart);
    const endY = yAxis.convertToPixel(data.brickEnd);
    const y = Math.min(startY, endY);
    const height = Math.max(1, Math.abs(endY - startY));

    ctx.fillStyle = data.brickEnd > data.brickStart ? "#ff0000" : "#00ff00";
    ctx.fillRect(x, y, width, height);
  }
  ctx.restore();

  return false;
}

function registerZhixingTrendIndicator() {
  if (!window.klinecharts || !window.klinecharts.registerIndicator) {
    return;
  }

  window.klinecharts.registerIndicator({
    name: ZHIXING_TREND,
    shortName: "知行趋势线",
    series: "price",
    precision: 2,
    calcParams: [14, 28, 57, 114],
    shouldOhlc: false,
    shouldFormatBigNumber: false,
    figures: [
      {
        key: "zhixingShort",
        title: "知行短期趋势线",
        type: "line",
        styles: () => ({ color: "#ffffff", size: 1 }),
      },
      {
        key: "zhixingLongShort",
        title: "知行多空线",
        type: "line",
        styles: () => ({ color: "#f4aa35", size: 1.4 }),
      },
    ],
    calc: (dataList, indicator) => {
      const params = indicator.calcParams || [14, 28, 57, 114];
      const closeValues = dataList.map((bar) => Number(bar.close));
      const doubleEma = ema(ema(closeValues, 10), 10);
      return dataList.map((bar, index) => {
        const averages = params.map((period) => movingAverage(closeValues, Number(period), index));
        const validAverages = averages.filter((value) => Number.isFinite(value));
        return {
          zhixingShort: doubleEma[index],
          zhixingLongShort:
            validAverages.length === params.length
              ? validAverages.reduce((sum, value) => sum + value, 0) / params.length
              : undefined,
        };
      });
    },
  });
}

function registerShortTermBrickIndicator() {
  if (!window.klinecharts || !window.klinecharts.registerIndicator) {
    return;
  }

  window.klinecharts.registerIndicator({
    name: SHORT_TERM_BRICK,
    shortName: "短期转型图",
    precision: 2,
    minValue: 0,
    shouldOhlc: false,
    shouldFormatBigNumber: false,
    figures: [
      {
        key: "brickValue",
        title: "砖型图",
      },
      {
        key: "holdEmptyLine",
        title: "红持绿空",
        type: "line",
        styles: () => ({ color: "#00ff68", size: 1, style: "dashed", dashedValue: [4, 3] }),
      },
    ],
    calc: (dataList) => {
      const highs = dataList.map((bar) => Number(bar.high));
      const lows = dataList.map((bar) => Number(bar.low));
      const closes = dataList.map((bar) => Number(bar.close));
      const var1a = dataList.map((bar, index) => {
        const highestHigh = windowExtreme(highs, 4, index, Math.max);
        const lowestLow = windowExtreme(lows, 4, index, Math.min);
        return safePercent(highestHigh - closes[index], highestHigh - lowestLow) - 90;
      });
      const var2a = tdxSma(var1a, 4, 1).map((value) => value + 100);
      const var3a = dataList.map((bar, index) => {
        const highestHigh = windowExtreme(highs, 4, index, Math.max);
        const lowestLow = windowExtreme(lows, 4, index, Math.min);
        return safePercent(closes[index] - lowestLow, highestHigh - lowestLow);
      });
      const var4a = tdxSma(var3a, 6, 1);
      const var5a = tdxSma(var4a, 6, 1).map((value) => value + 100);
      const brickValues = dataList.map((bar, index) => {
        const var6a = var5a[index] - var2a[index];
        return var6a > 4 ? var6a - 4 : 0;
      });

      return dataList.map((bar, index) => {
        const brickValue = brickValues[index];
        const previousBrickValue = index > 0 ? brickValues[index - 1] : brickValue;
        return {
          brickValue,
          brickStart: previousBrickValue,
          brickEnd: brickValue,
          holdEmptyLine: 0,
        };
      });
    },
    draw: drawShortTermBrick,
  });
}

function registerZhixingWashShortIndicator() {
  if (!window.klinecharts || !window.klinecharts.registerIndicator) {
    return;
  }

  window.klinecharts.registerIndicator({
    name: ZHIXING_WASH_SHORT,
    shortName: "知行洗盘短线",
    precision: 2,
    calcParams: [3, 21],
    minValue: -35,
    maxValue: 105,
    shouldOhlc: false,
    shouldFormatBigNumber: false,
    figures: [
      {
        key: "shortTerm",
        title: "短期",
        type: "line",
        styles: () => ({ color: "#ffffff", size: 1 }),
      },
      {
        key: "longTerm",
        title: "长期",
        type: "line",
        styles: () => ({ color: "#ff3d3d", size: 1.6 }),
      },
      {
        key: "level85",
        title: "",
        type: "line",
        styles: () => ({ color: "#f4d35e", size: 1, style: "dashed", dashedValue: [4, 3] }),
      },
      {
        key: "level30",
        title: "",
        type: "line",
        styles: () => ({ color: "#f4d35e", size: 1, style: "dashed", dashedValue: [4, 3] }),
      },
      {
        key: "zeroBuy",
        title: "四线归零买",
        type: "bar",
        styles: ({ current }) => ({
          color: current.indicatorData?.zeroBuy < 0 ? "#ff3d3d" : "rgba(0,0,0,0)",
        }),
      },
      {
        key: "whiteBelow20Buy",
        title: "白线下20买",
        type: "bar",
        styles: ({ current }) => ({
          color: current.indicatorData?.whiteBelow20Buy < 0 ? "#00e5ff" : "rgba(0,0,0,0)",
        }),
      },
      {
        key: "whiteCrossRedBuy",
        title: "白穿红线买",
        type: "bar",
        styles: ({ current }) => ({
          color: current.indicatorData?.whiteCrossRedBuy < 0 ? "#00ff68" : "rgba(0,0,0,0)",
        }),
      },
      {
        key: "whiteCrossYellowBuy",
        title: "白穿黄线买",
        type: "bar",
        styles: ({ current }) => ({
          color: current.indicatorData?.whiteCrossYellowBuy < 0 ? "#ff9150" : "rgba(0,0,0,0)",
        }),
      },
    ],
    calc: (dataList, indicator) => {
      const params = indicator.calcParams || [3, 21];
      const n1 = Math.min(Math.max(Number(params[0]) || 3, 1), 999);
      const n2 = Math.min(Math.max(Number(params[1]) || 21, 1), 999);
      const lows = dataList.map((bar) => Number(bar.low));
      const closes = dataList.map((bar) => Number(bar.close));
      const calcLine = (period) =>
        dataList.map((bar, index) => {
          const lowestLow = windowExtreme(lows, period, index, Math.min);
          const highestClose = windowExtreme(closes, period, index, Math.max);
          return safePercent(closes[index] - lowestLow, highestClose - lowestLow);
        });

      const shortTerm = calcLine(n1);
      const midTerm = calcLine(10);
      const midLongTerm = calcLine(20);
      const longTerm = calcLine(n2);

      return dataList.map((bar, index) => {
        const zeroBuy =
          shortTerm[index] <= 6 &&
          midTerm[index] <= 6 &&
          midLongTerm[index] <= 6 &&
          longTerm[index] <= 6
            ? -30
            : 0;
        const whiteBelow20Buy = shortTerm[index] <= 20 && longTerm[index] >= 60 ? -30 : 0;
        const whiteCrossRedBuy =
          crossedAbove(shortTerm, longTerm, index) && longTerm[index] < 20 ? -30 : 0;
        const whiteCrossYellowBuy =
          crossedAbove(shortTerm, midTerm, index) && midTerm[index] < 30 ? -30 : 0;

        return {
          shortTerm: shortTerm[index],
          longTerm: longTerm[index],
          level85: 85,
          level30: 30,
          zeroBuy,
          whiteBelow20Buy,
          whiteCrossRedBuy,
          whiteCrossYellowBuy,
        };
      });
    },
  });
}

function registerCustomIndicators() {
  registerZhixingTrendIndicator();
  registerShortTermBrickIndicator();
  registerZhixingWashShortIndicator();
}

function initKlineChart() {
  if (!chartContainer) {
    return;
  }

  if (!window.klinecharts) {
    setChartStatus("图表库未加载，当前仅保留 K 线面板占位");
    return;
  }

  registerCustomIndicators();

  let isChartInteractionActive = false;

  function setChartInteractionActive(active) {
    isChartInteractionActive = active;
    chartContainer.classList.toggle("is-interaction-active", active);
  }

  chartContainer.addEventListener("dblclick", () => {
    setChartInteractionActive(true);
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element) || chartContainer.contains(event.target)) {
      return;
    }
    setChartInteractionActive(false);
  });

  chartContainer.addEventListener(
    "wheel",
    (event) => {
      if (isChartInteractionActive) {
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    { capture: true, passive: false }
  );

  const chart = klinecharts.init(chartContainer, {
    styles: {
      grid: {
        horizontal: { show: false },
        vertical: { show: false },
      },
      separator: {
        size: 1,
        color: "rgba(138, 164, 184, 0.46)",
        fill: true,
        activeBackgroundColor: "rgba(49, 219, 199, 0.08)",
      },
      candle: {
        tooltip: {
          showRule: "none",
        },
        bar: {
          upColor: "#ff3d3d",
          downColor: "#00e676",
          noChangeColor: "#d4dde5",
          upBorderColor: "#ff3d3d",
          downBorderColor: "#00e676",
          noChangeBorderColor: "#d4dde5",
          upWickColor: "#ff3d3d",
          downWickColor: "#00e676",
          noChangeWickColor: "#d4dde5",
        },
      },
      indicator: {
        tooltip: {
          showRule: "none",
          showName: false,
          showParams: false,
        },
        bars: [{
          upColor: "#ff3d3d",
          downColor: "#00e676",
          noChangeColor: "#d4dde5",
        }],
        lines: [
          { color: "#f4aa35", size: 1.2, style: "solid", dashedValue: [], smooth: false },
          { color: "#ffffff", size: 1, style: "solid", dashedValue: [], smooth: false },
          { color: "#d000ff", size: 1, style: "solid", dashedValue: [], smooth: false },
        ],
      },
      yAxis: {
        axisLine: { show: true, color: "rgba(138, 164, 184, 0.34)" },
        tickLine: { show: false },
      },
      xAxis: {
        axisLine: { show: true, color: "rgba(138, 164, 184, 0.34)" },
        tickLine: { show: false },
      },
    },
    layout: [
      {
        type: "candle",
        content: [ZHIXING_TREND],
        options: { id: "candle_pane", height: PANE_HEIGHTS.candle },
      },
    ],
  });

  if (!chart) {
    setChartStatus("KLineCharts 初始化失败");
    return;
  }

  function bindLatestBarToRightEdge() {
    chart.setOffsetRightDistance(0);
    chart.setMaxOffsetRightDistance(0);
  }

  function resizeVisibleChart() {
    if (chartContainer.clientWidth <= 0 || chartContainer.clientHeight <= 0) {
      return;
    }
    chart.resize();
    bindLatestBarToRightEdge();
  }

  bindLatestBarToRightEdge();

  let latestRenderRequestId = 0;
  let defaultIndicatorsCreated = false;

  function ensureDefaultIndicators() {
    if (defaultIndicatorsCreated) return;
    // Create only the candle-pane indicator (ZHIXING_TREND)
    chart.createIndicator(ZHIXING_TREND, true, { id: "candle_pane" });
    defaultIndicatorsCreated = true;
  }

  var subIndicatorsCreated = false;
  window.AlphaAgentsChartExpand = function () {
    if (subIndicatorsCreated) return;
    SUB_INDICATORS.forEach(function (args) {
      chart.createIndicator(args[0], args[1], args[2]);
    });
    subIndicatorsCreated = true;
  };

  window.AlphaAgentsChartCollapse = function () {
    // Sub-indicators stay but will be less visible in smaller right panel
  };

  function renderBars(data) {
    const normalizedBars = normalizeDailyBars(data);
    bindLatestBarToRightEdge();
    chart.applyNewData(normalizedBars, false);
    updateQuoteStrip(normalizedBars);
    ensureDefaultIndicators();
    bindLatestBarToRightEdge();
  }

  function renderNoData(symbol, reason) {
    chart.applyNewData([], false);
    setQuoteStripEmpty();
    setChartStatus(symbol);
  }

  async function renderSymbol(symbol) {
    const requestId = latestRenderRequestId + 1;
    latestRenderRequestId = requestId;
    activateSymbol(symbol);
    setChartStatus(symbol);

    if (!window.AlphaAgentsApi || !window.AlphaAgentsApi.getDailyBars) {
      renderNoData(symbol, "API 未加载");
      return;
    }

    try {
      const result = await window.AlphaAgentsApi.getDailyBars(symbol, KLINE_HISTORY_LIMIT);
      if (requestId !== latestRenderRequestId) {
        return;
      }

      const bars = result && result.bars;
      if (bars && bars.length) {
        renderBars(bars);
        const name = result.name && result.name !== symbol ? `${result.name} ` : "";
        setChartStatus(`${name}${symbol}`);
        return;
      }

      renderNoData(symbol, (result && result.message) || "暂无本地日线数据");
    } catch (error) {
      if (requestId !== latestRenderRequestId) {
        return;
      }
      renderNoData(symbol, error.message || "读取失败");
    }
  }

  symbolButtons.forEach((button) => {
    button.addEventListener("click", () => {
      renderSymbol(button.dataset.chartSymbol);
    });
  });

  window.AlphaAgentsChart = {
    renderSymbol,
    resize: () => requestAnimationFrame(resizeVisibleChart),
  };
  window.addEventListener("alphaagents:chart-symbol-selected", (event) => {
    const symbol = event.detail?.symbol;
    if (symbol) {
      renderSymbol(symbol);
    }
  });

  if (window.ResizeObserver) {
    const observer = new ResizeObserver(resizeVisibleChart);
    observer.observe(chartContainer);
  } else {
    window.addEventListener("resize", resizeVisibleChart);
  }

  renderSymbol(DEFAULT_SYMBOL);
}

initKlineChart();
