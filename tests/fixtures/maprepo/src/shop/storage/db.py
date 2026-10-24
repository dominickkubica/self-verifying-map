"""Order storage. Everything that touches SQL lives here."""


def save_order(conn, order):
    conn.execute("INSERT INTO orders (id, customer_id) VALUES (?, ?)", order)


def fetch_order(conn, order_id):
    return conn.execute(
        "SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.id = ?",
        (order_id,),
    ).fetchone()


def purge(conn, table):
    conn.execute(f"DELETE FROM {table}")
