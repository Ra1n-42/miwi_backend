FROM mysql:latest

# Kopiere benutzerdefinierte SQL-Skripte, falls nötig
# COPY ./init.sql /docker-entrypoint-initdb.d/

# Kopiere mysql config und füge sie in den image/container hinzu
COPY ./my.cnf /etc/mysql/conf.d/my.cnf
