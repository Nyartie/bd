CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL CHECK (phone ~ '^\+?[0-9]{7,15}$'),
    email VARCHAR(100) UNIQUE NOT NULL CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    hashed_password VARCHAR(100) NOT NULL,
    registration_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE clients IS 'Пользователи системы аренды';
COMMENT ON COLUMN clients.phone IS 'Формат: +7XXXXXXXXXX или XXXXXXXXXXXX';

CREATE TABLE IF NOT EXISTS skate_models (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(50) NOT NULL,
    model_name VARCHAR(50) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('hockey', 'figure', 'speed')),
    description TEXT
);

CREATE TABLE IF NOT EXISTS sizes (
    id SERIAL PRIMARY KEY,
    skate_model_id INT NOT NULL REFERENCES skate_models(id) ON DELETE CASCADE,
    size INT NOT NULL CHECK (size BETWEEN 25 AND 50),
    UNIQUE (skate_model_id, size)
);

CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    size_id INT NOT NULL REFERENCES sizes(id) ON DELETE CASCADE,
    status VARCHAR(10) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'rented', 'repair')),
    purchase_date DATE NOT NULL DEFAULT CURRENT_DATE,
    last_maintenance DATE
);

CREATE TABLE IF NOT EXISTS rentals (
    id SERIAL PRIMARY KEY,
    client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    inventory_id INT NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP CHECK (end_time > start_time),
    price_per_hour NUMERIC(8,2) NOT NULL DEFAULT 5.00,
    total_cost NUMERIC(10,2)
);

COMMENT ON COLUMN rentals.end_time IS 'Время окончания аренды';

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    rental_id INT NOT NULL REFERENCES rentals(id) ON DELETE CASCADE,
    amount NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    payment_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payment_method VARCHAR(20) CHECK (payment_method IN ('cash', 'card', 'online'))
);

CREATE TABLE IF NOT EXISTS action_log (
    id SERIAL PRIMARY KEY,
    event_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INT REFERENCES clients(id) ON DELETE SET NULL,
    action_type VARCHAR(20) NOT NULL,
    details TEXT
);



CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);
CREATE INDEX IF NOT EXISTS idx_rentals_active ON rentals(end_time) WHERE end_time IS NULL;
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(status);


CREATE OR REPLACE VIEW active_rentals_view AS
SELECT
    r.id AS rental_id,
    c.name AS client_name,
    CONCAT(sm.brand, ' ', sm.model_name) AS skate_model,
    s.size,
    r.start_time,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.start_time))/3600 AS hours_rented
FROM rentals r
JOIN clients c ON r.client_id = c.id
JOIN inventory i ON r.inventory_id = i.id
JOIN sizes s ON i.size_id = s.id
JOIN skate_models sm ON s.skate_model_id = sm.id
WHERE r.end_time IS NULL;

COMMENT ON VIEW active_rentals_view IS 'Текущие активные аренды с расчетом времени';


CREATE OR REPLACE FUNCTION calculate_rental_cost(rental_id INT)
RETURNS NUMERIC(10,2) AS $$
DECLARE
    rental_record RECORD;
    total_hours NUMERIC;
BEGIN
    SELECT start_time, end_time, price_per_hour
    INTO rental_record
    FROM rentals
    WHERE id = rental_id;

    IF rental_record.end_time IS NULL THEN
        total_hours := EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - rental_record.start_time))/3600;
    ELSE
        total_hours := EXTRACT(EPOCH FROM (rental_record.end_time - rental_record.start_time))/3600;
    END IF;

    RETURN total_hours * rental_record.price_per_hour;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_inventory_status()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        UPDATE inventory SET status = 'rented' WHERE id = NEW.inventory_id;
    ELSIF (TG_OP = 'UPDATE' AND NEW.end_time IS NOT NULL) THEN
        UPDATE inventory SET status = 'available' WHERE id = NEW.inventory_id;
    END IF;

    INSERT INTO action_log (user_id, action_type, details)
    VALUES (
        NEW.client_id,
        TG_OP,
        'Inventory ID: ' || NEW.inventory_id || ', Status: ' ||
        CASE WHEN TG_OP = 'INSERT' THEN 'rented' ELSE 'available' END
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_rentals_inventory
AFTER INSERT OR UPDATE ON rentals
FOR EACH ROW EXECUTE FUNCTION update_inventory_status();



REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;

CREATE ROLE rental_admin WITH LOGIN PASSWORD 'admin123';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rental_admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rental_admin;

CREATE ROLE rental_client;
GRANT SELECT, INSERT ON rentals, payments TO rental_client;
GRANT SELECT ON active_rentals_view TO rental_client;



COMMENT ON FUNCTION calculate_rental_cost IS 'Расчет стоимости аренды по времени';
COMMENT ON TRIGGER trg_rentals_inventory ON rentals IS 'Автоматическое обновление статуса инвентаря';