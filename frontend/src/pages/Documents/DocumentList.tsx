import { useEffect, useState } from 'react'
import {
  Table, Button, Modal, Form, Input, Select, Space, Typography, message,
  Tag, Upload, Card,
} from 'antd'
import {
  PlusOutlined, UploadOutlined, ReloadOutlined, DeleteOutlined,
} from '@ant-design/icons'
import apiClient from '../../api/client'

const { Title } = Typography

interface Document {
  id: string
  kb_id: string
  title: string
  security_level: string
  status: string
  current_version: number
  created_at: string
}

interface KB { id: string; name: string; collection_name: string }

export default function DocumentListPage() {
  const [docs, setDocs] = useState<Document[]>([])
  const [kbs, setKbs] = useState<KB[]>([])
  const [loading, setLoading] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedKB, setSelectedKB] = useState<string | null>(null)
  const [form] = Form.useForm()

  const fetchDocs = async () => {
    setLoading(true)
    try {
      const params: any = { page_size: 100 }
      if (selectedKB) params.kb_id = selectedKB
      const { data } = await apiClient.get('/api/documents', { params })
      setDocs(data.items || [])
    } catch { message.error('获取文档列表失败') }
    finally { setLoading(false) }
  }

  const fetchKBs = async () => {
    try {
      const { data } = await apiClient.get('/api/kb', { params: { page_size: 100 } })
      setKbs(data.items || [])
    } catch { }
  }

  useEffect(() => {
    fetchKBs()
    fetchDocs()
  }, [])

  useEffect(() => { fetchDocs() }, [selectedKB])

  const handleUpload = async () => {
    const values = await form.validateFields()
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', values.file.file.originFileObj)
      formData.append('kb_id', values.kb_id)
      formData.append('title', values.title)
      formData.append('security_level', values.security_level || '公开')

      await apiClient.post('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      message.success('上传成功，正在入库...')
      setUploadOpen(false)
      fetchDocs()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api/documents/${id}`)
      message.success('已删除')
      fetchDocs()
    } catch { message.error('删除失败') }
  }

  const columns = [
    { title: '文档标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '密级', dataIndex: 'security_level', key: 'security_level', width: 80,
      render: (v: string) => {
        const colorMap: Record<string, string> = { '公开': 'green', '内部': 'blue', '机密': 'red' }
        return <Tag color={colorMap[v] || 'default'}>{v}</Tag>
      },
    },
    { title: '版本', dataIndex: 'current_version', key: 'version', width: 60 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'default'}>{v}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (v: string) => v?.split('T')[0] },
    {
      title: '操作', key: 'actions', width: 100,
      render: (_: any, record: Document) => (
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>
          删除
        </Button>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>文档管理</Title>
        <Space>
          <Select
            placeholder="按知识库筛选"
            allowClear
            style={{ width: 200 }}
            value={selectedKB}
            onChange={setSelectedKB}
            options={kbs.map(kb => ({ label: kb.name, value: kb.id }))}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchDocs}>刷新</Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => {
            setUploadOpen(true)
            form.resetFields()
          }}>上传文档</Button>
        </Space>
      </div>

      <Table dataSource={docs} columns={columns} rowKey="id" loading={loading} />

      <Modal
        title="上传文档"
        open={uploadOpen}
        onOk={handleUpload}
        onCancel={() => setUploadOpen(false)}
        confirmLoading={uploading}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="文档标题" rules={[{ required: true }]}>
            <Input placeholder="如：员工手册V3" />
          </Form.Item>
          <Form.Item name="kb_id" label="所属知识库" rules={[{ required: true }]}>
            <Select options={kbs.map(kb => ({ label: kb.name, value: kb.id }))} />
          </Form.Item>
          <Form.Item name="security_level" label="密级" initialValue="公开">
            <Select options={[
              { label: '公开', value: '公开' },
              { label: '内部', value: '内部' },
              { label: '机密', value: '机密' },
            ]} />
          </Form.Item>
          <Form.Item name="file" label="选择文件" rules={[{ required: true }]}
            valuePropName="file" getValueFromEvent={(e) => e?.fileList ? { file: e.fileList[0] } : undefined}
          >
            <Upload maxCount={1} beforeUpload={() => false}>
              <Button icon={<UploadOutlined />}>选择文件 (PDF/Word/Excel/PPT/TXT/MD)</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}