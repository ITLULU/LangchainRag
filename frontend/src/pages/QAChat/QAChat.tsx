import { useState, useRef, useEffect } from 'react'
import {
  Card, Input, Button, Select, Space, Typography, Tag, Divider,
  Spin, Empty, List, message, Segmented, Collapse, Tooltip,
} from 'antd'
import {
  SendOutlined, UserOutlined, RobotOutlined, ClearOutlined,
  FileTextOutlined, SafetyCertificateOutlined, ReloadOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import apiClient from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Text, Paragraph } = Typography

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  confidence?: number
  refused?: boolean
  handoff?: boolean
  streaming?: boolean
}

interface Citation {
  no: number
  doc: string
  page: number
  snippet: string
  score: number
}

export default function QAChatPage() {
  const { user } = useAuthStore()
  const [channel, setChannel] = useState<string>(user?.channel_scope || 'employee_kb')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<any>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const q = question.trim()
    if (!q || loading) return

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: q }
    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      streaming: true,
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setQuestion('')
    setLoading(true)

    try {
      const token = useAuthStore.getState().token
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          channel,
          question: q,
          conversation_id: conversationId,
          stream: true,
        }),
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || '请求失败')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''
      let finalData: any = null

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim())

              if (line.includes('"event":"chunk"') || data.content) {
                fullContent += data.content || ''
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: fullContent, streaming: true }
                      : m,
                  ),
                )
              } else if (line.includes('"event":"done"') || data.citations) {
                finalData = data
              } else if (data.answer) {
                finalData = data
              }
            } catch { }
          }
        }
      }

      // 更新最终消息
      if (finalData) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? {
                  ...m,
                  content: finalData.answer || fullContent,
                  citations: finalData.citations,
                  confidence: finalData.confidence,
                  refused: finalData.refused,
                  handoff: finalData.handoff,
                  streaming: false,
                }
              : m,
          ),
        )
        if (finalData.conversation_id) {
          setConversationId(finalData.conversation_id)
        }
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, content: fullContent, streaming: false }
              : m,
          ),
        )
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: `❌ 错误: ${err.message}`, streaming: false }
            : m,
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setMessages([])
    setConversationId(null)
    message.info('已清空对话')
  }

  const channelLabel = channel === 'cs_agent' ? '智能客服 (cs_agent)' : '员工手册 (employee_kb)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      {/* 顶部控制栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>问答对话</Title>
        <Space>
          <Segmented
            value={channel}
            onChange={(val) => { setChannel(val as string); handleClear() }}
            options={[
              { label: '员工通道', value: 'employee_kb', icon: <SafetyCertificateOutlined /> },
              { label: '客服通道', value: 'cs_agent', icon: <RobotOutlined /> },
            ]}
          />
          <Tag color={channel === 'cs_agent' ? 'green' : 'blue'}>{channelLabel}</Tag>
          <Button icon={<ClearOutlined />} onClick={handleClear} disabled={messages.length === 0}>
            清空对话
          </Button>
        </Space>
      </div>

      {/* 消息列表 */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        padding: 16,
        marginBottom: 16,
        background: '#fafafa',
      }}>
        {messages.length === 0 ? (
          <Empty
            description="开始问答——支持双通道架构"
            style={{ marginTop: 80 }}
          >
            <Text type="secondary">
              员工通道：有权限过滤，可访问内部/机密知识<br />
              客服通道：仅公开知识，高阈值宁可不答
            </Text>
          </Empty>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} style={{
              marginBottom: 20,
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              <div style={{
                maxWidth: '80%',
                background: msg.role === 'user' ? '#1677ff' : '#fff',
                color: msg.role === 'user' ? '#fff' : '#333',
                borderRadius: 12,
                padding: '12px 16px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
              }}>
                {/* 头像和角色 */}
                <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                  {msg.role === 'user' ? (
                    <Space><UserOutlined /><Text style={{ color: '#fff' }}>我</Text></Space>
                  ) : (
                    <Space>
                      <RobotOutlined />
                      <Text strong>AskKB</Text>
                      {msg.streaming && <Tag color="processing" style={{ margin: 0 }}>生成中...</Tag>}
                      {msg.confidence !== undefined && (
                        <Tooltip title="置信度">
                          <Tag color={msg.confidence > 0.5 ? 'green' : 'orange'}>
                            {((msg.confidence || 0) * 100).toFixed(0)}%
                          </Tag>
                        </Tooltip>
                      )}
                      {msg.refused && <Tag color="red">已拒答</Tag>}
                      {msg.handoff && <Tag color="orange">转人工</Tag>}
                    </Space>
                  )}
                </div>

                {/* 内容 */}
                <div style={{ lineHeight: 1.8 }}>
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  ) : (
                    <Paragraph style={{ color: '#fff', margin: 0 }}>{msg.content}</Paragraph>
                  )}
                  {msg.streaming && msg.role === 'assistant' && (
                    <span className="cursor-blink" style={{
                      display: 'inline-block', width: 2, height: 16,
                      background: '#1677ff', marginLeft: 2, verticalAlign: 'middle',
                    }} />
                  )}
                </div>

                {/* 引用 */}
                {msg.citations && msg.citations.length > 0 && (
                  <Collapse
                    size="small"
                    ghost
                    items={[{
                      key: 'citations',
                      label: <Text type="secondary">📎 引用来源 ({msg.citations.length}条)</Text>,
                      children: (
                        <div style={{ maxHeight: 200, overflow: 'auto' }}>
                          {msg.citations.map((c) => (
                            <div key={c.no} style={{
                              padding: '4px 0',
                              borderBottom: '1px solid #f0f0f0',
                              fontSize: 12,
                            }}>
                              <Space size={4}>
                                <Tag color="blue">[{c.no}]</Tag>
                                <Text strong>{c.doc}</Text>
                                <Text type="secondary">P{c.page}</Text>
                                <Tag color={c.score > 0.5 ? 'green' : 'orange'}>
                                  相关度: {(c.score * 100).toFixed(0)}%
                                </Tag>
                              </Space>
                              <div style={{ marginTop: 4, color: '#666' }}>
                                {c.snippet}
                              </div>
                            </div>
                          ))}
                        </div>
                      ),
                    }]}
                  />
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区 */}
      <Card size="small" style={{ borderRadius: 8 }}>
        <Input.TextArea
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) { e.preventDefault(); handleSend() }
          }}
          placeholder={channel === 'cs_agent'
            ? '输入客服问题，按 Enter 发送...'
            : '输入您想查询的内部知识，按 Enter 发送...'}
          autoSize={{ minRows: 2, maxRows: 6 }}
          disabled={loading}
          style={{ marginBottom: 8 }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Shift+Enter 换行 | 当前通道: {channelLabel}
          </Text>
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!question.trim()}
          >
            {loading ? '生成中...' : '发送'}
          </Button>
        </div>
      </Card>
    </div>
  )
}

// 注入闪烁动画样式
const styleSheet = document.createElement('style')
styleSheet.textContent = `
  .cursor-blink {
    animation: blink 1s step-end infinite;
  }
  @keyframes blink {
    50% { opacity: 0; }
  }
`
document.head.appendChild(styleSheet)