-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- PDFs table
CREATE TABLE IF NOT EXISTS pdfs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    total_pages INTEGER,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Sections table
CREATE TABLE IF NOT EXISTS sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pdf_id UUID REFERENCES pdfs(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    content_text TEXT,
    section_order INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Cards table (each query/note a user creates)
CREATE TABLE IF NOT EXISTS cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pdf_id UUID REFERENCES pdfs(id) ON DELETE CASCADE,
    section_id UUID REFERENCES sections(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    card_type TEXT DEFAULT 'question' CHECK (card_type IN ('question', 'note')),
    selected_text TEXT,
    page_number INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Messages table (conversation thread inside each card)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_sections_pdf_id ON sections(pdf_id);
CREATE INDEX IF NOT EXISTS idx_cards_pdf_id ON cards(pdf_id);
CREATE INDEX IF NOT EXISTS idx_cards_section_id ON cards(section_id);
CREATE INDEX IF NOT EXISTS idx_messages_card_id ON messages(card_id);