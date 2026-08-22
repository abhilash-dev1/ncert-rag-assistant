// frontend/src/data/books.js
export const books = [];

export async function loadBooks() {
  try {
    const response = await fetch('http://localhost:8000/api/textbooks');
    const data = await response.json();

    if (data.textbooks && data.textbooks.length > 0) {
      const loadedBooks = data.textbooks.map((tb) => ({
        id: tb.folder,  // ✅ Use folder name as stable ID
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