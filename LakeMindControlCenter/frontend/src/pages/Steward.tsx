import { Card, Input, Button, List, Typography } from 'antd';
import { useState, useRef } from 'react';
import { api } from '../api/client';

const { Text } = Typography;

export default function Steward() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([
    { role: 'system', content: 'Steward chat ready. Ask about platform health, inspection, or actions.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  function connect() {
    if (wsRef.current) return;
    const bffUrl = import.meta.env.VITE_BFF_URL || 'http://localhost:3001';
    const wsUrl = bffUrl.replace('http', 'ws') + '/ws';
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'pong' && data.data) {
          setMessages(prev => [...prev, { role: 'assistant', content: data.data }]);
        }
      } catch {}
      setLoading(false);
    };
    wsRef.current = ws;
  }

  function send() {
    if (!input.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    setLoading(true);
    connect();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(input);
    } else {
      setTimeout(() => wsRef.current?.send(input), 500);
    }
    setInput('');
  }

  return (
    <Card title="Steward Chat" style={{ height: '100%' }}>
      <div style={{ marginBottom: 16, maxHeight: 400, overflow: 'auto' }}>
        <List
          dataSource={messages}
          renderItem={(msg) => (
            <List.Item>
              <div style={{ width: '100%' }}>
                <Text strong color={msg.role === 'user' ? '#1677ff' : undefined}>
                  {msg.role}:
                </Text>{' '}
                <Text>{msg.content}</Text>
              </div>
            </List.Item>
          )}
        />
      </div>
      <Input.Group compact>
        <Input
          style={{ width: 'calc(100% - 80px)' }}
          value={input}
          onChange={e => setInput(e.target.value)}
          onPressEnter={send}
          placeholder="Ask Steward..."
          disabled={loading}
        />
        <Button type="primary" onClick={send} loading={loading}>Send</Button>
      </Input.Group>
    </Card>
  );
}
