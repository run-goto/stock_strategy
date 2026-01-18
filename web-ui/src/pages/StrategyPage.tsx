import React, { useState, useEffect } from 'react';
import { Card, Select, DatePicker, Button, Space, message, Typography, List, Collapse, Badge, Empty, Spin } from 'antd';
import { ExperimentOutlined, DownloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getStrategies, analyzeStrategies, exportResults } from '../api';
import type { Strategy } from '../api';

const { Title } = Typography;
const { RangePicker } = DatePicker;
const { Panel } = Collapse;

interface AnalysisResult {
  code: string;
  name: string;
  strategy: string;
  target_date: string;
  current_price?: number;
  current_volume?: number;
}

const StrategyPage: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [results, setResults] = useState<Record<string, AnalysisResult[]>>({});

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    setLoadingStrategies(true);
    try {
      const res = await getStrategies();
      if (res.success) {
        setStrategies(res.data);
      }
    } catch (error) {
      message.error('获取策略列表失败');
    } finally {
      setLoadingStrategies(false);
    }
  };

  const handleAnalyze = async () => {
    if (!dateRange) {
      message.warning('请选择日期范围');
      return;
    }
    if (selectedStrategies.length === 0) {
      message.warning('请选择至少一个策略');
      return;
    }
    
    setLoading(true);
    setResults({});
    try {
      const start = dateRange[0].format('YYYYMMDD');
      const end = dateRange[1].format('YYYYMMDD');
      const res = await analyzeStrategies(start, end, selectedStrategies);
      if (res.success) {
        setResults(res.data);
        message.success(`分析完成，共找到 ${res.total} 只符合条件的股票`);
      } else {
        message.error(res.message || '分析失败');
      }
    } catch (error) {
      message.error('策略分析失败');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (Object.keys(results).length === 0) {
      message.warning('没有可导出的数据');
      return;
    }
    
    setExporting(true);
    try {
      await exportResults(results);
      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    } finally {
      setExporting(false);
    }
  };

  const getStrategyName = (strategyKey: string) => {
    const strategy = strategies.find(s => s.value === strategyKey);
    return strategy?.name || strategyKey;
  };


  return (
    <div style={{ padding: '24px' }}>
      <Title level={4}>策略分析</Title>
      
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* 分析参数 */}
        <Card title="分析参数" size="small">
          <Space wrap>
            <div>
              <span style={{ marginRight: '8px' }}>日期范围：</span>
              <RangePicker
                value={dateRange}
                onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
              />
            </div>
            <div>
              <span style={{ marginRight: '8px' }}>选择策略：</span>
              <Select
                mode="multiple"
                placeholder="选择策略..."
                style={{ minWidth: 300 }}
                value={selectedStrategies}
                onChange={setSelectedStrategies}
                loading={loadingStrategies}
                options={strategies.map((s) => ({
                  label: s.name,
                  value: s.value,
                }))}
              />
            </div>
            <Button
              type="primary"
              icon={<ExperimentOutlined />}
              onClick={handleAnalyze}
              loading={loading}
            >
              开始分析
            </Button>
          </Space>
        </Card>

        {/* 分析结果 */}
        <Card 
          title="分析结果" 
          size="small"
          extra={
            Object.keys(results).length > 0 && (
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={handleExport}
                loading={exporting}
                size="small"
              >
                导出CSV
              </Button>
            )
          }
        >
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <Spin size="large" tip="正在分析中..." />
            </div>
          ) : Object.keys(results).length > 0 ? (
            <Collapse defaultActiveKey={Object.keys(results)}>
              {Object.entries(results).map(([strategy, stocks]) => (
                <Panel
                  header={
                    <span>
                      {getStrategyName(strategy)}
                      <Badge
                        count={stocks.length}
                        style={{ marginLeft: '8px', backgroundColor: '#1890ff' }}
                      />
                    </span>
                  }
                  key={strategy}
                >
                  <List
                    size="small"
                    dataSource={stocks.slice(0, 50)}
                    renderItem={(item: AnalysisResult) => (
                      <List.Item>
                        <span style={{ fontWeight: 'bold', marginRight: '8px' }}>{item.code}</span>
                        <span>{item.name}</span>
                        {item.current_price && (
                          <span style={{ marginLeft: '16px', color: '#888' }}>
                            价格: {item.current_price.toFixed(2)}
                          </span>
                        )}
                      </List.Item>
                    )}
                    footer={
                      stocks.length > 50 ? (
                        <div style={{ color: '#888' }}>...共 {stocks.length} 只股票</div>
                      ) : null
                    }
                  />
                </Panel>
              ))}
            </Collapse>
          ) : (
            <Empty description="暂无分析结果，请选择参数后点击开始分析" />
          )}
        </Card>
      </Space>
    </div>
  );
};

export default StrategyPage;
