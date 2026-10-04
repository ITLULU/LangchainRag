import { useEffect, useState } from 'react'
import { Card, Col, Row, Statistic, Typography, Spin } from 'antd'
import {
  BookOutlined, FileTextOutlined, MessageOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons'
import apiClient from '../api/client'

const { Title } = Typography

interface Stats {
  total_kbs: number
  total_docs: number
  total_queries: number
  avg_confidence: number
  reject_rate: number
  self_service_rate: number
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient.get('/api/dashboard/knowledge-ops')
      .then(({ data }) => setStats(data))
      .catch(() => setStats({ total_kbs: 0, total_docs: 0, total_queries: 0, avg_confidence: 0, reject_rate: 0, self_service_rate: 0 }))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>知识运营看板</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="知识库总数" value={stats?.total_kbs || 0} prefix={<BookOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="文档总数" value={stats?.total_docs || 0} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="累计问答" value={stats?.total_queries || 0} prefix={<MessageOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="平均置信度"
              value={stats?.avg_confidence || 0}
              precision={2}
              suffix={`/ 1.0`}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card>
            <Statistic
              title="自助解决率"
              value={stats?.self_service_rate || 0}
              precision={1}
              suffix="%"
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card>
            <Statistic
              title="拒答率"
              value={stats?.reject_rate || 0}
              precision={1}
              suffix="%"
              valueStyle={{ color: '#cf1322' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}