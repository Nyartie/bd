-- ######################################################
-- ##              Тестовые данные                    ##
-- ######################################################

-- Очистка таблиц (для перезаполнения)
TRUNCATE TABLE
    payments,
    rentals,
    inventory,
    sizes,
    skate_models,
    clients
RESTART IDENTITY CASCADE;

-- ############### Модели коньков ###############
INSERT INTO skate_models (brand, model_name, type, description)
VALUES
    ('Bauer', 'Vapor X500', 'hockey', 'Профессиональные хоккейные коньки для опытных игроков'),
    ('Riedell', 'Dart', 'figure', 'Базовая модель для начинающих фигуристов'),
    ('Jackson', 'Ultima', 'figure', 'Коньки для продвинутого фигурного катания'),
    ('CCM', 'JetSpeed FT4', 'hockey', 'Технологичные коньки для скоростного катания');

-- ############### Размеры моделей ###############
-- Bauer Vapor X500
INSERT INTO sizes (skate_model_id, size)
VALUES
    (1, 39), (1, 40), (1, 41), (1, 42), (1, 43);

-- Riedell Dart
INSERT INTO sizes (skate_model_id, size)
VALUES
    (2, 36), (2, 37), (2, 38), (2, 39);

-- Jackson Ultima
INSERT INTO sizes (skate_model_id, size)
VALUES
    (3, 38), (3, 39), (3, 40), (3, 41);

-- CCM JetSpeed FT4
INSERT INTO sizes (skate_model_id, size)
VALUES
    (4, 40), (4, 41), (4, 42), (4, 43);

-- ############### Инвентарь ###############
-- Для Bauer Vapor X500 (10 пар)
INSERT INTO inventory (size_id, status, purchase_date, last_maintenance)
SELECT
    id,
    CASE WHEN random() < 0.1 THEN 'repair' ELSE 'available' END,
    '2022-01-01'::DATE + (random()*200)::INT,
    CASE WHEN random() < 0.7 THEN CURRENT_DATE - (random()*90)::INT ELSE NULL END
FROM sizes WHERE skate_model_id = 1
CROSS JOIN generate_series(1,2);

-- Для Riedell Dart (8 пар)
INSERT INTO inventory (size_id, status)
SELECT id, 'available'
FROM sizes WHERE skate_model_id = 2
CROSS JOIN generate_series(1,2);

-- ############### Клиенты ###############
INSERT INTO clients (telegram_id, name, phone, email, hashed_password)
VALUES
    (123456789, 'Иван Петров', '+79161234567', 'ivan@mail.ru', 'pbkdf2_sha256$260000$abc...'),
    (987654321, 'Мария Сидорова', '+79031112233', 'mary@ya.ru', 'pbkdf2_sha256$260000$def...');

-- ############### Аренды ###############
-- Активные аренды
INSERT INTO rentals (client_id, inventory_id, start_time)
VALUES
    (1, 3, CURRENT_TIMESTAMP - INTERVAL '2 HOUR'),
    (2, 7, CURRENT_TIMESTAMP - INTERVAL '45 MINUTE');

-- Завершенные аренды
INSERT INTO rentals (client_id, inventory_id, start_time, end_time, price_per_hour)
VALUES
    (3, 2, '2023-10-01 14:00', '2023-10-01 16:30', 7.50),
    (1, 5, '2023-10-02 10:00', '2023-10-02 12:15', 6.00);

-- ############### Платежи ###############
INSERT INTO payments (rental_id, amount, payment_method)
VALUES
    (3, calculate_rental_cost(3), 'card'),
    (4, calculate_rental_cost(4), 'online');

-- ############### Логи действий ###############
INSERT INTO action_log (user_id, action_type, details)
VALUES
    (1, 'INSERT', 'Новая аренда ID 1'),
    (2, 'INSERT', 'Новая аренда ID 2'),
    (NULL, 'SYSTEM', 'Инициализация тестовых данных');