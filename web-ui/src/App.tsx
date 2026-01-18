import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, ConfigProvider, theme } from 'antd';
import { StockOutlined, LineChartOutlined, ExperimentOutlined } from '@ant-design/icons';
import zhCN from 'antd/locale/zh_CN';

import StocksPage from './pages/StocksPage';
import DailyDataPage from './pages/DailyDataPage';
import StrategyPage from './pages/StrategyPage';

const { Header, Content, Footer } = Layout;

const menuItems = [
  {
    key: '/stocks',
    icon: <StockOutlined />,
    label: <Link to="/stocks">股票信息</Link>,
  },
  {
    key: '/daily-data',
    icon: <LineChartOutlined />,
    label: <Link to="/daily-data">行情数据</Link>,
  },
  {
    key: '/strategy',
    icon: <ExperimentOutlined />,
    label: <Link to="/strategy">策略分析</Link>,
  },
];

const AppLayout: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname === '/' ? '/stocks' : location.pathname;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
        <div style={{ 
          color: '#fff', 
          fontSize: '18px', 
          fontWeight: 'bold', 
          marginRight: '40px',
          whiteSpace: 'nowrap'
        }}>
          A股策略分析系统
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[currentPath]}
          items={menuItems}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ background: '#f0f2f5' }}>
        <Routes>
          <Route path="/" element={<StocksPage />} />
          <Route path="/stocks" element={<StocksPage />} />
          <Route path="/daily-data" element={<DailyDataPage />} />
          <Route path="/strategy" element={<StrategyPage />} />
        </Routes>
      </Content>
      <Footer style={{ textAlign: 'center', background: '#f0f2f5' }}>
        A股策略分析系统 ©2026
      </Footer>
    </Layout>
  );
};

const App: React.FC = () => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff',
        },
      }}
    >
      <BrowserRouter>
        <AppLayout />
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
