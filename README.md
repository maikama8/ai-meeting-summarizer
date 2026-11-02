# AI Meeting / Voice Note Summarizer

A portfolio project that transcribes audio (meetings or voice notes) and generates concise summaries with action items using AI.

## Features (Planned / Scaffold)

- Upload or record audio
- Transcription (e.g. via Whisper or similar)
- AI-generated summary and key action items
- Simple web or CLI interface
- Export to Markdown or PDF

## Tech Stack (Suggested)

- Python 3.11+
- FastAPI or Streamlit for interface
- OpenAI / local LLM for summarization
- Whisper for transcription

## Getting Started

```bash
git clone https://github.com/maikama8/ai-meeting-summarizer.git
cd ai-meeting-summarizer
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Project Structure

```
ai-meeting-summarizer/
├── README.md
├── requirements.txt
├── app/
│   ├── main.py
│   └── summarizer.py
└── examples/
```

## Author

**Abdulrasheed Oseni** ([@maikama8](https://github.com/maikama8))

Built as a public portfolio project to demonstrate AI + audio processing skills.

## License

MIT
