# PDF Translator

A modern FastAPI application that allows users to upload PDF files, extract text content page by page, and translate the text into any language supported by OpenAI's models.

## Features

- Upload PDF files via drag-and-drop or file browser
- Extract text content from PDF files
- Translate text to any language supported by OpenAI
- Modern, responsive UI with search functionality for language selection
- View original and translated text side by side

## Requirements

- Python 3.7+
- OpenAI API key

## Installation

1. Clone this repository:
```
git clone https://github.com/yourusername/pdf-translator-V3.git
cd pdf-translator-V3
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
   - Edit the `.env` file and replace `your_openai_api_key_here` with your actual OpenAI API key

## Usage

1. Start the application:
```
python -m uvicorn app.main:app --reload
```

2. Open your browser and navigate to `http://localhost:8000`

3. Upload a PDF file by dragging and dropping it into the designated area or by clicking "Browse Files"

4. Select the target language for translation from the dropdown menu

5. Click "Translate PDF" to start the translation process

6. View the original and translated text side by side, and navigate between pages using the page selector

## Project Structure

```
pdf-translator-V3/
├── app/
│   ├── routers/
│   │   ├── __init__.py
│   │   └── pdf_router.py
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css
│   │   └── js/
│   │       └── main.js
│   ├── templates/
│   │   └── index.html
│   ├── __init__.py
│   └── main.py
├── uploads/           # Created automatically when first PDF is uploaded
├── .env
├── README.md
└── requirements.txt
```

## Technologies Used

- FastAPI: Web framework for building APIs
- PyPDF2: PDF processing library
- OpenAI API: For text translation
- Tailwind CSS: For styling the UI
- JavaScript: For client-side functionality

## License

This project is licensed under the MIT License - see the LICENSE file for details.
