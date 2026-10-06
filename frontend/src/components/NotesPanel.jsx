import { useState, useEffect } from 'react';
import { FaStickyNote, FaTrash, FaEdit } from 'react-icons/fa';

export default function NotesPanel({ bookId, chapterId, pageNumber, userId = 1, bookTitle }) {
  const [notes, setNotes] = useState([]);
  const [noteInput, setNoteInput] = useState('');
  const [editingId, setEditingId] = useState(null);

  const safeBookId = encodeURIComponent(bookId || '');
  const safeChapterId = encodeURIComponent(chapterId || '');

  // ✅ Reload notes when chapter changes
  useEffect(() => {
    if (!bookId || !chapterId) return;
    fetch(`http://localhost:8000/api/notes/${safeBookId}/${userId}?chapter_id=${safeChapterId}`)
      .then(res => res.json())
      .then(data => setNotes(data.notes || []))
      .catch(err => console.error("Failed to load notes:", err));
  }, [bookId, chapterId, userId]);

  const addNote = () => {
    if (!noteInput.trim()) return;
    fetch('http://localhost:8000/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: bookId,
        chapter_id: chapterId,
        page_number: pageNumber,
        content: noteInput
      })
    })
    .then(res => res.json())
    .then(() => {
      fetch(`http://localhost:8000/api/notes/${safeBookId}/${userId}?chapter_id=${safeChapterId}`)
        .then(res => res.json())
        .then(data => setNotes(data.notes || []));
    });
    setNoteInput('');
  };

  const deleteNote = (id) => {
    fetch(`http://localhost:8000/api/notes/${id}`, { method: 'DELETE' })
      .then(() => {
        fetch(`http://localhost:8000/api/notes/${safeBookId}/${userId}?chapter_id=${safeChapterId}`)
          .then(res => res.json())
          .then(data => setNotes(data.notes || []));
      });
  };

  const startEdit = (note) => { setEditingId(note.id); setNoteInput(note.content); };
  const updateNote = () => {
    if (!noteInput.trim() || !editingId) return;
    fetch('http://localhost:8000/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_id: bookId, chapter_id: chapterId, page_number: pageNumber, content: noteInput })
    }).then(() => {
      fetch(`http://localhost:8000/api/notes/${safeBookId}/${userId}?chapter_id=${safeChapterId}`)
        .then(res => res.json())
        .then(data => setNotes(data.notes || []));
    });
    setNoteInput('');
    setEditingId(null);
  };

  const cancelEdit = () => { setNoteInput(''); setEditingId(null); };

  return (
    <div style={{ background: '#fffdf5', height: '100%', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ background: '#38a169', color: 'white', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <FaStickyNote size={18} />
        <div>
          <div style={{ fontWeight: 'bold' }}>My Notes</div>
          <div style={{ fontSize: '11px', opacity: 0.8 }}>{bookTitle} — {chapterId}</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        {notes.length === 0 && (
          <div style={{ textAlign: 'center', color: '#999', marginTop: '30px' }}>
            <FaStickyNote size={40} style={{ marginBottom: '10px', color: '#38a169' }} />
            <p>No notes yet for this chapter.</p>
          </div>
        )}
        {notes.map((note) => (
          <div key={note.id} style={{ marginBottom: '10px', padding: '10px', background: 'white', borderRadius: '8px', borderLeft: '4px solid #38a169' }}>
            <p style={{ margin: '0 0 4px 0', color: '#333', whiteSpace: 'pre-wrap' }}>{note.content}</p>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#888' }}>
              <span>📄 Page {note.page}</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => startEdit(note)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#2b6cb0' }}><FaEdit /></button>
                <button onClick={() => deleteNote(note.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#e53e3e' }}><FaTrash /></button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding: '12px', background: 'white', borderTop: '1px solid #e0e0e0' }}>
        <textarea value={noteInput} onChange={(e) => setNoteInput(e.target.value)} rows="2" placeholder={`Write a note for ${chapterId}...`} style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #ccc', resize: 'none' }} />
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          <button onClick={editingId ? updateNote : addNote} style={{ flex: 1, padding: '8px', background: editingId ? '#2b6cb0' : '#38a169', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
            {editingId ? 'Update' : 'Add'}
          </button>
          {editingId && <button onClick={cancelEdit} style={{ padding: '8px', background: '#e0e0e0', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>Cancel</button>}
        </div>
      </div>
    </div>
  );
}