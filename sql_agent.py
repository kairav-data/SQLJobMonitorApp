import pyodbc

def build_conn_string(server, driver='{ODBC Driver 17 for SQL Server}'):
    address = server.get('address')
    instance = server.get('instance')
    user = server.get('user')
    password = server.get('password')
    server_str = f"{address}\\{instance}" if instance else address
    if user and password:
        return f"DRIVER={driver};SERVER={server_str};DATABASE=msdb;UID={user};PWD={password};TrustServerCertificate=yes;"
    return f"DRIVER={driver};SERVER={server_str};DATABASE=msdb;Trusted_Connection=yes;TrustServerCertificate=yes;"

def get_connection(server):
    """Try modern driver first, fallback to legacy."""
    conn_str = build_conn_string(server)
    try:
        return pyodbc.connect(conn_str, timeout=5)
    except Exception:
        fallback = build_conn_string(server, driver='{SQL Server}')
        return pyodbc.connect(fallback, timeout=5)

def test_connection(server):
    try:
        conn = get_connection(server)
        conn.close()
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)

def fetch_jobs(server):
    try:
        conn = get_connection(server)
    except Exception as e:
        return False, str(e)

    cursor = conn.cursor()
    query = """
    SELECT 
        j.job_id AS id,
        j.name,
        j.enabled,
        ISNULL(j.description, '') AS description,
        CASE 
            WHEN jh.run_status = 0 THEN 'Failed'
            WHEN jh.run_status = 1 THEN 'Succeeded'
            WHEN jh.run_status = 2 THEN 'Retry'
            WHEN jh.run_status = 3 THEN 'Canceled'
            WHEN jh.run_status = 4 THEN 'In Progress'
            ELSE 'Unknown'
        END AS last_run_status,
        ja.start_execution_date,
        ja.stop_execution_date,
        ja.next_scheduled_run_date,
        CASE WHEN ja.start_execution_date IS NOT NULL AND ja.stop_execution_date IS NOT NULL
             THEN DATEDIFF(SECOND, ja.start_execution_date, ja.stop_execution_date)
             ELSE NULL END AS duration_seconds
    FROM msdb.dbo.sysjobs j
    LEFT JOIN msdb.dbo.sysjobactivity ja ON ja.job_id = j.job_id 
        AND ja.session_id = (SELECT TOP 1 session_id FROM msdb.dbo.syssessions ORDER BY agent_start_date DESC)
    LEFT JOIN msdb.dbo.sysjobhistory jh ON j.job_id = jh.job_id
        AND jh.instance_id = (SELECT MAX(instance_id) FROM msdb.dbo.sysjobhistory WHERE job_id = j.job_id AND step_id = 0)
    ORDER BY j.name
    """
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        jobs = []
        for row in rows:
            jobs.append({
                "job_id": row.id,
                "name": row.name,
                "enabled": row.enabled,
                "description": row.description,
                "last_run_status": row.last_run_status,
                "start_execution_date": row.start_execution_date,
                "stop_execution_date": row.stop_execution_date,
                "next_scheduled_run_date": row.next_scheduled_run_date,
                "duration_seconds": row.duration_seconds,
            })
        conn.close()
        return True, jobs
    except Exception as e:
        conn.close()
        return False, str(e)

def fetch_job_history(server, job_name, limit=20):
    try:
        conn = get_connection(server)
    except Exception as e:
        return False, str(e)

    cursor = conn.cursor()
    query = f"""
        SELECT TOP ({limit})
            CASE 
                WHEN jh.run_status = 0 THEN 'Failed'
                WHEN jh.run_status = 1 THEN 'Succeeded'
                WHEN jh.run_status = 2 THEN 'Retry'
                WHEN jh.run_status = 3 THEN 'Canceled'
                WHEN jh.run_status = 4 THEN 'In Progress'
                ELSE 'Unknown'
            END AS status,
            msdb.dbo.agent_datetime(jh.run_date, jh.run_time) AS run_datetime,
            (jh.run_duration / 10000 * 3600) + ((jh.run_duration % 10000) / 100 * 60) + (jh.run_duration % 100) AS duration_seconds,
            jh.message
        FROM msdb.dbo.sysjobhistory jh
        JOIN msdb.dbo.sysjobs j ON j.job_id = jh.job_id
        WHERE j.name = ? AND jh.step_id = 0
        ORDER BY jh.instance_id DESC
    """

    try:
        cursor.execute(query, job_name)
        rows = cursor.fetchall()
        history = []
        for row in rows:
            history.append({
                "status": row.status,
                "run_datetime": row.run_datetime,
                "duration_seconds": row.duration_seconds,
                "message": row.message,
            })
        conn.close()
        return True, history
    except Exception as e:
        conn.close()
        return False, str(e)

def run_job(server, job_name):
    try:
        conn = get_connection(server)
    except Exception as e:
        return False, str(e)

    try:
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"EXEC msdb.dbo.sp_start_job N'{job_name}'")
        conn.close()
        return True, f"Job '{job_name}' started successfully."
    except Exception as e:
        conn.close()
        return False, str(e)

def set_job_enabled(server, job_name, enabled: bool):
    try:
        conn = get_connection(server)
    except Exception as e:
        return False, str(e)

    try:
        conn.autocommit = True
        cursor = conn.cursor()
        proc = "sp_update_job"
        enabled_val = 1 if enabled else 0
        cursor.execute(f"EXEC msdb.dbo.{proc} @job_name=?, @enabled=?", job_name, enabled_val)
        conn.close()
        state = "enabled" if enabled else "disabled"
        return True, f"Job '{job_name}' {state}."
    except Exception as e:
        conn.close()
        return False, str(e)
