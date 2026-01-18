import React, { useState, useEffect } from 'react';
import { Card, Select, DatePicker, Button, Space, message, Descriptions, Tag, Typography, Modal } from 'antd';
import { SyncOutlined, CloudDownloadOutlined, ThunderboltOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getStocks, getLoadedDates, getDailyData, syncDailyData, syncBatchDaily, syncTodayDaily } from '../api';
import type { Stock, DailyData } from '../api';

const { Title } = Typography;
const { RangePicker } = DatePicker;
const { confirm } = Modal;

const DailyDataPage: React.FC = () => {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedCode, setSelectedCode] = useState<string | undefined>();
  const [loadedDates, setLoadedDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | undefined>();
  const [dailyData, setDailyData] = useState<DailyData | null>(null);
  
  const [singleDateRange, setSingleDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [batchDateRange, setBatchDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  
  const [loadingSingle, setLoadingSingle] = useState(false);
  const [loadingBatch, setLoadingBatch] = useState(false);
  const [loadingToday, setLoadingToday] = useState(false);
  const [loadingStocks, setLoadingStocks] = useState(false);

  useEffect(() => {
    fetchStocks();
  }, []);

  useEffect(() => {
    if (selectedCode) {
      fetchLoadedDates(selectedCode);
    }
  }, [selectedCode]);

  const fetchStocks = async () => {
    setLoadingStocks(true);
    try {
      const res = await getStocks(undefined, 5000);
      if (res.success) {
        setStocks(res.data);
      }
    } catch (error) {
      message.error('获取股票列表失败');
    } finally {
      setLoadingStocks(false);
    }
  };

  const fetchLoadedDates = async (code: string) => {
    try {
      const res = await getLoadedDates(code);
      if (res.success) {
        setLoadedDates(res.dates);
      }
    } catch (error) {
      message.error('获取已加载日期失败');
    }
  };

  const handleDateClick = async (date: string) => {
    setSelectedDate(date);
    if (selectedCode) {
      try {
        const res = await getDailyData(selectedCode, date);
        if (res.success) {
          setDailyData(res.data);
        }
      } catch (error) {
        message.error('获取行情数据失败');
      }
    }
  };

  const handleLoadSingle = async () => {
    if (!selectedCode || !singleDateRange) {
      message.warning('请选择股票和日期范围');
      return;
    }
    setLoadingSingle(true);
    try {
      const start = singleDateRange[0].format('YYYYMMDD');
      const end = singleDateRange[1].format('YYYYMMDD');
      const res = await syncDailyData(selectedCode, start, end);
      if (res.success) {
        message.success(`加载完成，共 ${res.count} 条数据`);
        fetchLoadedDates(selectedCode);
      } else {
        message.error(res.error || '加载失败');
      }
    } catch (error) {
      message.error('加载行情数据失败');
    } finally {
      setLoadingSingle(false);
    }
  };

  const doLoadBatch = async () => {
    if (!batchDateRange) {
      message.warning('请选择日期范围');
      return;
    }
    setLoadingBatch(true);
    try {
      const start = batchDateRange[0].format('YYYYMMDD');
      const end = batchDateRange[1].format('YYYYMMDD');
      const res = await syncBatchDaily(start, end);
      if (res.success) {
        message.success(res.message);
      } else {
        message.error(res.message || '批量加载失败');
      }
    } catch (error) {
      message.error('批量加载失败');
    } finally {
      setLoadingBatch(false);
    }
  };

  const handleLoadBatch = () => {
    if (!batchDateRange) {
      message.warning('请选择日期范围');
      return;
    }
    const start = batchDateRange[0].format('YYYY-MM-DD');
    const end = batchDateRange[1].format('YYYY-MM-DD');
    confirm({
      title: '确认批量加载全部股票数据？',
      icon: <ExclamationCircleOutlined />,
      content: `这将加载 ${start} 至 ${end} 的所有股票行情数据，可能需要较长时间。`,
      okText: '确认',
      cancelText: '取消',
      onOk: doLoadBatch,
    });
  };

  const doSyncToday = async () => {
    setLoadingToday(true);
    try {
      const res = await syncTodayDaily();
      if (res.success) {
        message.success(res.message);
        if (selectedCode) {
          fetchLoadedDates(selectedCode);
        }
      } else {
        message.error(res.message || '同步失败');
      }
    } catch (error) {
      message.error('同步当天数据失败');
    } finally {
      setLoadingToday(false);
    }
  };

  const handleSyncToday = () => {
    confirm({
      title: '确认同步当天交易数据？',
      icon: <ExclamationCircleOutlined />,
      content: '这将同步今天所有股票的交易数据，可能需要较长时间。',
      okText: '确认',
      cancelText: '取消',
      onOk: doSyncToday,
    });
  };

  const formatDate = (date: string) => {
    if (date.length === 8) {
      return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
    }
    return date;
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={4}>每日行情数据管理</Title>
      
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* 选择股票 */}
        <Card title="选择股票" size="small">
          <Select
            showSearch
            placeholder="选择或搜索股票代码..."
            style={{ width: 400 }}
            value={selectedCode}
            onChange={setSelectedCode}
            loading={loadingStocks}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={stocks.map((s) => ({
              label: `${s.code} - ${s.name}`,
              value: s.code,
            }))}
          />
        </Card>

        {/* 加载单只股票数据 */}
        <Card title="加载单只股票数据" size="small">
          <Space>
            <RangePicker
              value={singleDateRange}
              onChange={(dates) => setSingleDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
            />
            <Button
              type="primary"
              icon={<CloudDownloadOutlined />}
              onClick={handleLoadSingle}
              loading={loadingSingle}
              disabled={!selectedCode}
            >
              加载
            </Button>
          </Space>
        </Card>

        {/* 批量加载 */}
        <Card title="批量加载全部股票数据" size="small">
          <Space>
            <RangePicker
              value={batchDateRange}
              onChange={(dates) => setBatchDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
            />
            <Button
              type="primary"
              icon={<SyncOutlined spin={loadingBatch} />}
              onClick={handleLoadBatch}
              loading={loadingBatch}
            >
              加载全部股票
            </Button>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={handleSyncToday}
              loading={loadingToday}
              style={{ backgroundColor: '#13c2c2', borderColor: '#13c2c2' }}
            >
              同步当天交易
            </Button>
          </Space>
        </Card>

        {/* 已加载日期和详情 */}
        <div style={{ display: 'flex', gap: '16px' }}>
          <Card title="已加载的交易日" size="small" style={{ flex: 1 }}>
            {selectedCode ? (
              loadedDates.length > 0 ? (
                <div style={{ maxHeight: '300px', overflow: 'auto' }}>
                  <p style={{ color: '#888', marginBottom: '8px' }}>共 {loadedDates.length} 个交易日</p>
                  <Space wrap>
                    {loadedDates.slice(0, 50).map((date) => (
                      <Tag
                        key={date}
                        color={selectedDate === date ? 'blue' : 'default'}
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleDateClick(date)}
                      >
                        {formatDate(date)}
                      </Tag>
                    ))}
                  </Space>
                </div>
              ) : (
                <span style={{ color: '#888' }}>该股票暂无已加载的数据</span>
              )
            ) : (
              <span style={{ color: '#888' }}>请选择股票代码</span>
            )}
          </Card>

          <Card title="行情详情" size="small" style={{ flex: 2 }}>
            {dailyData ? (
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="股票代码">{dailyData.code}</Descriptions.Item>
                <Descriptions.Item label="交易日期">{formatDate(dailyData.trade_date)}</Descriptions.Item>
                <Descriptions.Item label="开盘价">{dailyData.open?.toFixed(2) ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="收盘价">{dailyData.close?.toFixed(2) ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="最高价">{dailyData.high?.toFixed(2) ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="最低价">{dailyData.low?.toFixed(2) ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="成交量">{dailyData.volume?.toLocaleString() ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="成交额">{dailyData.amount?.toLocaleString() ?? '-'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <span style={{ color: '#888' }}>点击左侧日期查看详情</span>
            )}
          </Card>
        </div>
      </Space>
    </div>
  );
};

export default DailyDataPage;
