import { Card, Form, Input, Button, message, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/client';

const { Title } = Typography;

export default function Login() {
  const navigate = useNavigate();

  async function onFinish(values: { username: string; password: string }) {
    try {
      await login(values.username, values.password);
      navigate('/overview');
    } catch {
      message.error('Login failed. Check credentials.');
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f2f5' }}>
      <Card style={{ width: 400 }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 32 }}>LakeMind Control Center</Title>
        <Form onFinish={onFinish} layout="vertical">
          <Form.Item name="username" label="Username" rules={[{ required: true }]}>
            <Input placeholder="admin" />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true }]}>
            <Input.Password placeholder="Enter password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Login</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
