-- Migration 015: Diagnostic MCQ + AI plan + solution upload

-- Opțiunile grilă per exercițiu diagnostic
ALTER TABLE diagnostic_exercises
ADD COLUMN IF NOT EXISTS options       JSONB,           -- ["opt0","opt1","opt2","opt3"] (shuffled)
ADD COLUMN IF NOT EXISTS correct_option_index INTEGER,  -- 0-3, care opțiune e corectă
ADD COLUMN IF NOT EXISTS selected_option INTEGER;       -- opțiunea aleasă de student

-- Upload soluție scrisă la finalul testului diagnostic
ALTER TABLE diagnostic_tests
ADD COLUMN IF NOT EXISTS solution_file_path TEXT;

-- Planul AI generat de Claude
ALTER TABLE learning_paths
ADD COLUMN IF NOT EXISTS ai_plan JSONB,     -- JSON structurat cu săptămâni, sfaturi
ADD COLUMN IF NOT EXISTS ai_plan_text TEXT; -- fallback text dacă JSON nu e disponibil
