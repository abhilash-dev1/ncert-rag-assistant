import { useState, useEffect, useRef } from 'react';
import { FaPaperPlane, FaRobot, FaUser, FaTrash, FaDatabase, FaSearch, FaHistory, FaTimes, FaPlus } from 'react-icons/fa';

export default function ChatPage({ bookId, chapterId, userId = 1 }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messageCount, setMessageCount] = useState(0);
  const messagesEndRef = useRef(null);
  const MAX_MESSAGES = 50;

  const safeBookId = encodeURIComponent(bookId || '');
  const safeChapterId = encodeURIComponent(chapterId || '');

  // ✅ Reset when chapter changes
  useEffect(() => {
    setMessages([]);
    setCurrentSessionId(null);
    setMessageCount(0);
    setShowHistory(false);
  }, [bookId, chapterId]);

  // ✅ Load history filtered by book + chapter
  useEffect(() => {
    if (!bookId || !chapterId) return;
    fetch(`https://ncert-rag-assistant-production.up.railway.app/api/chat/history/${userId}?book_id=${safeBookId}&chapter_id=${safeChapterId}`)
      .then(res => res.json())
      .then(data => setHistory(data.history || []))
      .catch(err => console.error("Failed to load history:", err));
  }, [userId, bookId, chapterId]);

  const refreshHistory = () => {
    fetch(`https://ncert-rag-assistant-production.up.railway.app/api/chat/history/${userId}?book_id=${safeBookId}&chapter_id=${safeChapterId}`)
      .then(res => res.json())
      .then(data => setHistory(data.history || []));
  };

  const startNewChat = () => {
    setMessages([]);
    setInput('');
    setCurrentSessionId(null);
    setMessageCount(0);
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    if (messageCount >= MAX_MESSAGES) {
      alert("You have reached the 50 questions limit. Click 'New Chat' to start fresh.");
      return;
    }

    const userMsg = { id: Date.now(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setMessageCount(prev => prev + 1);

    try {
      // ✅ FIXED: Pointing to Railway URL
      const response = await fetch('https://ncert-rag-assistant-production.up.railway.app/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: input,
          book_id: bookId || null,
          chapter_id: chapterId || null,
          session_id: currentSessionId
        }),
      });

      const data = await response.json();

      if (data.session_id && !currentSessionId) {
        setCurrentSessionId(data.session_id);
      }

      const answerText = data.answer && data.answer.trim() 
        ? data.answer 
        : '⚠️ Could not find a clear answer. Please try rephrasing.';

      const aiMsg = {
        id: Date.now() + 1,
        sender: 'ai',
        text: answerText,
        sources: data.sources || [],
        chunks: data.chunks || [],
        scores: data.scores || []
      };
      setMessages(prev => [...prev, aiMsg]);
      refreshHistory();

    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'ai', text: '❌ Backend not reachable.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => e.key === 'Enter' && sendMessage();
  const clearChat = () => { setMessages([]); setCurrentSessionId(null); setMessageCount(0); };

  // ✅ Load a full session from history
  const loadChatFromHistory = (sessionId) => {
    // ✅ FIXED: Pointing to Railway URL
    fetch(`https://ncert-rag-assistant-production.up.railway.app/api/chat/${sessionId}`)
      .then(res => res.json())
      .then(data => {
        const loadedMessages = data.messages.map((msg, idx) => {
          let parsedSources = [];
          try {
            parsedSources = msg.sources ? JSON.parse(msg.sources) : [];
          } catch (e) {
            console.error("Failed to parse sources", e);
          }
          return {
            id: Date.now() + idx,
            sender: msg.sender,
            text: msg.text,
            sources: parsedSources
          };
        });
        setMessages(loadedMessages);
        setCurrentSessionId(sessionId);
        // Count only user messages for the limit
        setMessageCount(loadedMessages.filter(m => m.sender === 'user').length);
        setShowHistory(false);
      });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'linear-gradient(135deg, #f5f7fa, #c3cfe2)', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0,0,0,0.1)', fontFamily: "'Inter', sans-serif" }}>

      {/* Header */}
      <div style={{ background: 'linear-gradient(135deg, #8b0000, #b22222)', color: 'white', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FaRobot size={20} />
          <div>
            <div style={{ fontWeight: 'bold', fontSize: '14px' }}>AI Tutor Chat</div>
            <div style={{ fontSize: '11px', opacity: 0.8 }}>
              {chapterId} | {messageCount}/{MAX_MESSAGES} questions
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <button onClick={startNewChat} style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', borderRadius: '16px', padding: '6px 10px', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <FaPlus size={10} /> New Chat
          </button>
          <button onClick={() => setShowHistory(true)} style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', borderRadius: '16px', padding: '6px 10px', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <FaHistory size={10} /> History
          </button>
          <button onClick={clearChat} style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', borderRadius: '16px', padding: '6px 10px', cursor: 'pointer', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <FaTrash size={10} /> Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '40px', color: '#888' }}>
            <FaRobot size={40} style={{ marginBottom: '10px', color: '#8b0000' }} />
            <p style={{ fontSize: '14px' }}>Start a new conversation for {chapterId}!</p>
            <p style={{ fontSize: '12px', color: '#aaa' }}>Ask a question to begin.</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} style={{ display: 'flex', justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start', marginBottom: '10px', alignItems: 'flex-end', gap: '6px' }}>
            {msg.sender === 'ai' && (
              <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: 'linear-gradient(135deg, #8b0000, #b22222)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <FaRobot size={12} />
              </div>
            )}

            <div style={{ maxWidth: '80%', padding: '10px 14px', borderRadius: msg.sender === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px', background: msg.sender === 'user' ? 'linear-gradient(135deg, #8b0000, #b22222)' : 'white', color: msg.sender === 'user' ? 'white' : '#333', boxShadow: '0 2px 8px rgba(0,0,0,0.05)', fontSize: '13px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
              {msg.text}

              {msg.sources && msg.sources.length > 0 && (
                <div style={{ fontSize: '10px', marginTop: '6px', opacity: 0.8, borderTop: '1px solid rgba(0,0,0,0.1)', paddingTop: '4px' }}>
                  <FaDatabase style={{ marginRight: '4px' }} /> Sources: {msg.sources.join(', ')}
                </div>
              )}

              {msg.chunks && msg.chunks.length > 0 && (
                <div style={{ marginTop: '8px', background: '#f0f4ff', borderRadius: '6px', padding: '8px', border: '1px solid #c7d2fe' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '10px', color: '#1e3a8a', marginBottom: '4px' }}>
                    <FaSearch style={{ marginRight: '4px' }} /> Retrieved Knowledge:
                  </div>
                  {msg.chunks.map((chunk, idx) => (
                    <div key={idx} style={{ fontSize: '10px', color: '#555', marginBottom: '4px', borderLeft: '2px solid #3b82f6', paddingLeft: '6px' }}>
                      <div style={{ fontWeight: 'bold', color: '#2563eb' }}>Chunk {idx + 1} | Score: {msg.scores && msg.scores[idx] ? msg.scores[idx].toFixed(3) : 'N/A'}</div>
                      <div style={{ marginTop: '2px' }}>{chunk.substring(0, 100)}...</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: '#3182ce', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <FaUser size={12} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: 'linear-gradient(135deg, #8b0000, #b22222)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FaRobot size={12} />
            </div>
            <div style={{ background: 'white', padding: '8px 14px', borderRadius: '14px', color: '#888', fontSize: '13px' }}>Retrieving knowledge...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '10px', background: 'white', borderTop: '1px solid #e0e0e0' }}>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            onKeyPress={handleKeyPress} 
            placeholder={`Ask about ${chapterId}...`} 
            style={{ flex: 1, padding: '10px 14px', borderRadius: '20px', border: '1px solid #ddd', fontSize: '13px', outline: 'none', background: '#f9f9f9' }} 
          />
          <button onClick={sendMessage} style={{ background: 'linear-gradient(135deg, #8b0000, #b22222)', color: 'white', border: 'none', borderRadius: '50%', width: '38px', height: '38px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FaPaperPlane size={14} />
          </button>
        </div>
        <div style={{ textAlign: 'center', marginTop: '6px', fontSize: '10px', color: '#aaa' }}>
          Powered by NCERT RAG + Gemini AI | Max {MAX_MESSAGES} questions per chat
        </div>
      </div>

      {/* History Panel */}
      {showHistory && (
        <>
          <div onClick={() => setShowHistory(false)} style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.3)', zIndex: 999 }} />
          <div style={{ position: 'fixed', top: 0, right: 0, width: '380px', height: '100vh', background: 'white', zIndex: 1000, boxShadow: '-5px 0 20px rgba(0,0,0,0.2)', padding: '20px', overflowY: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', color: '#333' }}>
                <FaHistory style={{ marginRight: '8px', color: '#8b0000' }} /> History — {chapterId}
              </h3>
              <button onClick={() => setShowHistory(false)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#666' }}><FaTimes /></button>
            </div>

            {history.length === 0 ? (
              <p style={{ textAlign: 'center', color: '#999', marginTop: '50px' }}>No chat sessions for this chapter yet.</p>
            ) : (
              history.map((session, idx) => (
                <div 
                  key={idx} 
                  onClick={() => loadChatFromHistory(session.session_id)}
                  style={{
                    marginBottom: '12px',
                    padding: '14px',
                    borderRadius: '10px',
                    background: currentSessionId === session.session_id ? '#fef3f3' : '#f9f9f9',
                    border: currentSessionId === session.session_id ? '2px solid #8b0000' : '1px solid #e0e0e0',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#f0f0f0'}
                  onMouseLeave={(e) => e.currentTarget.style.background = currentSessionId === session.session_id ? '#fef3f3' : '#f9f9f9'}
                >
                  <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#8b0000', marginBottom: '6px' }}>
                    📝 {session.title || 'Chat Session'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#888', marginBottom: '6px' }}>
                    {Math.floor(session.messages.length / 2)} Q&A pairs | {session.created_at ? new Date(session.created_at).toLocaleString() : ''}
                  </div>
                  <div style={{ fontSize: '11px', color: '#555' }}>
                    {session.messages.length > 0 ? session.messages[0].text.substring(0, 70) + '...' : 'No messages'}
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