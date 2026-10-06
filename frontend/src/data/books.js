// frontend/src/data/books.js
export const books = [];

const API_BASE = 'https://ncert-rag-assistant-production-ea73.up.railway.app';

export async function loadBooks() {
  try {
    const response = await fetch(`${API_BASE}/api/textbooks`);
    const data = await response.json();

    if (data.textbooks && data.textbooks.length > 0) {
      const loadedBooks = data.textbooks.map((tb) => ({
        id: tb.folder,
        title: tb.folder,
        subject: 'NCERT',
        class: extractClass(tb.folder),
        folder: tb.folder,
        chapters: tb.chapters,
      }));

      books.length = 0;
      books.push(...loadedBooks);
      return books;
    }
  } catch (error) {
    console.error("Failed to load textbooks:", error);
  }

  return [];
}

function extractClass(folderName) {
  const match = folderName.match(/class\s*(\d+)/i);
  return match ? match[1] : 'all';
}