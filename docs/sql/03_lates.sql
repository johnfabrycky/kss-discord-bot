-- Create the lates table
CREATE TABLE  IF NOT EXISTS lates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    nickname TEXT,
    role TEXT,
    meal TEXT,
    day_of_week TEXT,
    is_permanent BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
