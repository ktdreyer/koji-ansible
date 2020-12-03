# Libary of shared functions for integration testing.

reset_database () {
    # Delete any existing koji database and recreate it empty.
    sudo -u postgres psql -c 'DROP DATABASE IF EXISTS koji;'
    sudo -u postgres psql -c 'DROP USER IF EXISTS koji;'
    sudo -u postgres psql -c 'CREATE DATABASE koji;'
    sudo -u postgres psql -c "CREATE USER koji WITH ENCRYPTED PASSWORD 'koji';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE koji TO koji;"

    export PGHOST=127.0.0.1
    export PGPASSWORD=koji

    # Import Koji schema:
    psql -q koji koji < koji/docs/schema.sql

    # Bootstrap the administrator account
    psql -U koji -c "INSERT INTO users (name, status, usertype) VALUES ('admin', 0, 0);"
    psql -U koji -c "INSERT INTO user_perms (user_id, perm_id, creator_id) VALUES (1, 1, 1);"
    unset PGPASSWORD
    unset PGHOST
}

reset_instance () {
    # Reset a running Koji instance to a pristine state.
    sudo systemctl stop apache2  # terminate any existing client connections
    reset_database
    sudo systemctl start apache2
    # Verify that we can log in.
    PYTHONPATH=$(pwd)/koji ./koji/cli/koji -p ci hello
}
