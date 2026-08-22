import { useState, useEffect, useRef } from 'react';
import { FaPaperPlane, FaRobot, FaUser, FaTrash, FaDatabase, FaSearch, FaHistory, FaTimes, FaPlus, FaChevronLeft } from 'react-icons/fa';

export default function ChatPage({ bookId, userId = 1 }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  // Load chat history (list of sessions)
  useEffect(() => {
    fetch(`http://localhost:8000/api/chat/history/${userId}`)
      .then(res => res.json())
      .then(data => setHistory(data.history || []))
      .catch(err => console.error("Failed to load history:", err));
  }, [userId]);

  // ✅ NEW CHAT - Start fresh
  const startNewChat = () => {
    setMessages([]);
    setInput('');
    setCurrentSessionId(null);
    
    // Create new session in database
    fetch(`http://localhost:8000/api/chat/new?user_id=${userId}&book_id=${bookId || ''}`)
      .then(res => res.json())
      .then(data => {
        setCurrentSessionId(data.session_id);
      });
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { id: Date.now(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      // If no session exists, create one
      if (!currentSessionId) {
        const newChatRes = await fetch(`http://localhost:8000/api/chat/new?user_id=${userId}&book_id=${bookId || ''}`);
        const newChatData = await newChatRes.json();
        setCurrentSessionId(newChatData.session_id);
      }

      // Send message to backend (which saves to DB)
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: input, book_id: bookId || null }),
      });

      const data = await response.json();
      
      const aiMsg = {
        id: Date.now() + 1,
        sender: 'ai',
        text: data.answer || 'No response',
        sources: data.sources || [],
        chunks: data.chunks || [],
        scores: data.scores || []
      };
      setMessages(prev => [...prev, aiMsg]);
      
      // Refresh history list
      fetch(`http://localhost:8000/api/chat/history/${userId}`)
        .then(res => res.json())
        .then(data => setHistory(data.history || []));
      
    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'ai', text: '❌ Backend not reachable. Check server.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => e.key === 'Enter' && sendMessage();

  const clearChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  // ✅ LOAD A SPECIFIC CHAT FROM HISTORY
  const loadChatFromHistory = (sessionId) => {
    fetch(`http://localhost:8000/api/chat/${sessionId}`)
      .then(res => res.json())
      .then(data => {
        const loadedMessages = data.messages.map((msg, idx) => ({
          id: Date.now() + idx,
          sender: msg.sender,
          text: msg.text,
          sources: msg.sources ? JSON.parse(msg.sources) : []
        }));
        setMessages(loadedMessages);
        setCurrentSessionId(sessionId);
        setShowHistory(false);
      });
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: 'linear-gradient(135deg, #f5f7fa, #c3cfe2)',
      borderRadius: '16px',
      overflow: 'hidden',
      boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
      fontFamily: "'Inter', sans-serif"
    }}>
      
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #8b0000, #b22222)',
        color: 'white',
        padding: '14px 20px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FaRobot size={22} />
          <div>
            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>AI Tutor Chat</div>
            <div style={{ fontSize: '12px', opacity: 0.8 }}>ChatGPT-style conversations</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {/* ✅ NEW CHAT BUTTON */}
          <button 
            onClick={startNewChat}
            style={{ 
              background: 'rgba(255,255,255,0.2)', 
              color: 'white', 
              border: 'none', 
              borderRadius: '20px', 
              padding: '6px 12px', 
              cursor: 'pointer', 
              fontSize: '12px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <FaPlus size={12} /> New Chat
          </button>

          <button 
            onClick={() => setShowHistory(true)}
            style={{ 
              background: 'rgba(255,255,255,0.2)', 
              color: 'white', 
              border: 'none', 
              borderRadius: '20px', 
              padding: '6px 12px', 
              cursor: 'pointer', 
              fontSize: '12px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <FaHistory size={12} /> History
          </button>
          <button onClick={clearChat} style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', borderRadius: '20px', padding: '6px 12px', cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <FaTrash size={12} /> Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px',
        scrollbarWidth: 'none',
        msOverflowStyle: 'none'
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '50px', color: '#888' }}>
            <FaRobot size={50} style={{ marginBottom: '12px', color: '#8b0000' }} />
            <p style={{ fontSize: '16px' }}>Start a new conversation!</p>
            <p style={{ fontSize: '13px', color: '#aaa' }}>Click "New Chat" to begin, or "History" to see past chats.</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} style={{
            display: 'flex',
            justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '12px',
            alignItems: 'flex-end',
            gap: '8px'
          }}>
            {msg.sender === 'ai' && (
              <div style={{ width: '30px', height: '30px', borderRadius: '50%', background: 'linear-gradient(135deg, #8b0000, #b22222)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <FaRobot size={14} />
              </div>
            )}
            
            <div style={{
              maxWidth: '80%',
              padding: '12px 16px',
              borderRadius: msg.sender === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
              background: msg.sender === 'user' ? 'linear-gradient(135deg, #8b0000, #b22222)' : 'white',
              color: msg.sender === 'user' ? 'white' : '#333',
              boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
              fontSize: '14px',
              lineHeight: '1.5'
            }}>
              {msg.text}
              
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ fontSize: '11px', marginTop: '8px', opacity: 0.8, borderTop: '1px solid rgba(0,0,0,0.1)', paddingTop: '6px' }}>
                  <FaDatabase style={{ marginRight: '4px' }} /> Sources: {msg.sources.join(', ')}
                </div>
              )}

              {msg.chunks && msg.chunks.length > 0 && (
                <div style={{
                  marginTop: '10px',
                  background: '#f0f4ff',
                  borderRadius: '8px',
                  padding: '10px',
                  border: '1px solid #c7d2fe'
                }}>
                  <div style={{ fontWeight: 'bold', fontSize: '12px', color: '#1e3a8a', marginBottom: '6px' }}>
                    <FaSearch style={{ marginRight: '4px' }} /> Retrieved Knowledge:
                  </div>
                  {msg.chunks.map((chunk, idx) => (
                    <div key={idx} style={{ fontSize: '11px', color: '#555', marginBottom: '6px', borderLeft: '2px solid #3b82f6', paddingLeft: '8px' }}>
                      <div style={{ fontWeight: 'bold', color: '#2563eb' }}>
                        Chunk {idx + 1} | Score: {msg.scores && msg.scores[idx] ? msg.scores[idx].toFixed(3) : 'N/A'}
                      </div>
                      <div style={{ marginTop: '2px' }}>{chunk.substring(0, 150)}...</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div style={{ width: '30px', height: '30px', borderRadius: '50%', background: '#3182ce', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <FaUser size={14} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ width: '30px', height: '30px', borderRadius: '50%', background: 'linear-gradient(135deg, #8b0000, #b22222)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FaRobot size={14} />
            </div>
            <div style={{ background: 'white', padding: '10px 16px', borderRadius: '18px', color: '#888', fontSize: '14px' }}>
              Retrieving knowledge...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '14px', background: 'white', borderTop: '1px solid #e0e0e0' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question..."
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: '24px',
              border: '1px solid #ddd',
              fontSize: '14px',
              outline: 'none',
              background: '#f9f9f9'
            }}
          />
          <button
            onClick={sendMessage}
            style={{
              background: 'linear-gradient(135deg, #8b0000, #b22222)',
              color: 'white',
              border: 'none',
              borderRadius: '50%',
              width: '44px',
              height: '44px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'transform 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
          >
            <FaPaperPlane size={16} />
          </button>
        </div>
        <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '11px', color: '#aaa' }}>
          Powered by NCERT RAG + Gemini AI
        </div>
      </div>

      {/* ✅ HISTORY PANEL (List of Chats) */}
      {showHistory && (
        <>
          <div onClick={() => setShowHistory(false)} style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.3)', zIndex: 999 }} />
          <div style={{ position: 'fixed', top: 0, right: 0, width: '380px', height: '100vh', background: 'white', zIndex: 1000, boxShadow: '-5px 0 20px rgba(0,0,0,0.2)', padding: '20px', overflowY: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none', fontFamily: "'Inter', sans-serif" }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', color: '#333' }}>
                <FaHistory style={{ marginRight: '8px', color: '#8b0000' }} /> Chat History
              </h3>
              <button onClick={() => setShowHistory(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#666' }}>
                <FaTimes />
              </button>
            </div>

            {history.length === 0 ? (
              <p style={{ textAlign: 'center', color: '#999', marginTop: '50px' }}>No chat history yet.</p>
            ) : (
              history.map((session, idx) => (
                <div key={idx} style={{ marginBottom: '12px', padding: '12px', borderRadius: '8px', background: '#f9f9f9', border: '1px solid #e0e0e0', cursor: 'pointer' }} onClick={() => loadChatFromHistory(session.session_id)}>
                  <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#8b0000', marginBottom: '4px' }}>
                    📝 {session.title || 'Chat Session'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#888', marginBottom: '6px' }}>
                    {session.created_at ? new Date(session.created_at).toLocaleString() : ''}
                  </div>
                  <div style={{ fontSize: '12px', color: '#555', marginTop: '4px' }}>
                    {session.messages.length > 0 ? session.messages[session.messages.length - 1].text.substring(0, 80) + '...' : 'No messages'}
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}