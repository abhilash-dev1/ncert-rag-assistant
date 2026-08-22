import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LibraryPage from './components/LibraryPage';
import ReaderPage from './components/ReaderPage';
import ChatPage from './components/ChatPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/reader/:bookId" element={<ReaderPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;