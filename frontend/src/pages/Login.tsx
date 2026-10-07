import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Form, Input, Button, Typography, message, Tabs } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useAuthStore } from '../stores/authStore'
import apiClient from '../api/client'

const { Title } = Typography

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const handleSubmit = async (values: any) => {
    setLoading(true)
    try {
      const endpoint = tab === 'login' ? '/api/auth/login' : '/api/auth/register'
      const payload = tab === 'login'
        ? { username: values.username, password: values.password }
        : { ...values, role: 'employee', security_level: '内部' }

      const { data } = await apiClient.post(endpoint, payload)
      login(data.access_token, data.refresh_token, data.user)
      message.success(tab === 'login' ? '登录成功' : '注册成功')
      navigate('/dashboard')
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <Card style={{ width: 420, borderRadius: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.15)' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2} style={{ margin: 0, color: '#1677ff' }}>智汇 AskKB</Title>
          <Typography.Text type="secondary">企业级 RAG 知识库平台</Typography.Text>
        </div>

        <Tabs
          activeKey={tab}
          onChange={(key) => setTab(key as 'login' | 'register')}
          centered
          items={[
            { key: 'login', label: '登录' },
            { key: 'register', label: '注册' },
          ]}
        />

        <Form onFinish={handleSubmit} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, min: 4, message: '密码至少4位' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          {tab === 'register' && (
            <>
              <Form.Item name="display_name" rules={[{ required: true, message: '请输入显示名称' }]}>
                <Input placeholder="显示名称" />
              </Form.Item>
              <Form.Item name="department">
                <Input placeholder="部门（可选）" />
              </Form.Item>
            </>
          )}
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              {tab === 'login' ? '登录' : '注册'}
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}