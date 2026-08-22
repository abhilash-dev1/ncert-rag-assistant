import { useState, useEffect, useRef } from 'react';
import { FaPaperPlane, FaRobot } from 'react-icons/fa';

export default function AssistPanel({ bookId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Load last 10 chats from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(`assist_chats_${bookId}`);
    if (saved) setMessages(JSON.parse(saved));
  }, [bookId]);

  // Save last 10 chats
  useEffect(() => {
    localStorage.setItem(`assist_chats_${bookId}`, JSON.stringify(messages.slice(-10)));
  }, [messages, bookId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { id: Date.now(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: input, book_id: bookId || null }),
      });
      const data = await response.json();
      const aiMsg = { id: Date.now() + 1, sender: 'ai', text: data.answer || 'No response', sources: data.sources || [] };
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'ai', text: '❌ Backend not reachable. Check server.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => e.key === 'Enter' && sendMessage();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f5f5f5', borderRadius: '12px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ background: '#3182ce', color: 'white', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <FaRobot size={18} />
        <span style={{ fontWeight: 'bold' }}>AI Assistant</span>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#888', marginTop: '30px' }}>
            <FaRobot size={40} style={{ marginBottom: '10px', color: '#3182ce' }} />
            <p>Ask me anything about this chapter!</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: 'flex', justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start', marginBottom: '8px' }}>
            <div style={{ maxWidth: '80%', padding: '8px 12px', borderRadius: '12px', background: msg.sender === 'user' ? '#3182ce' : '#e0e0e0', color: msg.sender === 'user' ? 'white' : '#333' }}>
              {msg.text}
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ fontSize: '10px', marginTop: '4px', opacity: 0.7 }}>📖 {msg.sources.join(', ')}</div>
              )}
            </div>
          </div>
        ))}
        {loading && <div style={{ color: '#888' }}>Thinking...</div>}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '10px', background: 'white', borderTop: '1px solid #e0e0e0' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyPress={handleKeyPress} placeholder="Ask a question..." style={{ flex: 1, padding: '8px 12px', borderRadius: '20px', border: '1px solid #ccc', fontSize: '14px' }} />
          <button onClick={sendMessage} style={{ background: '#3182ce', color: 'white', border: 'none', borderRadius: '50%', width: '36px', height: '36px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FaPaperPlane size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}