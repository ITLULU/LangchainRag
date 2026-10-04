import { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, Select, Space, Typography, message, Tag, Popconfirm, Card } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import apiClient from '../../api/client'

const { Title } = Typography

interface KB {
  id: string
  name: string
  description: string
  channel_type: string
  collection_name: string
  owner_dept: string
  visibility: string
  status: string
  doc_count: number
  chunk_count: number
  created_at: string
}

export default function KBListPage() {
  const [kbs, setKbs] = useState<KB[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingKB, setEditingKB] = useState<KB | null>(null)
  const [form] = Form.useForm()

  const fetchKBs = async () => {
    setLoading(true)
    try {
      const { data } = await apiClient.get('/api/kb', { params: { page_size: 100 } })
      setKbs(data.items || [])
    } catch { message.error('获取知识库列表失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchKBs() }, [])

  const handleCreate = () => {
    setEditingKB(null)
    form.resetFields()
    setModalOpen(true)
  }

  const handleEdit = (kb: KB) => {
    setEditingKB(kb)
    form.setFieldsValue(kb)
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    try {
      if (editingKB) {
        await apiClient.put(`/api/kb/${editingKB.id}`, values)
        message.success('已更新')
      } else {
        await apiClient.post('/api/kb', values)
        message.success('创建成功')
      }
      setModalOpen(false)
      fetchKBs()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api/kb/${id}`)
      message.success('已删除')
      fetchKBs()
    } catch { message.error('删除失败') }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '通道', dataIndex: 'channel_type', key: 'channel_type', width: 120,
      render: (v: string) => (
        <Tag color={v === 'cs_agent' ? 'green' : 'blue'}>
          {v === 'cs_agent' ? '智能客服' : '员工手册'}
        </Tag>
      ),
    },
    { title: '部门', dataIndex: 'owner_dept', key: 'owner_dept', width: 100 },
    { title: '文档数', dataIndex: 'doc_count', key: 'doc_count', width: 80 },
    { title: '切片数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'default'}>{v}</Tag>,
    },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_: any, record: KB) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>知识库管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchKBs}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建知识库</Button>
        </Space>
      </div>

      <Table dataSource={kbs} columns={columns} rowKey="id" loading={loading} scroll={{ x: 900 }} />

      <Modal
        title={editingKB ? '编辑知识库' : '新建知识库'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="知识库名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="描述信息" />
          </Form.Item>
          <Form.Item name="channel_type" label="通道类型" initialValue="employee_kb">
            <Select options={[
              { label: '企业员工手册 (employee_kb)', value: 'employee_kb' },
              { label: '智能客服 (cs_agent)', value: 'cs_agent' },
            ]} />
          </Form.Item>
          <Form.Item name="owner_dept" label="所属部门" initialValue="通用部门">
            <Input />
          </Form.Item>
          <Space>
            <Form.Item name="chunk_size" label="切片大小" initialValue={800}>
              <Input type="number" style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="chunk_overlap" label="重叠长度" initialValue={150}>
              <Input type="number" style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="reject_threshold" label="拒答阈值" initialValue={0.35}>
              <Input type="number" step={0.05} style={{ width: 100 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}