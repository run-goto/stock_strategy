import axios from 'axios';

const API_BASE = 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ==================== 股票信息 API ====================

export interface Stock {
  code: string;
  name: string;
  updated_at?: string;
}

export interface StocksResponse {
  success: boolean;
  data: Stock[];
  total: number;
}

export const getStocks = async (search?: string, limit = 50, offset = 0): Promise<StocksResponse> => {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  
  const response = await api.get(`/stocks?${params.toString()}`);
  return response.data;
};

export const syncStocks = async () => {
  const response = await api.post('/stocks/sync');
  return response.data;
};

export const getStockCount = async () => {
  const response = await api.get('/stocks/count');
  return response.data;
};

// ==================== 行情数据 API ====================

export interface DailyData {
  id?: number;
  code: string;
  trade_date: string;
  open?: number;
  close?: number;
  high?: number;
  low?: number;
  volume?: number;
  amount?: number;
}

export const getLoadedDates = async (code: string) => {
  const response = await api.get(`/daily/${code}/dates`);
  return response.data;
};

export const getDailyData = async (code: string, tradeDate: string) => {
  const response = await api.get(`/daily/${code}/${tradeDate}`);
  return response.data;
};

export const getDailyRange = async (code: string, start: string, end: string) => {
  const response = await api.get(`/daily/${code}/range?start=${start}&end=${end}`);
  return response.data;
};

export const syncDailyData = async (code: string, startDate: string, endDate: string) => {
  const response = await api.post('/daily/sync', {
    code,
    start_date: startDate,
    end_date: endDate,
  });
  return response.data;
};

export const syncBatchDaily = async (startDate: string, endDate: string) => {
  const response = await api.post('/daily/sync-batch', {
    start_date: startDate,
    end_date: endDate,
  });
  return response.data;
};

export const syncTodayDaily = async () => {
  const response = await api.post('/daily/sync-today');
  return response.data;
};

export const getAllLoadedDates = async () => {
  const response = await api.get('/daily/loaded-dates');
  return response.data;
};

// ==================== 策略分析 API ====================

export interface Strategy {
  name: string;
  value: string;
}

export const getStrategies = async () => {
  const response = await api.get('/strategies');
  return response.data;
};

export const analyzeStrategies = async (startDate: string, endDate: string, strategies: string[]) => {
  const response = await api.post('/strategies/analyze', {
    start_date: startDate,
    end_date: endDate,
    strategies,
  });
  return response.data;
};

export const exportResults = async (results: Record<string, any[]>) => {
  const response = await api.post('/strategies/export', 
    { results },
    { responseType: 'blob' }
  );
  
  // 创建下载链接
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `strategy_results_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

// ==================== 健康检查 ====================

export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;

