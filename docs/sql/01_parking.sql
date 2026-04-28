-- Create the parking_spots table
CREATE TABLE IF NOT EXISTS parking_spots (
    spot_number BIGINT PRIMARY KEY,
    spot_type TEXT,
    is_guest BOOLEAN,
    discord_userid TEXT,
    discord_nickname TEXT
);

-- Create the parking_offers table
CREATE TABLE IF NOT EXISTS parking_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spot_number BIGINT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    owner_id TEXT,
    owner_discord_username TEXT,
    FOREIGN KEY (spot_number) REFERENCES parking_spots(spot_number)
);

-- Create the parking_reservations table
CREATE TABLE IF NOT EXISTS parking_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spot_number INT,
    claimer_id TEXT,
    start_time TIMESTAMPTZ,
    offer_id UUID,
    end_time TIMESTAMPTZ,
    claimer_discord_username TEXT,
    FOREIGN KEY (spot_number) REFERENCES parking_spots(spot_number),
    FOREIGN KEY (offer_id) REFERENCES parking_offers(id)
);