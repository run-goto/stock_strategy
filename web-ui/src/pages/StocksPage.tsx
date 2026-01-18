import React, { useState, useEffect } from 'react';
import { Table, Input, Button, Card, message, Badge, Typography, Modal } from 'antd';
import { SearchOutlined, SyncOutlined, ReloadOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { getStocks, syncStocks } from '../api';
import type { Stock } from '../api';

const { Title } = Typography;
const { confirm } = Modal;

const StocksPage: React.FC = () => {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 50 });

  const fetchStocks = async (search?: string, page = 1, pageSize = 50) => {
    setLoading(true);
    try {
      const offset = (page - 1) * pageSize;
      const res = await getStocks(search, pageSize, offset);
      if (res.success) {
        setStocks(res.data);
        setTotal(res.total);
      }
    } catch (error) {
      message.error('获取股票列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStocks();
  }, []);

  const handleSearch = () => {
    setPagination({ ...pagination, current: 1 });
    fetchStocks(searchText, 1, pagination.pageSize);
  };

  const doSync = async () => {
    setSyncing(true);
    try {
      const res = await syncStocks();
      if (res.success) {
        message.success(res.message);
        fetchStocks(searchText, pagination.current, pagination.pageSize);
      } else {
        message.error(res.message);
      }
    } catch (error) {
      message.error('同步股票列表失败');
    } finally {
      setSyncing(false);
    }
  };

  const handleSync = () => {
    confirm({
      title: '确认刷新股票列表？',
      icon: <ExclamationCircleOutlined />,
      content: '这将从akshare获取最新的A股股票列表并更新数据库，可能需要一些时间。',
      okText: '确认',
      cancelText: '取消',
      onOk: doSync,
    });
  };

  const handleTableChange = (paginationConfig: any) => {
    setPagination(paginationConfig);
    fetchStocks(searchText, paginationConfig.current, paginationConfig.pageSize);
  };

  const columns: ColumnsType<Stock> = [
    {
      title: '股票代码',
      dataIndex: 'code',
      key: 'code',
      width: 120,
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 200,
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={4} style={{ margin: 0 }}>股票基础信息管理</Title>
          <Badge count={total} showZero style={{ backgroundColor: '#1890ff' }} overflowCount={99999}>
            <span style={{ marginRight: '8px' }}>共</span>
          </Badge>
        </div>
        
        <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
          <Input.Search
            placeholder="搜索代码或名称..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 300 }}
            enterButton={<SearchOutlined />}
          />
          <Button 
            type="primary" 
            icon={<SyncOutlined spin={syncing} />} 
            onClick={handleSync}
            loading={syncing}
          >
            刷新股票列表
          </Button>
          <Button 
            icon={<ReloadOutlined />} 
            onClick={() => fetchStocks(searchText, pagination.current, pagination.pageSize)}
          >
            刷新
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={stocks}
          rowKey="code"
          loading={loading}
          pagination={{
            ...pagination,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          onChange={handleTableChange}
          size="small"
        />
      </Card>
    </div>
  );
};

export default StocksPage;
