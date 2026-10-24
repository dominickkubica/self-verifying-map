# Notes

### table:orders
fact: 35d7f6475606
One row per order.

### table:customers
fact: 0823755d4380
Who placed each order.

### table:audit
fact: d986fb94f2bf
Written by nothing yet; reserved for the audit trail.

### trap:purge-takes-any-table
test: tests/test_db.py::test_purge_is_never_called_with_user_input
`purge` deletes from whatever table it is given.
