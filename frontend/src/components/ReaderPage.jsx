import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';
import { loadBooks } from '../data/books';
import { FaArrowLeft, FaChevronLeft, FaChevronRight, FaRobot, FaStickyNote, FaExpand, FaCompress, FaPlus, FaMinus, FaWindowMinimize } from 'react-icons/fa';
import ChatPage from './ChatPage';
import NotesPanel from './NotesPanel';

import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';

import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = pdfjsWorker;

export default function ReaderPage() {
  const { bookId } = useParams();
  const navigate = useNavigate();

  const [book, setBook] = useState(null);
  const [currentChapter, setCurrentChapter] = useState(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [activePanel, setActivePanel] = useState('chat');
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [scale, setScale] = useState(2.0);
  const [isPanelVisible, setIsPanelVisible] = useState(false);

  const folderName = decodeURIComponent(bookId);

  useEffect(() => {
    loadBooks().then(allBooks => {
      const foundBook = allBooks.find(b => b.folder === folderName);
      setBook(foundBook);
      if (foundBook && foundBook.chapters.length > 0) {
        setCurrentChapter(foundBook.chapters[0]);
        setPageNumber(1);
      }
    });
  }, [folderName]);

  const onDocumentLoadSuccess = ({ numPages }) => setNumPages(numPages);

  const handleChapterClick = (chapter) => {
    setCurrentChapter(chapter);
    setPageNumber(1);
    setIsPanelVisible(false);
  };

  const goToPrevPage = () => pageNumber > 1 && setPageNumber(pageNumber - 1);
  const goToNextPage = () => pageNumber < numPages && setPageNumber(pageNumber + 1);

  const zoomIn = () => setScale(prev => Math.min(prev + 0.2, 3.0));
  const zoomOut = () => setScale(prev => Math.max(prev - 0.2, 1.0));

  const openChat = () => { setActivePanel('chat'); setIsPanelVisible(true); };
  const openNotes = () => { setActivePanel('notes'); setIsPanelVisible(true); };
  const minimizePanel = () => setIsPanelVisible(false);

  if (!book) return <div style={{ padding: '40px', textAlign: 'center' }}>Loading book...</div>;

  const pdfUrl = currentChapter
    ? `http://localhost:8000/api/pdf/${encodeURIComponent(book.folder)}/${encodeURIComponent(currentChapter)}`
    : null;

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', fontFamily: "'Merriweather', serif", background: '#faf9f6', overflow: 'hidden' }}>

      {/* LEFT SIDE */}
      <div style={{ flex: isFullScreen ? 1 : 4, display: 'flex', flexDirection: 'column', background: '#e8e8e8', padding: '20px', overflow: 'hidden', position: 'relative' }}>

        {/* Top Bar */}
        <div style={{ position: 'absolute', top: '10px', left: '20px', right: '20px', zIndex: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button onClick={() => navigate('/library')} style={{ background: '#8b0000', color: 'white', border: 'none', borderRadius: '20px', padding: '8px 15px', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FaArrowLeft /> Back to Library
          </button>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={zoomOut} style={{ background: '#4a5568', color: 'white', border: 'none', borderRadius: '20px', padding: '8px 12px', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <FaMinus /> Zoom
            </button>
            <button onClick={() => setIsFullScreen(!isFullScreen)} style={{ background: '#2b6cb0', color: 'white', border: 'none', borderRadius: '20px', padding: '8px 15px', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
              {isFullScreen ? <FaCompress /> : <FaExpand />} {isFullScreen ? 'Exit' : 'Full Screen'}
            </button>
            <button onClick={openChat} style={{ background: '#3182ce', color: 'white', border: 'none', borderRadius: '20px', padding: '8px 15px', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FaRobot /> Chat
            </button>
            <button onClick={openNotes} style={{ background: '#38a169', color: 'white', border: 'none', borderRadius: '20px', padding: '8px 15px', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FaStickyNote /> Notes
            </button>
            <button onClick={zoomIn} style={{ background: '#2f855a', color: 'white', border: 'none', borderRadius: '20px', padding: '8px 12px', fontSize: '14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <FaPlus /> Zoom
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div style={{ marginTop: '60px', flex: 1, position: 'relative', overflow: 'hidden' }}>

          {/* PDF VIEWER */}
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            display: 'flex', flexDirection: 'column', alignItems: 'center', overflow: 'hidden',
            visibility: isPanelVisible ? 'hidden' : 'visible',
            pointerEvents: isPanelVisible ? 'none' : 'auto'
          }}>
            {pdfUrl ? (
              <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none', width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
                <Document file={pdfUrl} onLoadSuccess={onDocumentLoadSuccess} loading={<div>Loading chapter...</div>} error={<div style={{ color: 'red' }}>❌ Failed to load PDF.</div>}>
                  <Page pageNumber={pageNumber} scale={scale} />
                </Document>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: '#666', marginTop: '50px' }}>
                <div style={{ fontSize: '80px' }}>📖</div>
                <h3>{book.title}</h3>
                <p>Select a chapter from the right side.</p>
              </div>
            )}

            {pdfUrl && (
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', padding: '10px' }}>
                <button onClick={goToPrevPage} disabled={pageNumber <= 1} style={{ background: '#8b0000', color: 'white', border: 'none', borderRadius: '50%', width: '40px', height: '40px', cursor: 'pointer', fontSize: '18px', opacity: pageNumber <= 1 ? 0.5 : 1 }}>
                  <FaChevronLeft />
                </button>
                <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#333' }}>Page {pageNumber} of {numPages || '...'}</span>
                <button onClick={goToNextPage} disabled={pageNumber >= numPages} style={{ background: '#8b0000', color: 'white', border: 'none', borderRadius: '50%', width: '40px', height: '40px', cursor: 'pointer', fontSize: '18px', opacity: pageNumber >= numPages ? 0.5 : 1 }}>
                  <FaChevronRight />
                </button>
              </div>
            )}
          </div>

          {/* PANEL */}
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            background: 'white',
            borderRadius: '12px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            visibility: isPanelVisible ? 'visible' : 'hidden',
            pointerEvents: isPanelVisible ? 'auto' : 'none'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 20px', borderBottom: '1px solid #e0e0e0', background: '#f8f9fa', flexShrink: 0 }}>
              <span style={{ fontWeight: 'bold', color: '#333' }}>
                {activePanel === 'chat' ? 'AI Tutor Chat' : 'My Notes'} — {currentChapter}
              </span>
              <button onClick={minimizePanel} style={{ background: 'none', border: 'none', fontSize: '16px', cursor: 'pointer', color: '#666', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <FaWindowMinimize /> Minimize
              </button>
            </div>

            <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: activePanel === 'chat' ? 'flex' : 'none', flexDirection: 'column' }}>
                <ChatPage bookId={folderName} chapterId={currentChapter} />
              </div>
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: activePanel === 'notes' ? 'flex' : 'none', flexDirection: 'column' }}>
                <NotesPanel bookId={folderName} chapterId={currentChapter} pageNumber={pageNumber} bookTitle={book.title} />
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* RIGHT SIDE - Chapter List */}
      {!isFullScreen && (
        <div style={{ flex: 1, background: '#8b0000', color: 'white', display: 'flex', flexDirection: 'column', padding: '20px', overflowY: 'hidden', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
          <style>{`::-webkit-scrollbar { display: none !important; }`}</style>
          <h2 style={{ fontSize: '18px', marginBottom: '10px', borderBottom: '2px solid white', paddingBottom: '10px' }}>{book.title}</h2>
          <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            {book.chapters.length === 0 ? (
              <p style={{ color: '#ccc', fontSize: '14px' }}>No chapters found.</p>
            ) : (
              book.chapters.map((chapter, index) => (
                <button key={index} onClick={() => handleChapterClick(chapter)} style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  background: currentChapter === chapter ? 'rgba(255,255,255,0.2)' : 'transparent',
                  border: 'none', color: 'white', padding: '10px 0', fontSize: '14px',
                  cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.2)'
                }}>
                  {chapter} <span style={{ float: 'right', fontSize: '12px' }}>(Open)</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}