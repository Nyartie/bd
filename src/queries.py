class SQL:
    # =============================================
    # Запросы для работы с пользователями
    # =============================================

    GET_USER_BY_TG_ID = """
            SELECT * 
            FROM clients 
            WHERE telegram_id = $1
            LIMIT 1
        """

    REGISTER_USER = """
        INSERT INTO clients (name, email, phone, hashed_password) 
        VALUES ($1, $2, $3, $4)
        RETURNING id
    """

    GET_USER_BY_EMAIL = """
        SELECT * FROM clients 
        WHERE email = $1 
        LIMIT 1
    """

    UPDATE_USER_PROFILE = """
        UPDATE clients SET
            name = COALESCE($2, name),
            phone = COALESCE($3, phone)
        WHERE id = $1
    """

    # =============================================
    # Запросы для работы с арендами
    # =============================================

    CREATE_RENTAL = """
        INSERT INTO rentals (client_id, inventory_id, price_per_hour)
        VALUES ($1, $2, $3)
        RETURNING id
    """

    COMPLETE_RENTAL = """
        UPDATE rentals SET
            end_time = NOW(),
            total_cost = calculate_rental_cost(id)
        WHERE id = $1
    """

    GET_ACTIVE_RENTALS = """
            SELECT * 
            FROM rentals 
            WHERE is_active = TRUE
        """

    # =============================================
    # Запросы для работы с инвентарем
    # =============================================

    GET_AVAILABLE_SIZES = """
        SELECT DISTINCT s.size 
        FROM sizes s
        JOIN inventory i ON s.id = i.size_id
        WHERE i.status = 'available'
    """

    GET_INVENTORY_DETAILS = """
        SELECT i.id, sm.brand, s.size, i.status
        FROM inventory i
        JOIN sizes s ON i.size_id = s.id
        JOIN skate_models sm ON s.skate_model_id = sm.id
        WHERE s.size = $1 AND i.status = 'available'
    """

    UPDATE_INVENTORY_STATUS = """
        UPDATE inventory SET
            status = $2,
            last_maintenance = CASE WHEN $2 = 'repair' THEN NOW() ELSE last_maintenance END
        WHERE id = $1
    """

    # =============================================
    # Отчеты и аналитика
    # =============================================

    GET_RENTAL_HISTORY = """
        SELECT r.start_time, r.end_time, sm.brand, s.size, r.total_cost
        FROM rentals r
        JOIN inventory i ON r.inventory_id = i.id
        JOIN sizes s ON i.size_id = s.id
        JOIN skate_models sm ON s.skate_model_id = sm.id
        WHERE r.client_id = $1
        ORDER BY r.start_time DESC
    """

    GET_POPULAR_SIZES = """
        SELECT s.size, COUNT(*) as rentals_count
        FROM rentals r
        JOIN inventory i ON r.inventory_id = i.id
        JOIN sizes s ON i.size_id = s.id
        GROUP BY s.size
        ORDER BY rentals_count DESC
        LIMIT 5
    """

    GET_FINANCIAL_REPORT = """
        SELECT 
            DATE_TRUNC('day', payment_time) as day,
            SUM(amount) as total_income,
            COUNT(*) as transactions_count
        FROM payments
        GROUP BY day
        ORDER BY day DESC
    """

    # =============================================
    # Системные запросы
    # =============================================

    LOG_ACTION = """
        INSERT INTO action_log (user_id, action_type, details)
        VALUES ($1, $2, $3)
    """

    CLEANUP_OLD_LOGS = """
        DELETE FROM action_log 
        WHERE event_time < NOW() - INTERVAL '30 days'
    """