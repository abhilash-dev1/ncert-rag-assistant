import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { loadBooks } from '../data/books';
import { GoogleOAuthProvider, GoogleLogin, googleLogout } from '@react-oauth/google';
import { jwtDecode } from 'jwt-decode';

const GOOGLE_CLIENT_ID = "332298862506-s6cb3gnhvcbamvvb498hcji62ldto15n.apps.googleusercontent.com";

const coverColors = [
  '#2C3E50', '#E74C3C', '#3498DB', '#27AE60', '#8E44AD',
  '#D35400', '#16A085', '#C0392B', '#2980B9', '#F39C12'
];

const subjectIcons = {
  'History': '🏛️',
  'Geography': '🌍',
  'Civics': '⚖️',
  'Economics': '📈',
  'Sociology': '👥',
  'Political Science': '🏛️',
  'Social Science': '📚'
};

function LibraryContent() {
  const [selectedClass, setSelectedClass] = useState('all');
  const [books, setBooks] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // ✅ Restore user from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('user');
    if (saved) {
      try {
        setUser(JSON.parse(saved));
      } catch (e) {
        localStorage.removeItem('user');
      }
    }
  }, []);

  // ✅ Only load books AFTER the user signs in
  useEffect(() => {
    if (!user) {
      setBooks([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    loadBooks().then(data => {
      setBooks(data);
      setLoading(false);
    });
  }, [user]);

  const classes = ['all', '6', '7', '8', '9', '10', '11', '12'];

  const filteredBooks = selectedClass === 'all'
    ? books
    : books.filter(book => book.class === selectedClass || book.class === 'all');

  const handleSignInSuccess = (credentialResponse) => {
    const decoded = jwtDecode(credentialResponse.credential);
    const userData = { name: decoded.name, email: decoded.email, picture: decoded.picture };
    setUser(userData);
    localStorage.setItem('user', JSON.stringify(userData));
  };

  const handleSignInError = () => {
    console.log('Sign-in error');
  };

  const handleLogout = () => {
    googleLogout();
    setUser(null);
    setBooks([]);
    localStorage.removeItem('user');
  };

  return (
    <div style={{
      fontFamily: "'Merriweather', Georgia, serif",
      background: '#faf9f6',
      minHeight: '100vh',
      padding: '0 40px 60px 40px',
      color: '#2c2c2c'
    }}>
      
      {/* Top Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '20px 0',
        borderBottom: '2px solid #8b0000'
      }}>
        <h1 style={{ fontSize: '28px', color: '#8b0000', margin: 0 }}>📚 NCERT Library</h1>
        
        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img src={user.picture} alt={user.name} style={{ width: '40px', height: '40px', borderRadius: '50%', border: '2px solid #8b0000' }} />
            <span style={{ fontSize: '14px', color: '#333' }}>{user.name}</span>
            <button onClick={handleLogout} style={{ background: '#f0f0f0', color: '#8b0000', border: '1px solid #8b0000', borderRadius: '20px', padding: '8px 16px', fontSize: '12px', cursor: 'pointer', fontFamily: "'Inter', sans-serif", fontWeight: '600' }}>
              Sign Out
            </button>
          </div>
        ) : (
          <GoogleLogin onSuccess={handleSignInSuccess} onError={handleSignInError} size="large" shape="pill" theme="outline" text="signin_with" />
        )}
      </div>

      {/* ✅ If NOT signed in, show only the sign-in prompt */}
      {!user ? (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          textAlign: 'center',
          padding: '40px'
        }}>
          <div style={{ fontSize: '80px', marginBottom: '20px' }}>🔐</div>
          <h2 style={{ fontSize: '26px', color: '#8b0000', marginBottom: '12px', fontFamily: "'Merriweather', serif" }}>
            Sign In Required
          </h2>
          <p style={{ fontSize: '16px', color: '#555', maxWidth: '500px', lineHeight: '1.7', marginBottom: '30px', fontFamily: "'Inter', sans-serif" }}>
            Please sign in with your Google account to access the NCERT Library, read textbooks, and chat with the AI Tutor.
          </p>
          <GoogleLogin onSuccess={handleSignInSuccess} onError={handleSignInError} size="large" shape="pill" theme="filled_blue" text="signin_with" />
        </div>
      ) : (
        <>
          {/* Class Filter */}
          <div style={{
            background: 'white',
            borderRadius: '12px',
            padding: '20px 30px',
            margin: '30px 0',
            boxShadow: '0 4px 20px rgba(0,0,0,0.05)',
            border: '1px solid #e0e0e0'
          }}>
            <h2 style={{ fontSize: '18px', color: '#333', marginBottom: '10px' }}>Choose Your Class</h2>
            <select value={selectedClass} onChange={(e) => setSelectedClass(e.target.value)} style={{ padding: '12px 20px', borderRadius: '8px', border: '2px solid #8b0000', fontSize: '16px', fontFamily: "'Inter', sans-serif", background: '#fff', minWidth: '200px', cursor: 'pointer' }}>
              {classes.map(cls => (
                <option key={cls} value={cls}>{cls === 'all' ? 'All Classes' : `Class ${cls}`}</option>
              ))}
            </select>
          </div>

          {/* Book Grid */}
          {loading ? (
            <p style={{ color: '#888', fontSize: '18px' }}>Loading textbooks...</p>
          ) : (
            <>
              <h2 style={{ fontSize: '22px', color: '#333', marginBottom: '20px' }}>
                {selectedClass === 'all' ? 'All Textbooks' : `Class ${selectedClass} Textbooks`}
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '30px' }}>
                {filteredBooks.length === 0 ? (
                  <p style={{ color: '#999' }}>No books found for this class.</p>
                ) : (
                  filteredBooks.map((book, index) => (
                    <Link to={`/reader/${encodeURIComponent(book.folder)}`} key={book.folder} style={{ textDecoration: 'none', color: 'inherit' }}>
                      <div style={{
                        background: 'white',
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
                        transition: 'transform 0.2s, boxShadow 0.2s',
                        border: '1px solid #e0e0e0'
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 8px 30px rgba(0,0,0,0.15)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 15px rgba(0,0,0,0.1)'; }}
                      >
                        <div style={{
                          height: '200px',
                          background: coverColors[index % coverColors.length],
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          padding: '10px',
                          position: 'relative',
                          borderLeft: '8px solid rgba(0,0,0,0.3)'
                        }}>
                          <div style={{ fontSize: '50px', marginBottom: '10px' }}>
                            {subjectIcons[book.subject] || '📚'}
                          </div>
                          <div style={{
                            fontSize: '14px',
                            fontWeight: 'bold',
                            color: 'white',
                            textAlign: 'center',
                            textShadow: '0 2px 4px rgba(0,0,0,0.3)',
                            lineHeight: '1.2'
                          }}>
                            {book.title}
                          </div>
                          <div style={{
                            position: 'absolute',
                            bottom: '10px',
                            left: '10px',
                            right: '10px',
                            textAlign: 'center',
                            background: 'rgba(0,0,0,0.3)',
                            color: 'white',
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '12px'
                          }}>
                            Class {book.class}
                          </div>
                        </div>
                        
                        <div style={{ padding: '12px 15px' }}>
                          <p style={{ fontSize: '13px', fontWeight: 'bold', color: '#333', margin: '0 0 4px 0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {book.title}
                          </p>
                          <p style={{ fontSize: '12px', color: '#888', margin: 0 }}>
                            {book.subject} | {book.chapters.length} Chapters
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function LibraryPage() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <LibraryContent />
    </GoogleOAuthProvider>
  );
}